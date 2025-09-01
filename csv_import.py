#!/usr/bin/env python3
"""
B2B RAG System - CSV Import Script
Bu script CSV dosyalarını PostgreSQL veritabanına aktarır
"""

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
import os
import re
from datetime import datetime
import logging

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Database connection
DB_CONNECTION = "postgresql://postgres:masterkey@localhost:5432/b2b_rag_system"

def clean_decimal_string(value):
    """Türkçe sayı formatını temizle (örn: '8,258.90' -> 8258.90)"""
    if pd.isna(value) or value == '' or str(value).strip() == '':
        return None
    
    # String'e çevir ve temizle
    str_val = str(value).strip()
    
    # Çok karmaşık string'leri (birden fazla sayı içeren) reddet
    if str_val.count(',') > 2 or str_val.count('.') > 2:
        logger.warning(f"Karmaşık sayı formatı atlanıyor: {value}")
        return None
    
    # Boşluk ve diğer karakterleri temizle
    str_val = re.sub(r'[^\d.,-]', '', str_val)
    
    # Basit durum: sadece rakam
    if str_val.replace('.', '').replace(',', '').replace('-', '').isdigit():
        if ',' in str_val and '.' not in str_val:
            # Sadece virgül var - son 2-3 hane ondalık kısım olabilir
            parts = str_val.split(',')
            if len(parts) == 2 and len(parts[1]) <= 2:
                str_val = parts[0] + '.' + parts[1]
            else:
                # Binlik ayırıcı olarak kullanılmış
                str_val = str_val.replace(',', '')
        elif '.' in str_val and ',' not in str_val:
            # Sadece nokta var - ondalık ayırıcı
            pass
        elif ',' in str_val and '.' in str_val:
            # İkisi de var - son olan ondalık ayırıcı
            last_comma = str_val.rfind(',')
            last_dot = str_val.rfind('.')
            
            if last_comma > last_dot:
                # Virgül son - Türkçe format (1.234,56)
                str_val = str_val.replace('.', '').replace(',', '.')
            else:
                # Nokta son - İngilizce format (1,234.56)
                str_val = str_val.replace(',', '')
    
    # Son temizlik
    str_val = re.sub(r'[^\d.-]', '', str_val)
    
    try:
        result = float(str_val) if str_val else None
        # Çok büyük sayıları sınırla (PostgreSQL DECIMAL(15,2) limiti)
        if result and abs(result) > 9999999999999.99:
            logger.warning(f"Çok büyük sayı sınırlanıyor: {result}")
            return 9999999999999.99 if result > 0 else -9999999999999.99
        return result
    except ValueError:
        logger.warning(f"Sayı dönüşümü başarısız: {value} -> {str_val}")
        return None

def clean_text(text):
    """Metni temizle ve normalize et"""
    if pd.isna(text):
        return None
    return str(text).strip().replace('\x00', '')

def extract_product_keywords(description):
    """Ürün açıklamasından anahtar kelimeleri çıkar"""
    if pd.isna(description):
        return None
    
    desc = str(description).upper()
    keywords = []
    
    # Boyut bilgileri
    size_patterns = [
        r'\b(\d+[./]\d+)\b',  # 1/2, 1/4 gibi
        r'\b(\d+)\s*MM\b',    # mm ölçüleri
        r'\b(\d+)\s*CM\b',    # cm ölçüleri
        r'\b(\d+)\s*İNCH\b',  # inch ölçüleri
        r'\b(\d+[LÜK]+)\b',   # 100lük gibi
    ]
    
    for pattern in size_patterns:
        matches = re.findall(pattern, desc)
        keywords.extend(matches)
    
    # Ürün tipleri
    product_types = ['FİLTRE', 'SİLİNDİR', 'VALF', 'PISTON', 'CONTA', 'RULMAN', 
                    'KAYIŞ', 'ZİNCİR', 'MOTOR', 'POMPA', 'HORTUM', 'BORU']
    
    for ptype in product_types:
        if ptype in desc:
            keywords.append(ptype)
    
    return ' '.join(keywords) if keywords else None

def guess_category_from_description(description):
    """Açıklamadan kategori tahmin et"""
    if pd.isna(description):
        return 1  # Genel
    
    desc = str(description).upper()
    
    if 'FİLTRE' in desc:
        return 2  # Filtre
    elif any(word in desc for word in ['ELEKTRİK', 'MOTOR', 'SENSÖR', 'KABLO']):
        return 3  # Elektronik
    elif 'SİLİNDİR' in desc:
        return 5  # Silindir  
    elif any(word in desc for word in ['VALF', 'VANA']):
        return 6  # Valf
    elif any(word in desc for word in ['PISTON', 'RULMAN', 'KAYIŞ', 'ZİNCİR']):
        return 4  # Makine Parçaları
    else:
        return 1  # Genel

def import_sales_data():
    """Satış verilerini import et (İHSAN KOCAK 002.csv)"""
    logger.info("Satış verileri import ediliyor...")
    
    # CSV'yi oku
    files = [f for f in os.listdir('.') if f.endswith('.csv')]
    sales_file = None
    
    for file in files:
        if '002' in file:  # Satış verisi dosyası
            sales_file = file
            break
    
    if not sales_file:
        logger.error("Satış verisi dosyası bulunamadı")
        return
        
    logger.info(f"Satış dosyası okunuyor: {sales_file}")
    df_sales = pd.read_csv(sales_file, encoding='utf-8-sig')
    
    conn = psycopg2.connect(DB_CONNECTION)
    cur = conn.cursor()
    
    try:
        # Brands tablosunu doldur
        brands = df_sales['Marka'].dropna().unique()
        brand_data = [(brand,) for brand in brands if str(brand).strip()]
        
        if brand_data:
            cur.execute("DELETE FROM brands")  # Temizle
            execute_values(cur, 
                          "INSERT INTO brands (brand_name) VALUES %s ON CONFLICT (brand_name) DO NOTHING", 
                          brand_data)
            logger.info(f"{len(brand_data)} marka eklendi")
        
        # Brand ID mapping
        cur.execute("SELECT id, brand_name FROM brands")
        brand_map = {name: id for id, name in cur.fetchall()}
        
        # Customer ekle (tek müşteri - KOÇAK)
        customer_data = (
            '102892',  # customer_code
            'İHSAN KOÇAK MAKİNA SAN.VE TİC. A.Ş.',  # company_name
            'TR',  # country_code
            6,  # customer_group
        )
        
        cur.execute("""
            INSERT INTO customers (customer_code, company_name, country_code, customer_group) 
            VALUES (%s, %s, %s, %s) 
            ON CONFLICT (customer_code) DO NOTHING
        """, customer_data)
        
        # Customer ID al
        cur.execute("SELECT id FROM customers WHERE customer_code = %s", ('102892',))
        customer_id = cur.fetchone()[0]
        logger.info(f"Müşteri ID: {customer_id}")
        
        # Products tablosunu doldur
        products_data = []
        product_codes = df_sales['Malzeme'].dropna().unique()
        
        for _, row in df_sales.drop_duplicates('Malzeme').iterrows():
            if pd.notna(row['Malzeme']):
                brand_id = brand_map.get(row['Marka']) if pd.notna(row['Marka']) else None
                category_id = guess_category_from_description(row['Malzeme Adı'])
                keywords = extract_product_keywords(row['Malzeme Adı'])
                
                product_data = (
                    clean_text(row['Malzeme']),  # malzeme_kodu
                    clean_text(row['Malzeme Adı']),  # malzeme_adi
                    clean_text(row['Malzeme Satınalma Açıklaması']),  # satinalma_aciklamasi
                    category_id,  # category_id
                    brand_id,  # brand_id
                    clean_text(row['Malzeme Tipi']),  # malzeme_tipi
                    clean_text(row['Mlz.Grb.']),  # malzeme_grubu
                    keywords,  # search_keywords
                    clean_text(row['Malzeme Adı']),  # normalized_description
                    clean_text(row['Miktar Br.']),  # unit
                )
                products_data.append(product_data)
        
        if products_data:
            execute_values(cur, """
                INSERT INTO products (malzeme_kodu, malzeme_adi, satinalma_aciklamasi, 
                                    category_id, brand_id, malzeme_tipi, malzeme_grubu,
                                    search_keywords, normalized_description, unit)
                VALUES %s ON CONFLICT (malzeme_kodu) DO NOTHING
            """, products_data)
            logger.info(f"{len(products_data)} ürün eklendi")
        
        # Product ID mapping
        cur.execute("SELECT id, malzeme_kodu FROM products")
        product_map = {code: id for id, code in cur.fetchall()}
        
        # Orders ve Order Items
        orders_data = []
        order_items_data = []
        
        # Benzersiz siparişleri grupla
        order_groups = df_sales.groupby('Belge Numarası')
        
        for belge_no, group in order_groups:
            # Order kaydı
            first_row = group.iloc[0]
            
            order_data = (
                clean_text(belge_no),  # belge_numarasi
                clean_text(first_row['Belge Tipi']),  # belge_tipi
                customer_id,  # customer_id
                pd.to_datetime(first_row['Belge Tarihi']).date(),  # belge_tarihi
                clean_text(first_row['İş Alanı']),  # is_alani
                clean_text(first_row['Satış Departmanı']),  # sales_department
                clean_decimal_string(group['Ciro Tutarı'].sum()),  # total_ciro
                clean_decimal_string(group['Net Ciro'].sum()),  # total_net_ciro
            )
            orders_data.append(order_data)
            
            # Order items
            for _, item_row in group.iterrows():
                product_id = product_map.get(item_row['Malzeme'])
                if product_id:
                    item_data = (
                        clean_text(belge_no),  # order için belge_numarasi (foreign key sonra çözülecek)
                        clean_text(item_row['KalemNo']),  # kalem_no
                        product_id,  # product_id
                        clean_decimal_string(item_row['Miktar']),  # miktar
                        clean_text(item_row['Miktar Br.']),  # birim
                        clean_decimal_string(item_row['Stok Fiyatı']),  # birim_fiyat
                        clean_decimal_string(item_row['Ciro Tutarı']),  # ciro_tutari
                        clean_decimal_string(item_row['Net Ciro']),  # net_ciro
                        clean_decimal_string(item_row['Stok Fiyatı']),  # stok_fiyati
                        clean_decimal_string(item_row['Ek Maliyetler']),  # ek_maliyetler
                        clean_decimal_string(item_row['İndirim/Artırım']),  # indirim_artirim
                        clean_decimal_string(item_row[' Fiyat Farkı']),  # fiyat_farki
                        clean_decimal_string(item_row['Kar-Zarar']),  # kar_zarar
                        clean_decimal_string(item_row['İade Stok Fiyatı']),  # iade_stok_fiyati
                        clean_decimal_string(item_row['Değer İade']),  # deger_iade
                        clean_decimal_string(item_row['Miktar İade']),  # miktar_iade
                        clean_decimal_string(item_row['Oran%']),  # profit_margin_percent
                    )
                    order_items_data.append(item_data)
        
        # Orders insert
        if orders_data:
            execute_values(cur, """
                INSERT INTO orders (belge_numarasi, belge_tipi, customer_id, belge_tarihi,
                                  is_alani, sales_department, total_ciro, total_net_ciro)
                VALUES %s ON CONFLICT (belge_numarasi) DO NOTHING
            """, orders_data)
            logger.info(f"{len(orders_data)} sipariş eklendi")
        
        # Order ID mapping
        cur.execute("SELECT id, belge_numarasi FROM orders")
        order_map = {belge_no: id for id, belge_no in cur.fetchall()}
        
        # Order items - belge_numarası'nı order_id'ye çevir
        final_order_items = []
        for item in order_items_data:
            belge_no = item[0]
            order_id = order_map.get(belge_no)
            if order_id:
                # İlk elemanı (belge_no) order_id ile değiştir
                final_item = (order_id,) + item[1:]
                final_order_items.append(final_item)
        
        if final_order_items:
            execute_values(cur, """
                INSERT INTO order_items (order_id, kalem_no, product_id, miktar, birim, 
                                       birim_fiyat, ciro_tutari, net_ciro, stok_fiyati,
                                       ek_maliyetler, indirim_artirim, fiyat_farki, kar_zarar,
                                       iade_stok_fiyati, deger_iade, miktar_iade, profit_margin_percent)
                VALUES %s
            """, final_order_items)
            logger.info(f"{len(final_order_items)} sipariş kalemi eklendi")
        
        conn.commit()
        logger.info("Satış verileri başarıyla import edildi")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Satış verisi import hatası: {e}")
        raise
    finally:
        cur.close()
        conn.close()

def import_inventory_data():
    """Stok verilerini import et (İHSAN KOCAK 003.csv)"""
    logger.info("Stok verileri import ediliyor...")
    
    # Stok dosyasını bul
    files = [f for f in os.listdir('.') if f.endswith('.csv')]
    inventory_file = None
    
    for file in files:
        if '003' in file:  # Stok verisi dosyası
            inventory_file = file
            break
    
    if not inventory_file:
        logger.error("Stok verisi dosyası bulunamadı")
        return
        
    logger.info(f"Stok dosyası okunuyor: {inventory_file}")
    df_inventory = pd.read_csv(inventory_file, encoding='utf-8-sig')
    
    conn = psycopg2.connect(DB_CONNECTION)
    cur = conn.cursor()
    
    try:
        # Warehouse ID al (MERKEZ depo)
        cur.execute("SELECT id FROM warehouses WHERE warehouse_code = 'MERKEZ'")
        warehouse_id = cur.fetchone()[0]
        
        # Yeni ürünleri ekle (satış verisinde olmayan ürünler)
        new_products_data = []
        existing_products = set()
        
        cur.execute("SELECT malzeme_kodu FROM products")
        existing_products = {row[0] for row in cur.fetchall()}
        
        new_brands = set()
        for _, row in df_inventory.iterrows():
            if pd.notna(row['Malzeme']) and row['Malzeme'] not in existing_products:
                brand = clean_text(row['Marka'])
                if brand:
                    new_brands.add(brand)
                
                category_id = guess_category_from_description(row['Malzeme Açıklaması'])
                keywords = extract_product_keywords(row['Malzeme Açıklaması'])
                
                product_data = (
                    clean_text(row['Malzeme']),  # malzeme_kodu
                    clean_text(row['Malzeme Açıklaması']),  # malzeme_adi
                    clean_text(row['Satınalma Açık.']),  # satinalma_aciklamasi
                    category_id,  # category_id
                    None,  # brand_id (sonra update edilecek)
                    None,  # malzeme_tipi
                    None,  # malzeme_grubu
                    keywords,  # search_keywords
                    clean_text(row['Malzeme Açıklaması']),  # normalized_description
                    'AD',  # unit
                )
                new_products_data.append(product_data)
        
        # Yeni markaları ekle
        if new_brands:
            brand_data = [(brand,) for brand in new_brands]
            execute_values(cur, 
                          "INSERT INTO brands (brand_name) VALUES %s ON CONFLICT (brand_name) DO NOTHING", 
                          brand_data)
            logger.info(f"{len(new_brands)} yeni marka eklendi")
        
        # Yeni ürünleri ekle
        if new_products_data:
            execute_values(cur, """
                INSERT INTO products (malzeme_kodu, malzeme_adi, satinalma_aciklamasi, 
                                    category_id, brand_id, malzeme_tipi, malzeme_grubu,
                                    search_keywords, normalized_description, unit)
                VALUES %s ON CONFLICT (malzeme_kodu) DO NOTHING
            """, new_products_data)
            logger.info(f"{len(new_products_data)} yeni ürün eklendi")
        
        # Brand ID mapping güncelle
        cur.execute("SELECT id, brand_name FROM brands")
        brand_map = {name: id for id, name in cur.fetchall()}
        
        # Ürünlerin brand_id'lerini güncelle
        for _, row in df_inventory.iterrows():
            if pd.notna(row['Malzeme']) and pd.notna(row['Marka']):
                brand_id = brand_map.get(clean_text(row['Marka']))
                if brand_id:
                    cur.execute("""
                        UPDATE products SET brand_id = %s 
                        WHERE malzeme_kodu = %s AND brand_id IS NULL
                    """, (brand_id, clean_text(row['Malzeme'])))
        
        # Product ID mapping
        cur.execute("SELECT id, malzeme_kodu FROM products")
        product_map = {code: id for id, code in cur.fetchall()}
        
        # Inventory records
        inventory_data = []
        for _, row in df_inventory.iterrows():
            product_id = product_map.get(row['Malzeme'])
            if product_id:
                inventory_record = (
                    product_id,  # product_id
                    warehouse_id,  # warehouse_id
                    clean_decimal_string(row['Dönem Başı Miktar']),  # donem_basi_miktar
                    clean_decimal_string(row['Dönem Başı Tutar']),  # donem_basi_tutar
                    clean_decimal_string(row['Dönem Sonu Miktar']),  # donem_sonu_miktar
                    clean_decimal_string(row['Dönem Sonu Tutar']),  # donem_sonu_tutar
                    clean_decimal_string(row['Dönem Sonu Miktar']),  # current_stock
                    clean_decimal_string(row['Dönem Sonu Tutar']),  # current_value
                )
                inventory_data.append(inventory_record)
        
        if inventory_data:
            execute_values(cur, """
                INSERT INTO inventory (product_id, warehouse_id, donem_basi_miktar, donem_basi_tutar,
                                     donem_sonu_miktar, donem_sonu_tutar, current_stock, current_value)
                VALUES %s ON CONFLICT (product_id, warehouse_id) 
                DO UPDATE SET 
                    donem_basi_miktar = EXCLUDED.donem_basi_miktar,
                    donem_basi_tutar = EXCLUDED.donem_basi_tutar,
                    donem_sonu_miktar = EXCLUDED.donem_sonu_miktar,
                    donem_sonu_tutar = EXCLUDED.donem_sonu_tutar,
                    current_stock = EXCLUDED.current_stock,
                    current_value = EXCLUDED.current_value,
                    last_updated = CURRENT_TIMESTAMP
            """, inventory_data)
            logger.info(f"{len(inventory_data)} stok kaydı eklendi")
        
        conn.commit()
        logger.info("Stok verileri başarıyla import edildi")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Stok verisi import hatası: {e}")
        raise
    finally:
        cur.close()
        conn.close()

def verify_import():
    """Import sonuçlarını kontrol et"""
    logger.info("Import sonuçları kontrol ediliyor...")
    
    conn = psycopg2.connect(DB_CONNECTION)
    cur = conn.cursor()
    
    try:
        # Tablo sayıları
        tables = ['customers', 'brands', 'products', 'orders', 'order_items', 'inventory']
        
        for table in tables:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            logger.info(f"{table}: {count} kayıt")
        
        # Örnek veriler
        logger.info("\n=== ÖRNEK VERİLER ===")
        
        # En çok satılan ürünler
        cur.execute("""
            SELECT p.malzeme_adi, SUM(oi.miktar) as total_miktar, COUNT(*) as siparis_sayisi
            FROM products p
            JOIN order_items oi ON p.id = oi.product_id
            GROUP BY p.id, p.malzeme_adi
            ORDER BY total_miktar DESC
            LIMIT 5
        """)
        
        logger.info("En çok satılan ürünler:")
        for row in cur.fetchall():
            logger.info(f"  - {row[0]}: {row[1]} adet, {row[2]} sipariş")
        
        # Stok durumu örnekleri  
        cur.execute("""
            SELECT p.malzeme_adi, i.current_stock, i.current_value
            FROM products p
            JOIN inventory i ON p.id = i.product_id
            WHERE i.current_stock > 0
            ORDER BY i.current_stock DESC
            LIMIT 5
        """)
        
        logger.info("\nEn yüksek stoklu ürünler:")
        for row in cur.fetchall():
            logger.info(f"  - {row[0]}: {row[1]} adet, {row[2]:.2f} TL" if row[2] else f"  - {row[0]}: {row[1]} adet")
            
    except Exception as e:
        logger.error(f"Kontrol hatası: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    logger.info("=== B2B RAG System CSV Import Başlıyor ===")
    
    try:
        # 1. Satış verilerini import et
        import_sales_data()
        
        # 2. Stok verilerini import et  
        import_inventory_data()
        
        # 3. Sonuçları kontrol et
        verify_import()
        
        logger.info("=== Import işlemi başarıyla tamamlandı ===")
        
    except Exception as e:
        logger.error(f"Import işlemi başarısız: {e}")
        exit(1)
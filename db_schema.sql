-- B2B RAG System - PostgreSQL Database Schema
-- Orta Seviye: B2B ihtiyaçları + Esnek kategorizasyon

-- Companies/Customers table
CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    customer_code VARCHAR(50) UNIQUE,
    company_name VARCHAR(255) NOT NULL,
    country_code VARCHAR(10) DEFAULT 'TR',
    customer_group INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Product Categories (başta basit, sonra AI ile gelişir)
CREATE TABLE product_categories (
    id SERIAL PRIMARY KEY,
    category_name VARCHAR(100) NOT NULL,
    parent_category_id INTEGER REFERENCES product_categories(id),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Brands
CREATE TABLE brands (
    id SERIAL PRIMARY KEY,
    brand_name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT
);

-- Warehouses/Depots
CREATE TABLE warehouses (
    id SERIAL PRIMARY KEY,
    warehouse_code VARCHAR(50) UNIQUE,
    warehouse_name VARCHAR(100) NOT NULL,
    location VARCHAR(255)
);

-- Products/Materials (esnek yapı)
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    malzeme_kodu VARCHAR(50) UNIQUE NOT NULL,
    malzeme_adi VARCHAR(500) NOT NULL,
    satinalma_aciklamasi VARCHAR(100),
    category_id INTEGER REFERENCES product_categories(id),
    brand_id INTEGER REFERENCES brands(id),
    malzeme_tipi VARCHAR(50),
    malzeme_grubu VARCHAR(50),
    
    -- AI için arama alanları
    search_keywords TEXT, -- AI tarafından oluşturulacak
    normalized_description TEXT, -- Temizlenmiş açıklama
    
    unit VARCHAR(10) DEFAULT 'AD',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Orders/Documents
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    belge_numarasi VARCHAR(50) UNIQUE,
    belge_tipi VARCHAR(10),
    customer_id INTEGER REFERENCES customers(id),
    belge_tarihi DATE,
    is_alani VARCHAR(50),
    sales_department VARCHAR(100),
    
    -- Toplam tutarlar
    total_ciro DECIMAL(15,2),
    total_net_ciro DECIMAL(15,2),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Order Items/Details
CREATE TABLE order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id),
    kalem_no INTEGER,
    product_id INTEGER REFERENCES products(id),
    
    -- Miktar ve fiyat
    miktar DECIMAL(10,3),
    birim VARCHAR(10),
    birim_fiyat DECIMAL(15,4),
    
    -- Tutar hesaplamaları
    ciro_tutari DECIMAL(15,2),
    net_ciro DECIMAL(15,2),
    stok_fiyati DECIMAL(15,2),
    ek_maliyetler DECIMAL(15,2) DEFAULT 0,
    indirim_artirim DECIMAL(15,2) DEFAULT 0,
    fiyat_farki DECIMAL(15,2) DEFAULT 0,
    kar_zarar DECIMAL(15,2),
    
    -- İade bilgileri
    iade_stok_fiyati DECIMAL(15,2) DEFAULT 0,
    deger_iade DECIMAL(15,2) DEFAULT 0,
    miktar_iade DECIMAL(10,3) DEFAULT 0,
    
    profit_margin_percent DECIMAL(8,2),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Current Inventory Status
CREATE TABLE inventory (
    id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(id),
    warehouse_id INTEGER REFERENCES warehouses(id),
    
    -- Dönem bilgileri
    donem_basi_miktar DECIMAL(10,3) DEFAULT 0,
    donem_basi_tutar DECIMAL(15,2) DEFAULT 0,
    donem_sonu_miktar DECIMAL(10,3) DEFAULT 0,
    donem_sonu_tutar DECIMAL(15,2) DEFAULT 0,
    
    -- Mevcut stok
    current_stock DECIMAL(10,3) DEFAULT 0,
    current_value DECIMAL(15,2) DEFAULT 0,
    
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(product_id, warehouse_id)
);

-- Stock Movements (giriş/çıkış hareketleri)
CREATE TABLE stock_movements (
    id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(id),
    warehouse_id INTEGER REFERENCES warehouses(id),
    
    movement_type VARCHAR(10) CHECK (movement_type IN ('GIRIS', 'CIKIS')),
    movement_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    quantity DECIMAL(10,3),
    unit_cost DECIMAL(15,4),
    total_value DECIMAL(15,2),
    
    reference_document VARCHAR(100), -- Hangi belgeye bağlı
    notes TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- RAG için özel tablo - AI queries ve sonuçları
CREATE TABLE ai_query_patterns (
    id SERIAL PRIMARY KEY,
    query_text TEXT NOT NULL,
    query_type VARCHAR(50), -- 'product_search', 'customer_history', 'stock_check'
    sql_template TEXT,
    parameters JSONB,
    success_count INTEGER DEFAULT 0,
    last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_products_malzeme_kodu ON products(malzeme_kodu);
CREATE INDEX idx_products_search ON products USING GIN(to_tsvector('turkish', malzeme_adi || ' ' || COALESCE(search_keywords, '')));
CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_orders_date ON orders(belge_tarihi);
CREATE INDEX idx_order_items_product ON order_items(product_id);
CREATE INDEX idx_inventory_product_warehouse ON inventory(product_id, warehouse_id);

-- Insert initial categories
INSERT INTO product_categories (category_name, description) VALUES
('Genel', 'Genel kategori - henüz sınıflandırılmamış'),
('Filtre', 'Filtre ürünleri'),
('Elektronik', 'Elektronik komponentler'),
('Makine Parçaları', 'Makine yedek parçaları'),
('Silindir', 'Silindir ürünleri'),
('Valf', 'Valf ve vanalar');

-- Insert initial warehouse
INSERT INTO warehouses (warehouse_code, warehouse_name, location) VALUES
('MERKEZ', 'Merkez Depo', 'Ana Depo');

-- Sample view for AI queries
CREATE VIEW v_product_search AS
SELECT 
    p.id,
    p.malzeme_kodu,
    p.malzeme_adi,
    p.satinalma_aciklamasi,
    pc.category_name,
    b.brand_name,
    i.current_stock,
    i.current_value,
    w.warehouse_name
FROM products p
LEFT JOIN product_categories pc ON p.category_id = pc.id  
LEFT JOIN brands b ON p.brand_id = b.id
LEFT JOIN inventory i ON p.id = i.product_id
LEFT JOIN warehouses w ON i.warehouse_id = w.id;

-- View for customer purchase history
CREATE VIEW v_customer_purchases AS
SELECT 
    c.company_name,
    p.malzeme_kodu,
    p.malzeme_adi,
    oi.miktar,
    oi.ciro_tutari,
    o.belge_tarihi,
    o.belge_numarasi
FROM customers c
JOIN orders o ON c.id = o.customer_id
JOIN order_items oi ON o.id = oi.order_id  
JOIN products p ON oi.product_id = p.id
ORDER BY o.belge_tarihi DESC;
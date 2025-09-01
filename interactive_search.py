#!/usr/bin/env python3
"""
Interactive B2B RAG Search CLI
Gerçek zamanlı ürün arama ve test ortamı
"""

import os
import sys
import time
import psycopg2
from psycopg2.extras import RealDictCursor
import chromadb
from dotenv import load_dotenv
import requests
from typing import List, Dict, Optional

# UTF-8 encoding fix for Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

# Configuration
DB_CONNECTION = "postgresql://postgres:masterkey@localhost:5432/b2b_rag_system"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL_NAME = os.getenv("MODEL", "openai/gpt-3.5-turbo")

class InteractiveRAGSearch:
    """Interactive RAG arama sistemi"""
    
    def __init__(self):
        print("B2B RAG Arama Sistemi yuklenyor...")
        
        # ChromaDB connection
        try:
            self.chroma_client = chromadb.PersistentClient(
                path=os.path.join(os.getcwd(), "chroma_db")
            )
            self.collection = self.chroma_client.get_collection("b2b_products")
            print(f"✓ ChromaDB yuklendi: {self.collection.count()} dokuman")
        except Exception as e:
            print(f"✗ ChromaDB hatasi: {e}")
            print("Lutfen once 'python rag_enhanced.py' calistirin")
            sys.exit(1)
        
        # PostgreSQL connection
        try:
            self.db = psycopg2.connect(DB_CONNECTION)
            print("✓ PostgreSQL baglantisi kuruldu")
        except Exception as e:
            print(f"✗ PostgreSQL hatasi: {e}")
            sys.exit(1)
        
        # API key check
        if not OPENROUTER_API_KEY:
            print("✗ OpenRouter API key bulunamadi (.env dosyasini kontrol edin)")
            sys.exit(1)
        else:
            print("✓ OpenRouter API hazir")
        
        print("\n" + "="*60)
        print("RAG SISTEM HAZIR!")
        print("="*60)
    
    def search_products(self, query: str, limit: int = 10) -> List[Dict]:
        """RAG ile ürün ara"""
        try:
            start_time = time.time()
            
            # Vector search
            results = self.collection.query(
                query_texts=[query],
                n_results=limit,
                where={"stock": {"$gte": 0.1}}  # Stokta olanlar
            )
            
            products = []
            if results['documents'] and results['documents'][0]:
                for i, doc in enumerate(results['documents'][0]):
                    metadata = results['metadatas'][0][i]
                    
                    # Parse product info
                    product_name = doc.split('\n')[0].replace('ÜRÜN: ', '')
                    similarity_score = 1 - results['distances'][0][i]
                    
                    products.append({
                        'id': metadata['product_id'],
                        'malzeme_kodu': metadata['malzeme_kodu'], 
                        'malzeme_adi': product_name,
                        'brand_name': metadata['brand'],
                        'current_stock': metadata['stock'],
                        'category_name': metadata['category'],
                        'similarity_score': similarity_score,
                        'full_content': doc
                    })
            
            search_time = time.time() - start_time
            
            return products, search_time
            
        except Exception as e:
            print(f"Arama hatasi: {e}")
            return [], 0
    
    def get_product_details(self, product_id: int) -> Optional[Dict]:
        """Ürün detaylarını getir"""
        try:
            with self.db.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        p.id, p.malzeme_kodu, p.malzeme_adi,
                        COALESCE(b.brand_name, 'Bilinmeyen') as brand_name,
                        COALESCE(i.current_stock, 0) as current_stock,
                        COALESCE(pc.category_name, 'Genel') as category_name,
                        COALESCE(p.search_keywords, '') as search_keywords
                    FROM products p
                    LEFT JOIN brands b ON p.brand_id = b.id
                    LEFT JOIN inventory i ON p.id = i.product_id
                    LEFT JOIN product_categories pc ON p.category_id = pc.id
                    WHERE p.id = %s
                """, (product_id,))
                
                row = cur.fetchone()
                return dict(row) if row else None
                
        except Exception as e:
            print(f"Detay hatasi: {e}")
            return None
    
    def generate_ai_response(self, query: str, products: List[Dict]) -> str:
        """AI yanıt oluştur"""
        if not products:
            return "Aradiginiz kriterlerde urun bulunamadi. Farkli anahtar kelimeler deneyebilirsiniz."
        
        # Context hazırla
        context = "MEVCUT URUNLER:\n\n"
        for i, product in enumerate(products[:3], 1):
            context += f"{i}. URUN: {product['malzeme_adi']}\n"
            context += f"   MARKA: {product['brand_name']}\n"
            context += f"   KOD: {product['malzeme_kodu']}\n"
            context += f"   STOK: {product['current_stock']:.0f} adet\n"
            context += f"   BENZERLIK: {product['similarity_score']:.2f}\n\n"
        
        # AI prompt
        messages = [
            {
                "role": "system",
                "content": """Sen B2B endustriyel urun uzmanısın. Musteri sorularına teknik bilgiyle cevap ver.

Gorevlerin:
1. En uygun urunu belirle ve one
2. Teknik ozellikleri acikla  
3. Stok durumunu belirt
4. Alternatif onerilerde bulun
5. Professional ama samimi dilde yanitla
6. Turkce karakterler kullanma (encoding sorunu)"""
            },
            {
                "role": "user",
                "content": f"MUSTERI TALEBI: {query}\n\n{context}\n\nYukaridaki urunler arasinden en uygun olani oner ve nedenini acikla."
            }
        ]
        
        try:
            headers = {
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            }
            
            data = {
                "model": MODEL_NAME,
                "messages": messages,
                "temperature": 0.4,
                "max_tokens": 400
            }
            
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=15
            )
            
            if response.status_code == 200:
                return response.json()['choices'][0]['message']['content']
            else:
                return f"AI hata kodu: {response.status_code}"
                
        except Exception as e:
            return f"AI baglanti hatasi: {e}"
    
    def show_help(self):
        """Yardım menüsü"""
        print("\n" + "="*60)
        print("KOMUTLAR:")
        print("="*60)
        print("help       - Bu yardim menusunu goster")
        print("search     - Normal arama modu")
        print("detail <id> - Urun detaylarini goster") 
        print("stats      - Sistem istatistikleri")
        print("examples   - Ornek sorgu listesi")
        print("quit       - Cikis")
        print("="*60)
    
    def show_examples(self):
        """Örnek sorgular"""
        print("\n" + "="*60)
        print("ORNEK SORGULAR:")
        print("="*60)
        
        examples = [
            "silindir ariyorum",
            "100mm silindir", 
            "yastiklamali silindir lazim",
            "manyetik sensorlu silindir",
            "MAG marka filtre",
            "hava filtresine ihtiyacim var",
            "akis kontrol valfi ariyorum",
            "yuksek basinca dayanalikli urun",
            "sessiz calisan silindir",
            "yag direncli, 100mm silindir"
        ]
        
        for i, example in enumerate(examples, 1):
            print(f"{i:2d}. {example}")
        
        print("="*60)
        print("Orneklerden birini kopyalayip kullanabilirsiniz!")
    
    def show_stats(self):
        """Sistem istatistikleri"""
        print("\n" + "="*60)
        print("SISTEM ISTATISTIKLERI:")
        print("="*60)
        
        # ChromaDB stats
        doc_count = self.collection.count()
        print(f"ChromaDB Dokuman Sayisi: {doc_count:,}")
        
        # PostgreSQL stats
        try:
            with self.db.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM products")
                product_count = cur.fetchone()[0]
                
                cur.execute("SELECT COUNT(*) FROM products p JOIN inventory i ON p.id = i.product_id WHERE i.current_stock > 0")
                in_stock_count = cur.fetchone()[0]
                
                cur.execute("SELECT COUNT(DISTINCT brand_id) FROM products WHERE brand_id IS NOT NULL")
                brand_count = cur.fetchone()[0]
                
                print(f"Toplam Urun Sayisi: {product_count:,}")
                print(f"Stokta Urun Sayisi: {in_stock_count:,}")
                print(f"Marka Sayisi: {brand_count:,}")
                
        except Exception as e:
            print(f"Veritabani stats hatasi: {e}")
        
        print(f"AI Model: {MODEL_NAME}")
        print("="*60)
    
    def search_mode(self):
        """Ana arama modu"""
        while True:
            print("\n" + "-"*60)
            query = input("ARAMA SORGUSU (veya 'back' ile ana menuye donus): ").strip()
            
            if query.lower() in ['back', 'geri']:
                return
            
            if not query:
                print("Lutfen bir arama sorgusu girin.")
                continue
            
            print(f"\nAraniyor: '{query}'...")
            
            # Arama yap
            products, search_time = self.search_products(query)
            
            if not products:
                print("Hic urun bulunamadi. Farkli kelimeler deneyin.")
                continue
            
            print(f"\n{len(products)} urun bulundu ({search_time:.3f} saniye)")
            print("="*60)
            
            # İlk 5 sonucu göster
            for i, product in enumerate(products[:5], 1):
                print(f"{i}. {product['malzeme_adi']}")
                print(f"   Marka: {product['brand_name']}")
                print(f"   Kod: {product['malzeme_kodu']}")
                print(f"   Stok: {product['current_stock']:.0f} adet")
                print(f"   Benzerlik: {product['similarity_score']:.3f}")
                print()
            
            # AI yanıt oluştur
            print("AI yanitini olusturuyor...")
            ai_response = self.generate_ai_response(query, products)
            
            print("\n" + "="*60)
            print("AI UZMANI:")
            print("="*60)
            print(ai_response)
            print("="*60)
            
            # Kullanıcı seçenekleri
            while True:
                choice = input("\nSecenekler: [d]etay, [y]eni arama, [m]enu: ").lower().strip()
                
                if choice == 'y':
                    break
                elif choice == 'm':
                    return
                elif choice == 'd':
                    try:
                        product_num = int(input("Hangi urun numarasi (1-5): ")) - 1
                        if 0 <= product_num < len(products[:5]):
                            product = products[product_num]
                            self.show_product_detail(product)
                        else:
                            print("Gecersiz numara")
                    except ValueError:
                        print("Lutfen gecerli bir numara girin")
                else:
                    print("Gecersiz secim. Lutfen d, y, veya m girin.")
    
    def show_product_detail(self, product: Dict):
        """Ürün detayını göster"""
        print("\n" + "="*60)
        print("URUN DETAYI:")
        print("="*60)
        
        # Veritabanından tam detayları getir
        full_detail = self.get_product_details(product['id'])
        
        if full_detail:
            print(f"Urun Adi: {full_detail['malzeme_adi']}")
            print(f"Malzeme Kodu: {full_detail['malzeme_kodu']}")
            print(f"Marka: {full_detail['brand_name']}")
            print(f"Kategori: {full_detail['category_name']}")
            print(f"Stok: {full_detail['current_stock']:.0f} adet")
            if full_detail['search_keywords']:
                print(f"Anahtar Kelimeler: {full_detail['search_keywords']}")
            
            print(f"\nBenzerlik Skoru: {product['similarity_score']:.3f}")
            
            # RAG document content
            if 'full_content' in product:
                print("\nRAG DOKUMAN ICERIGI:")
                print("-" * 40)
                print(product['full_content'][:500] + "..." if len(product['full_content']) > 500 else product['full_content'])
        
        print("="*60)
        input("Devam etmek icin Enter...")
    
    def run(self):
        """Ana CLI döngüsü"""
        print("\nB2B RAG ARAMA SISTEMI")
        print("Hosgeldiniz! 'help' yazarak komutlari gorebilirsiniz.\n")
        
        while True:
            try:
                command = input(">>> ").strip().lower()
                
                if command in ['quit', 'exit', 'cikis', 'q']:
                    print("Gorusmek uzere!")
                    break
                
                elif command == 'help':
                    self.show_help()
                
                elif command == 'search':
                    self.search_mode()
                
                elif command.startswith('detail '):
                    try:
                        product_id = int(command.split()[1])
                        detail = self.get_product_details(product_id)
                        if detail:
                            print("\n" + "="*60)
                            print("URUN DETAYI:")
                            print("="*60)
                            for key, value in detail.items():
                                print(f"{key}: {value}")
                        else:
                            print(f"ID {product_id} ile urun bulunamadi")
                    except (IndexError, ValueError):
                        print("Kullanim: detail <urun_id>")
                
                elif command == 'stats':
                    self.show_stats()
                
                elif command == 'examples':
                    self.show_examples()
                
                elif command == '':
                    continue
                
                else:
                    # Direkt arama yap
                    print(f"Araniyor: '{command}'...")
                    products, search_time = self.search_products(command)
                    
                    if products:
                        print(f"\n{len(products)} sonuc ({search_time:.3f}s):")
                        for i, p in enumerate(products[:3], 1):
                            print(f"{i}. {p['malzeme_adi']} ({p['brand_name']}) - {p['similarity_score']:.3f}")
                        
                        if len(products) > 3:
                            print(f"... ve {len(products)-3} daha")
                        
                        print("Daha detayli arama icin 'search' komutunu kullanin.")
                    else:
                        print("Sonuc bulunamadi")
            
            except KeyboardInterrupt:
                print("\n\nCikiliyor...")
                break
            except EOFError:
                print("\n\nInput stream kapandi. Cikiliyor...")
                break
            except Exception as e:
                print(f"Beklenmeyen hata: {e}")
                # Recursive loop'u engellemek için break
                break

def main():
    """Ana fonksiyon"""
    try:
        search_system = InteractiveRAGSearch()
        search_system.run()
    except KeyboardInterrupt:
        print("\n\nProgram sonlandirildi.")
    except Exception as e:
        print(f"Sistem hatasi: {e}")

if __name__ == "__main__":
    main()
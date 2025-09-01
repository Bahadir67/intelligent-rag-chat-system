#!/usr/bin/env python3
"""
Manuel Interactive Test - Kendi sorularınızı yazarak test edin
"""

import os
import sys
import time
import chromadb
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()
DB_CONNECTION = "postgresql://postgres:masterkey@localhost:5432/b2b_rag_system"

class ManualTester:
    """Manuel test sistemi"""
    
    def __init__(self):
        self.db = psycopg2.connect(DB_CONNECTION)
        print("B2B RAG Test Sistemi hazir!")
        print("Kendi sorularinizi yazarak test edebilirsiniz.\n")
    
    def process_query(self, query: str):
        """Query'yi işle ve yanıtla"""
        print(f"\n{'='*60}")
        print(f"SORU: {query}")
        print('='*60)
        
        # 1. Parse dimensions
        diameter, stroke = self._extract_dimensions(query)
        print(f"Algilanan boyutlar: Çap={diameter}mm, Strok={stroke}mm")
        
        # 2. Detect tone
        tone = self._detect_tone(query)
        print(f"Ton: {tone}")
        
        # 3. Progressive inquiry logic
        if diameter and not stroke:
            self._handle_missing_stroke(diameter, tone)
        elif stroke and not diameter:
            self._handle_missing_diameter(stroke, tone)
        elif diameter and stroke:
            self._handle_complete_info(diameter, stroke, tone)
        else:
            self._handle_no_info(tone)
    
    def _extract_dimensions(self, query):
        """Boyutları çıkar"""
        import re
        query_upper = query.upper()
        
        diameter = None
        stroke = None
        
        # Çap patterns
        cap_patterns = [
            r'(\d+)\s*(?:CAP|CAPLI|ÇAP|ÇAPLI|MM\s*CAP)',
            r'(\d+)\s*LUK',
            r'Ø(\d+)'
        ]
        
        for pattern in cap_patterns:
            matches = re.findall(pattern, query_upper)
            if matches:
                diameter = int(matches[0])
                break
        
        # Strok patterns
        strok_patterns = [
            r'(\d+)\s*(?:STROK|STROKLU|STROKE)',
            r'(\d+)\s*[*x×]\s*(\d+)'  # 100x200 format
        ]
        
        for pattern in strok_patterns:
            matches = re.findall(pattern, query_upper)
            if matches:
                if isinstance(matches[0], tuple):
                    stroke = int(matches[0][1])  # Second number in 100x200
                else:
                    stroke = int(matches[0])
                break
        
        return diameter, stroke
    
    def _detect_tone(self, query):
        """Ton tespit et"""
        friendly_words = ['canim', 'kardesim', 'dostum', 'arkadas']
        query_lower = query.lower()
        
        if any(word in query_lower for word in friendly_words):
            return "samimi"
        else:
            return "professional"
    
    def _handle_missing_stroke(self, diameter, tone):
        """Strok eksik - seçenekleri sun"""
        try:
            with self.db.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT p.malzeme_adi, i.current_stock
                    FROM products p 
                    JOIN inventory i ON p.id = i.product_id
                    WHERE p.malzeme_adi ILIKE %s AND i.current_stock > 0
                    ORDER BY i.current_stock DESC LIMIT 10
                """, (f'%{diameter}%',))
                
                results = cur.fetchall()
                stroke_options = {}
                
                import re
                for row in results:
                    name = row['malzeme_adi']
                    stock = row['current_stock']
                    
                    # Strok çıkar
                    stroke_patterns = [
                        rf'{diameter}[*x×](\d+)',
                        rf'{diameter}/(\d+)',
                        r'(\d+)\s*(?:STROK|STROKE)'
                    ]
                    
                    for pattern in stroke_patterns:
                        matches = re.findall(pattern, name.upper())
                        if matches:
                            stroke_val = int(matches[0])
                            key = f"{stroke_val}mm"
                            stroke_options[key] = stroke_options.get(key, 0) + stock
                            break
                
                if stroke_options:
                    total_stock = sum(stroke_options.values())
                    option_count = len(stroke_options)
                    
                    print(f"\nSISTEM YANITI:")
                    print("-" * 30)
                    
                    if tone == "samimi":
                        print(f"Hmm, {diameter}mm çapli silindir icin {option_count} strok secenegi var")
                        print(f"(toplam {total_stock:.0f} adet stokta).")
                        print("Strok uzunlugu der misin? Boylece sana en uygun urunu bulabilirim!")
                    else:
                        print(f"İyi bir arama icin {diameter}mm çapli silindir icin {option_count} strok secenegi var")
                        print(f"(toplam {total_stock:.0f} adet stokta).")
                        print("Hangi strok uzunlugunu tercih edersiniz? Belirtirseniz daha hassas sonuclar bulabilirim.")
                    
                    print(f"\nMEVCUT SEÇENEKLER:")
                    sorted_options = sorted(stroke_options.items(), key=lambda x: x[1], reverse=True)
                    for i, (stroke, count) in enumerate(sorted_options[:5], 1):
                        print(f"{i}. {stroke} strok: {count:.0f} adet stokta")
                
                else:
                    print(f"\nMaalesef {diameter}mm çapinda silindir bulunamadi.")
                    
        except Exception as e:
            print(f"Hata: {e}")
    
    def _handle_missing_diameter(self, stroke, tone):
        """Çap eksik - seçenekleri sun"""
        try:
            with self.db.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT p.malzeme_adi, i.current_stock
                    FROM products p
                    JOIN inventory i ON p.id = i.product_id  
                    WHERE p.malzeme_adi ILIKE %s AND i.current_stock > 0
                    ORDER BY i.current_stock DESC LIMIT 10
                """, (f'%{stroke}%',))
                
                results = cur.fetchall()
                diameter_options = {}
                
                import re
                for row in results:
                    name = row['malzeme_adi']
                    stock = row['current_stock']
                    
                    # Çap çıkar  
                    diameter_patterns = [
                        rf'(\d+)[*x×]{stroke}',
                        rf'(\d+)/{stroke}',
                        r'Ø(\d+)',
                        r'(\d+)\s*(?:ÇAP|CAPLI)'
                    ]
                    
                    for pattern in diameter_patterns:
                        matches = re.findall(pattern, name.upper())
                        if matches:
                            diameter_val = int(matches[0])
                            key = f"{diameter_val}mm"
                            diameter_options[key] = diameter_options.get(key, 0) + stock
                            break
                
                if diameter_options:
                    option_count = len(diameter_options)
                    
                    print(f"\nSISTEM YANITI:")
                    print("-" * 30)
                    
                    if tone == "samimi":
                        print(f"Tabii canim! {stroke}mm stroklu silindir icin {option_count} cap secenegi var.")
                        print("Cap der misin? En uygun urunu bulayim!")
                    else:
                        print(f"{stroke}mm stroklu silindir icin {option_count} cap secenegi bulunuyor.")
                        print("Hangi capi tercih edersiniz?")
                    
                    print(f"\nMEVCUT SEÇENEKLER:")
                    sorted_options = sorted(diameter_options.items(), key=lambda x: x[1], reverse=True)
                    for i, (diameter, count) in enumerate(sorted_options[:5], 1):
                        print(f"{i}. {diameter} cap: {count:.0f} adet stokta")
                
                else:
                    print(f"\nMaalesef {stroke}mm stroklu silindir bulunamadi.")
                    
        except Exception as e:
            print(f"Hata: {e}")
    
    def _handle_complete_info(self, diameter, stroke, tone):
        """Tam bilgi - ürün ara"""
        print(f"\nSISTEM YANITI:")
        print("-" * 30)
        
        if tone == "samimi":
            print(f"Super! {diameter}mm x {stroke}mm silindir ariyorsun.")
            print("Tam bilgiye sahipsin, hemen en uygun urunleri buluyorum!")
        else:
            print(f"Tam bilgiye sahipsiniz: {diameter}mm cap x {stroke}mm strok silindir.")
            print("Urun aramasi yapiliyor...")
        
        # Gerçek arama yap
        try:
            # ChromaDB'den ara
            chroma_client = chromadb.PersistentClient(
                path=os.path.join(os.getcwd(), "chroma_db")
            )
            collection = chroma_client.get_collection("b2b_products")
            
            search_query = f"{diameter}mm {stroke}mm silindir"
            results = collection.query(
                query_texts=[search_query],
                n_results=3,
                where={"stock": {"$gte": 0.1}}
            )
            
            if results['documents'] and results['documents'][0]:
                print(f"\n{len(results['documents'][0])} UYGUN URUN BULUNDU:")
                for i, doc in enumerate(results['documents'][0], 1):
                    metadata = results['metadatas'][0][i-1]
                    similarity = 1 - results['distances'][0][i-1]
                    product_name = doc.split('\n')[0].replace('ÜRÜN: ', '')
                    
                    print(f"\n{i}. {product_name}")
                    print(f"   Marka: {metadata['brand']}")
                    print(f"   Kod: {metadata['malzeme_kodu']}")
                    print(f"   Stok: {metadata['stock']:.0f} adet")
                    print(f"   Uygunluk: {similarity:.3f}")
            else:
                print("Bu boyutlarda urun bulunamadi.")
                
        except Exception as e:
            print(f"Arama hatasi: {e}")
    
    def _handle_no_info(self, tone):
        """Hiç bilgi yok - rehberlik et"""
        print(f"\nSISTEM YANITI:")
        print("-" * 30)
        
        if tone == "samimi":
            print("Tabii canim! Silindir ariyorsun ama boyut bilgisine ihtiyacim var.")
            print("Cap (orn: 100mm) ve strok (orn: 200mm) soylersen")
            print("sana en uygun urunleri bulabilirim!")
        else:
            print("Silindir aramaniz icin daha spesifik bilgiye ihtiyac var.")
            print("Cap (ornek: 100mm) ve strok uzunlugu (ornek: 200mm)")
            print("belirtirseniz size mevcut secenekleri sunabilirim.")
        
        print(f"\nORNEK SORGULAR:")
        print("- '100 cap silindir'")
        print("- '400 stroklu silindir'") 
        print("- '100 cap 200 strok silindir'")
        print("- 'manyetik sensorlu 100mm silindir'")
    
    def run(self):
        """Ana test döngüsü"""
        print("MANUEL INTERACTIVE TEST")
        print("=" * 40)
        print("Kendi sorularinizi yazin, sistem yanitlasin!")
        print("'quit' yazarak cikabilirsiniz.\n")
        
        while True:
            try:
                query = input("SORU > ").strip()
                
                if query.lower() in ['quit', 'exit', 'cikis', 'q']:
                    print("\nGorusmek uzere!")
                    break
                
                if not query:
                    print("Lutfen bir soru yazin.")
                    continue
                
                self.process_query(query)
                
            except EOFError:
                print("\n\nCikiliyor...")
                break
            except KeyboardInterrupt:
                print("\n\nCikiliyor...")
                break
            except Exception as e:
                print(f"Hata: {e}")

if __name__ == "__main__":
    tester = ManualTester()
    tester.run()
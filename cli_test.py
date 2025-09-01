#!/usr/bin/env python3
"""
CLI Test - Sorgu yaz, cevap gör
"""

import os
import sys
import chromadb
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()
DB_CONNECTION = "postgresql://postgres:masterkey@localhost:5432/b2b_rag_system"

def quick_answer(query: str):
    """Hızlı cevap ver"""
    print(f"\nSORU: {query}")
    print("=" * 50)
    
    # Parse
    import re
    query_upper = query.upper()
    
    diameter = None
    stroke = None
    
    # Çap
    cap_patterns = [r'(\d+)\s*(?:CAP|CAPLI|ÇAP|ÇAPLI|LUK)', r'Ø(\d+)']
    for pattern in cap_patterns:
        matches = re.findall(pattern, query_upper)
        if matches:
            diameter = int(matches[0])
            break
    
    # Strok
    strok_patterns = [r'(\d+)\s*(?:STROK|STROKLU)']
    for pattern in strok_patterns:
        matches = re.findall(pattern, query_upper)
        if matches:
            stroke = int(matches[0])
            break
    
    # Tone
    friendly = any(word in query.lower() for word in ['canim', 'kardesim', 'dostum'])
    
    print(f"Çap: {diameter or 'yok'}, Strok: {stroke or 'yok'}")
    
    try:
        db = psycopg2.connect(DB_CONNECTION)
        
        if diameter and not stroke:
            # Strok seçenekleri
            with db.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT p.malzeme_adi, i.current_stock
                    FROM products p JOIN inventory i ON p.id = i.product_id
                    WHERE p.malzeme_adi ILIKE %s AND i.current_stock > 0
                    ORDER BY i.current_stock DESC LIMIT 8
                """, (f'%{diameter}%',))
                
                results = cur.fetchall()
                strokes = {}
                
                for row in results:
                    name = row['malzeme_adi']
                    stock = row['current_stock']
                    
                    match = re.search(rf'{diameter}[*x×](\d+)', name.upper())
                    if match:
                        s = int(match.group(1))
                        strokes[s] = strokes.get(s, 0) + stock
                
                if strokes:
                    total = sum(strokes.values())
                    print(f"\nAI CEVAP:")
                    if friendly:
                        print(f"Hmm, {diameter}mm çaplı silindir için {len(strokes)} strok seçeneği var")
                        print(f"(toplam {total:.0f} adet). Strok der misin?")
                    else:
                        print(f"{diameter}mm çaplı silindir için {len(strokes)} strok seçeneği:")
                        print(f"(toplam {total:.0f} adet stokta)")
                    
                    print("\nSeçenekler:")
                    for stroke_val, count in sorted(strokes.items(), key=lambda x: x[1], reverse=True)[:4]:
                        print(f"  • {stroke_val}mm strok: {count:.0f} adet")
                else:
                    print(f"\n{diameter}mm çaplı silindir bulunamadı")
        
        elif stroke and not diameter:
            print(f"\nAI CEVAP:")
            if friendly:
                print(f"Canım, {stroke}mm strok için çap lazım!")
            else:
                print(f"{stroke}mm strok için çap belirtirseniz bulabilirim.")
        
        elif diameter and stroke:
            print(f"\nAI CEVAP:")
            print(f"Tam bilgi! {diameter}x{stroke}mm silindir aranıyor...")
            
            # ChromaDB search
            try:
                client = chromadb.PersistentClient(path="chroma_db")
                collection = client.get_collection("b2b_products")
                
                results = collection.query(
                    query_texts=[f"{diameter}mm {stroke}mm silindir"],
                    n_results=3,
                    where={"stock": {"$gte": 0.1}}
                )
                
                if results['documents'] and results['documents'][0]:
                    print(f"\n{len(results['documents'][0])} uygun ürün:")
                    for i, doc in enumerate(results['documents'][0], 1):
                        meta = results['metadatas'][0][i-1]
                        name = doc.split('\n')[0].replace('ÜRÜN: ', '')
                        similarity = 1 - results['distances'][0][i-1]
                        print(f"  {i}. {name} ({meta['brand']}) - {similarity:.2f}")
                else:
                    print("Bu boyutlarda ürün yok")
            except:
                print("ChromaDB arama hatası")
        
        else:
            print(f"\nAI CEVAP:")
            if friendly:
                print("Canım, silindir için boyut lazım!")
                print("Çap söyle (100mm gibi), seçenekleri göstereyim")
            else:
                print("Silindir araması için çap veya strok belirtin")
                print("Örnek: '100 çap silindir' veya '200 stroklu silindir'")
        
        db.close()
        
    except Exception as e:
        print(f"Hata: {e}")

def main():
    print("CLI TEST - Sorgu yazın, cevap görün!")
    print("Örnekler: '100 çap silindir', '400 stroklu silindir', 'quit' ile çıkış")
    print("=" * 60)
    
    while True:
        try:
            query = input("\n> ").strip()
            
            if query.lower() in ['quit', 'q', 'exit']:
                print("Bye!")
                break
            
            if query:
                quick_answer(query)
        except:
            break

if __name__ == "__main__":
    main()
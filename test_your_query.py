#!/usr/bin/env python3
"""
Test Your Query - Sorgunuzu buraya yazıp test edin
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

# ===== BURAYA SORGUNUZU YAZIN =====
YOUR_QUERY = "100 çap silindir"
# ===================================

def test_single_query(query: str):
    """Tek sorguyu test et"""
    print(f"TEST SORGUSU: '{query}'")
    print("=" * 60)
    
    # Parse dimensions
    import re
    query_upper = query.upper()
    
    diameter = None
    stroke = None
    
    # Çap extraction
    cap_patterns = [r'(\d+)\s*(?:CAP|CAPLI|ÇAP|ÇAPLI)', r'(\d+)\s*LUK', r'Ø(\d+)']
    for pattern in cap_patterns:
        matches = re.findall(pattern, query_upper)
        if matches:
            diameter = int(matches[0])
            break
    
    # Strok extraction
    strok_patterns = [r'(\d+)\s*(?:STROK|STROKLU)']
    for pattern in strok_patterns:
        matches = re.findall(pattern, query_upper)
        if matches:
            stroke = int(matches[0])
            break
    
    # Tone detection
    friendly_words = ['canim', 'kardesim', 'dostum']
    tone = "samimi" if any(word in query.lower() for word in friendly_words) else "professional"
    
    print(f"ALGILANAN:")
    print(f"  Çap: {diameter}mm")
    print(f"  Strok: {stroke}mm") 
    print(f"  Ton: {tone}")
    
    # Progressive logic
    try:
        db = psycopg2.connect(DB_CONNECTION)
        
        if diameter and not stroke:
            print(f"\nDURUM: Çap var, strok eksik -> Strok seçenekleri sun")
            
            with db.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT p.malzeme_adi, i.current_stock
                    FROM products p 
                    JOIN inventory i ON p.id = i.product_id
                    WHERE p.malzeme_adi ILIKE %s AND i.current_stock > 0
                    ORDER BY i.current_stock DESC LIMIT 10
                """, (f'%{diameter}%',))
                
                results = cur.fetchall()
                stroke_options = {}
                
                for row in results:
                    name = row['malzeme_adi']
                    stock = row['current_stock']
                    
                    stroke_match = re.search(rf'{diameter}[*x×](\d+)', name.upper())
                    if stroke_match:
                        stroke_val = int(stroke_match.group(1))
                        key = f"{stroke_val}mm strok"
                        stroke_options[key] = stroke_options.get(key, 0) + stock
                
                if stroke_options:
                    total = sum(stroke_options.values())
                    count = len(stroke_options)
                    
                    print(f"\nAI YANITLARI:")
                    print("-" * 40)
                    
                    if tone == "samimi":
                        print(f"✓ Hmm, {diameter}mm çaplı silindir için {count} strok seçeneği var")
                        print(f"  (toplam {total:.0f} adet stokta).")
                        print("✓ Strok uzunluğu der misin? Böylece sana en uygun ürünü bulabilirim!")
                    else:
                        print(f"✓ İyi bir arama için {diameter}mm çaplı silindir için {count} strok seçeneği var")
                        print(f"  (toplam {total:.0f} adet stokta).")
                        print("✓ Hangi strok uzunluğunu tercih edersiniz? Belirtirseniz daha hassas sonuçlar bulabilirim.")
                    
                    print(f"\nMEVCUT SEÇENEKLER:")
                    sorted_options = sorted(stroke_options.items(), key=lambda x: x[1], reverse=True)
                    for i, (stroke_opt, stock_count) in enumerate(sorted_options[:5], 1):
                        print(f"  {i}. {stroke_opt}: {stock_count:.0f} adet")
                else:
                    print(f"Maalesef {diameter}mm çaplı silindir bulunamadı.")
        
        elif stroke and not diameter:
            print(f"\nDURUM: Strok var, çap eksik -> Çap seçenekleri sun")
            print("AI: Çap seçenekleri sunulacak...")
            
        elif diameter and stroke:
            print(f"\nDURUM: Tam bilgi -> Ürün araması yap")
            print(f"AI: {diameter}mm x {stroke}mm silindir araması yapılıyor...")
            
        else:
            print(f"\nDURUM: Bilgi yok -> Rehberlik et")
            if tone == "samimi":
                print("✓ Tabii canım! Silindir arıyorsun ama boyut bilgisine ihtiyacım var.")
                print("✓ Çap (örn: 100mm) der misin? En uygun ürünü bulayım!")
            else:
                print("✓ Silindir aramanız için boyut bilgisi gerekli.")
                print("✓ Çap (örn: 100mm) belirtirseniz size seçenekleri sunabilirim.")
        
        db.close()
        
    except Exception as e:
        print(f"Hata: {e}")

def main():
    """Ana fonksiyon"""
    print("SINGLE QUERY TESTER")
    print("=" * 40)
    print("Script'in başındaki YOUR_QUERY değişkenini değiştirip test edin!\n")
    
    test_single_query(YOUR_QUERY)
    
    print(f"\n" + "=" * 60)
    print("TEST BİTTİ!")
    print("Başka sorgu test etmek için YOUR_QUERY değişkenini değiştirin.")

if __name__ == "__main__":
    main()
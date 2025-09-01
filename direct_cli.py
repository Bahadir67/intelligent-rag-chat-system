#!/usr/bin/env python3
"""
Direct CLI - Komut satırından argüman ile kullanın
Kullanım: python direct_cli.py "100 lük silindir"
"""

import sys, re
import psycopg2
from psycopg2.extras import RealDictCursor

# Set UTF-8 encoding for Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

if len(sys.argv) < 2:
    print("Kullanim: python direct_cli.py \"sorgunuz\"")
    print("Ornek: python direct_cli.py \"100 cap silindir\"")
    sys.exit()

query = sys.argv[1]
print(f"SORU: {query}")
print("="*50)

# Parse
q = query.upper()
diameter = stroke = None

for pattern in [r'(\d+)\s*(?:CAP|CAPLI|LUK|ÇAP|L\w*K)', r'(\d+)\s*MM']:
    matches = re.findall(pattern, q)
    if matches:
        diameter = int(matches[0])
        break

for pattern in [r'(\d+)\s*(?:STROK|STROKLU)']:
    matches = re.findall(pattern, q)
    if matches:
        stroke = int(matches[0])
        break

# Check for friendly words with better Turkish character handling
friendly_words = ['canım', 'canim', 'kardeşim', 'kardesim', 'dostum', 'abi', 'abla']
friendly = any(word in query.lower() for word in friendly_words)

try:
    db = psycopg2.connect("postgresql://postgres:masterkey@localhost:5432/b2b_rag_system")
    
    if diameter and not stroke:
        with db.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT p.malzeme_adi, i.current_stock
                FROM products p 
                LEFT JOIN inventory i ON p.id = i.product_id
                WHERE p.malzeme_adi ILIKE %s AND COALESCE(i.current_stock, 0) > 0
                LIMIT 10
            """, (f'%{diameter}%',))
            
            results = cur.fetchall()
            strokes = {}
            
            for row in results:
                name, stock = row['malzeme_adi'], row['current_stock']
                # Multiple stroke patterns
                stroke_patterns = [
                    rf'{diameter}[*x](\d+)',  # 100*300
                    rf'(\d+)[*x]\s*{diameter}',  # 32*100  
                    rf'{diameter}\s*/\s*(\d+)',  # 100/300
                ]
                
                for pattern in stroke_patterns:
                    match = re.search(pattern, name.upper())
                    if match:
                        s = int(match.group(1))
                        if s != diameter:  # Don't count diameter as stroke
                            strokes[s] = strokes.get(s, 0) + stock
                        break
            
            if strokes:
                total = sum(strokes.values())
                print("\nAI CEVAP:")
                if friendly:
                    print(f"Hmm canım, {diameter}mm çaplı silindir için {len(strokes)} strok seçeneği var")
                    print(f"(toplam {total:.0f} adet stokta). Strok der misin?")
                else:
                    print(f"{diameter}mm çaplı silindir için {len(strokes)} strok seçeneği:")
                    print(f"(toplam {total:.0f} adet stokta)")
                    print("Hangi strok uzunluğunu tercih edersiniz?")
                
                print("\nMEVCUT SEÇENEKLER:")
                for s, c in sorted(strokes.items(), key=lambda x: x[1], reverse=True)[:3]:
                    print(f"  • {s}mm strok: {c:.0f} adet stokta")
            else:
                print(f"\n{diameter}mm çaplı silindir bulunamadı")
    
    elif stroke and not diameter:
        print("\nAI CEVAP:")
        if friendly:
            print(f"Canım, {stroke}mm strok için çap gerekli!")
            print("Çap der misin? En uygun ürünü bulayım!")
        else:
            print(f"{stroke}mm stroklu silindir için çap belirtirseniz")
            print("size mevcut seçenekleri sunabilirim.")
    
    elif diameter and stroke:
        print("\nAI CEVAP:")
        if friendly:
            print(f"Süper canım! {diameter}mm x {stroke}mm silindir arıyorsun.")
            print("Tam bilgiye sahipsin, ürün araması yapıyorum...")
        else:
            print(f"Mükemmel! {diameter}mm x {stroke}mm silindir arıyorsunuz.")
            print("Tam bilgiye sahipsiniz, ürün araması yapılıyor...")
    
    else:
        print("\nAI CEVAP:")
        if friendly:
            print("Canım, silindir için boyut bilgisi lazım!")
            print("Çap (100mm gibi) söyle, seçenekleri göstereyim.")
        else:
            print("Silindir araması için boyut bilgisi gerekli.")
            print("Çap (örnek: 100mm) veya strok belirtin.")
    
    db.close()

except Exception as e:
    print(f"Hata: {e}")

print(f"\n" + "="*50)
print("Başka sorgu için: python direct_cli.py \"yeni sorgunuz\"")
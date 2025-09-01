#!/usr/bin/env python3

# BASIT CLI TEST - Sorguyu buraya yazin ve calistirin!

query = "100 cap silindir"  # <- BURAYA SORGUNUZU YAZIN

import os, sys, re
sys.stdout.reconfigure(encoding='utf-8') if sys.platform == "win32" else None

import psycopg2
from psycopg2.extras import RealDictCursor

print(f"SORU: {query}")
print("="*40)

# Parse
q = query.upper()
diameter = None
stroke = None

# Cap patterns
for pattern in [r'(\d+)\s*(?:CAP|CAPLI|LUK)', r'(\d+)\s*MM']:
    matches = re.findall(pattern, q)
    if matches:
        diameter = int(matches[0])
        break

# Strok patterns  
for pattern in [r'(\d+)\s*(?:STROK|STROKLU)']:
    matches = re.findall(pattern, q)
    if matches:
        stroke = int(matches[0])
        break

friendly = any(w in query.lower() for w in ['canim', 'kardesim', 'dostum'])

print(f"Çap: {diameter}, Strok: {stroke}, Ton: {'samimi' if friendly else 'resmi'}")

# DB
try:
    db = psycopg2.connect("postgresql://postgres:masterkey@localhost:5432/b2b_rag_system")
    
    if diameter and not stroke:
        print("\nSTROK SEÇENEKLERİ ARANIYOR...")
        
        with db.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT p.malzeme_adi, i.current_stock
                FROM products p JOIN inventory i ON p.id = i.product_id
                WHERE p.malzeme_adi ILIKE %s AND i.current_stock > 0
                ORDER BY i.current_stock DESC LIMIT 10
            """, (f'%{diameter}%',))
            
            results = cur.fetchall()
            strokes = {}
            
            for row in results:
                name, stock = row['malzeme_adi'], row['current_stock']
                match = re.search(rf'{diameter}[*x](\d+)', name.upper())
                if match:
                    s = int(match.group(1))
                    strokes[s] = strokes.get(s, 0) + stock
            
            if strokes:
                total = sum(strokes.values())
                print(f"\nAI: {diameter}mm çaplı silindir için {len(strokes)} strok seçeneği")
                print(f"    (toplam {total:.0f} adet stokta)")
                
                if friendly:
                    print("    Strok der misin? En uygun ürünü bulayım!")
                else:
                    print("    Hangi strok uzunluğunu tercih edersiniz?")
                
                print("\nSEÇENEKLER:")
                for stroke_val, count in sorted(strokes.items(), key=lambda x: x[1], reverse=True)[:3]:
                    print(f"  • {stroke_val}mm strok: {count:.0f} adet")
            else:
                print(f"\n{diameter}mm çaplı silindir bulunamadı")
    
    elif stroke and not diameter:
        print(f"\nAI: {stroke}mm strok için çap gerekli!")
        if friendly:
            print("    Çap der misin canım?")
        else:
            print("    Çap belirtirseniz bulabilirim.")
    
    elif diameter and stroke:
        print(f"\nAI: {diameter}x{stroke}mm silindir aranıyor...")
        print("    (Tam bilgi - ürün araması yapılacak)")
    
    else:
        print("\nAI: Silindir için boyut lazım")
        print("    Örnek: '100 çap silindir' yazın")
    
    db.close()

except Exception as e:
    print(f"Hata: {e}")

print(f"\n" + "="*40)
print("TEST BİTTİ! Başka sorgu için yukarıdaki 'query' değişkenini değiştirin.")
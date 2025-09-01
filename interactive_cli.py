#!/usr/bin/env python3

import os, sys, re
import psycopg2
from psycopg2.extras import RealDictCursor

def get_answer(query):
    q = query.upper()
    diameter = stroke = None
    
    # Parse cap
    for pattern in [r'(\d+)\s*(?:CAP|CAPLI|LUK|ÇAP)', r'(\d+)\s*MM']:
        matches = re.findall(pattern, q)
        if matches:
            diameter = int(matches[0])
            break
    
    # Parse strok
    for pattern in [r'(\d+)\s*(?:STROK|STROKLU)']:
        matches = re.findall(pattern, q)
        if matches:
            stroke = int(matches[0])
            break
    
    friendly = any(w in query.lower() for w in ['canim', 'kardesim', 'dostum'])
    
    try:
        db = psycopg2.connect("postgresql://postgres:masterkey@localhost:5432/b2b_rag_system")
        
        if diameter and not stroke:
            with db.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT p.malzeme_adi, i.current_stock
                    FROM products p JOIN inventory i ON p.id = i.product_id
                    WHERE p.malzeme_adi ILIKE %s AND i.current_stock > 0
                    LIMIT 10
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
                    if friendly:
                        print(f"\nHmm, {diameter}mm capli silindir icin {len(strokes)} strok secenegi var")
                        print(f"(toplam {total:.0f} adet). Strok der misin?")
                    else:
                        print(f"\n{diameter}mm capli silindir icin {len(strokes)} strok secenegi:")
                        print(f"(toplam {total:.0f} adet stokta)")
                    
                    print("Seçenekler:")
                    for s, c in sorted(strokes.items(), key=lambda x: x[1], reverse=True)[:3]:
                        print(f"  - {s}mm strok: {c:.0f} adet")
                else:
                    print(f"\n{diameter}mm capli silindir bulunamadi")
        
        elif stroke and not diameter:
            if friendly:
                print(f"\nCanim, {stroke}mm strok icin cap lazim!")
            else:
                print(f"\n{stroke}mm strok icin cap belirtirseniz bulabilirim")
        
        elif diameter and stroke:
            print(f"\nTamam! {diameter}x{stroke}mm silindir aranıyor...")
        
        else:
            if friendly:
                print("\nCanim, silindir icin boyut soyle!")
            else:
                print("\nSilindir icin cap veya strok belirtin")
                print("Ornek: '100 cap silindir'")
        
        db.close()
        
    except Exception as e:
        print(f"Hata: {e}")

# MAIN LOOP
print("B2B Silindir AI - Yazin, Enter basin!")
print("'quit' ile cikis")
print("-" * 40)

while True:
    try:
        query = input("\n> ")
        if query.lower() in ['quit', 'q', 'exit', 'cikis']:
            print("Bye!")
            break
        if query.strip():
            get_answer(query)
    except (EOFError, KeyboardInterrupt):
        print("\nBye!")
        break
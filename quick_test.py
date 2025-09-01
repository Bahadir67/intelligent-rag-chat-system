#!/usr/bin/env python3
"""
Quick Progressive Test - Sadece core functionality
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

def quick_progressive_test(query: str):
    """Hızlı progressive test"""
    print(f"\nSORU: {query}")
    print("=" * 50)
    
    # 1. Parse query for dimensions
    diameter = None
    stroke = None
    
    import re
    query_upper = query.upper()
    
    # Çap extraction
    cap_patterns = [r'(\d+)\s*(?:CAP|CAPLI|ÇAP|ÇAPLI)', r'(\d+)\s*LUK', r'(\d+)\s*MM']
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
    
    print(f"Algilanan - Çap: {diameter}mm, Strok: {stroke}mm")
    
    # 2. Check what's missing and get options
    try:
        db = psycopg2.connect(DB_CONNECTION)
        
        if diameter and not stroke:
            # Strok seçenekleri
            print(f"\n{diameter}mm çap için strok seçenekleri:")
            with db.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT p.malzeme_adi, i.current_stock
                    FROM products p 
                    JOIN inventory i ON p.id = i.product_id
                    WHERE p.malzeme_adi ILIKE %s AND i.current_stock > 0
                    ORDER BY i.current_stock DESC LIMIT 5
                """, (f'%{diameter}%',))
                
                results = cur.fetchall()
                stroke_counts = {}
                
                for row in results:
                    name = row['malzeme_adi']
                    stock = row['current_stock']
                    
                    # Extract stroke
                    stroke_match = re.search(rf'{diameter}[*x×](\d+)', name.upper())
                    if stroke_match:
                        stroke_val = int(stroke_match.group(1))
                        key = f"{stroke_val}mm strok"
                        stroke_counts[key] = stroke_counts.get(key, 0) + stock
                
                if stroke_counts:
                    total = sum(stroke_counts.values())
                    print(f"Toplam {len(stroke_counts)} seçenek, {total:.0f} adet stokta")
                    
                    for stroke_opt, count in sorted(stroke_counts.items(), key=lambda x: x[1], reverse=True)[:3]:
                        print(f"  • {stroke_opt}: {count:.0f} adet")
                    
                    print(f"\nAI: Hmm, {diameter}mm çaplı silindir için {len(stroke_counts)} strok seçeneği var.")
                    print("Hangi strok uzunluğunu tercih edersiniz?")
                else:
                    print("Strok seçenekleri bulunamadı")
        
        elif stroke and not diameter:
            # Çap seçenekleri  
            print(f"\n{stroke}mm strok için çap seçenekleri:")
            with db.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT p.malzeme_adi, i.current_stock
                    FROM products p
                    JOIN inventory i ON p.id = i.product_id  
                    WHERE p.malzeme_adi ILIKE %s AND i.current_stock > 0
                    ORDER BY i.current_stock DESC LIMIT 5
                """, (f'%{stroke}%',))
                
                results = cur.fetchall()
                diameter_counts = {}
                
                for row in results:
                    name = row['malzeme_adi'] 
                    stock = row['current_stock']
                    
                    # Extract diameter
                    dia_match = re.search(rf'(\d+)[*x×]{stroke}', name.upper())
                    if dia_match:
                        dia_val = int(dia_match.group(1))
                        key = f"{dia_val}mm çap"
                        diameter_counts[key] = diameter_counts.get(key, 0) + stock
                
                if diameter_counts:
                    print(f"Toplam {len(diameter_counts)} seçenek mevcut")
                    
                    for dia_opt, count in sorted(diameter_counts.items(), key=lambda x: x[1], reverse=True)[:3]:
                        print(f"  • {dia_opt}: {count:.0f} adet")
                    
                    print(f"\nAI: {stroke}mm stroklu silindir için {len(diameter_counts)} çap seçeneği var.")
                    print("Hangi çapı tercih edersiniz?")
                else:
                    print("Çap seçenekleri bulunamadı")
        
        elif diameter and stroke:
            # Tam bilgi - direkt arama
            print(f"\n{diameter}mm x {stroke}mm silindir aranıyor...")
            print("AI: Tam bilgiye sahipsiniz, ürün araması yapılıyor!")
        
        else:
            # Hiç bilgi yok
            print("\nAI: Silindir aramanız için boyut bilgisi gerekli.")
            print("Çap (örn: 100mm) ve strok (örn: 200mm) söylerseniz")
            print("size mevcut seçenekleri sunabilirim.")
        
        db.close()
        
    except Exception as e:
        print(f"Database hatası: {e}")

def main():
    """Ana test"""
    print("QUICK PROGRESSIVE INQUIRY TEST")
    print("=" * 40)
    
    test_cases = [
        "100 çap silindir",
        "100 lük silindir arıyorum canım kardeşim",
        "400 stroklu silindir lazım", 
        "silindir arıyorum",
        "100 çap 200 strok silindir"
    ]
    
    for query in test_cases:
        quick_progressive_test(query)
        print()

if __name__ == "__main__":
    main()
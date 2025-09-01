#!/usr/bin/env python3
"""
Simple Progressive Inquiry Test - Tek seferde test edin
"""

import os
import sys
from progressive_inquiry_system import ProgressiveInquirySystem

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

def simple_test(query: str):
    """Basit test fonksiyonu"""
    print(f"\n{'='*60}")
    print(f"SORU: {query}")
    print('='*60)
    
    system = ProgressiveInquirySystem()
    response = system.analyze_and_respond(query)
    
    print("\nAI CEVAP:")
    print("-" * 30)
    print(response.main_response)
    
    if response.follow_up_questions:
        print("\nEK SORULAR:")
        for i, q in enumerate(response.follow_up_questions, 1):
            print(f"{i}. {q}")
    
    if response.available_options:
        print("\nSECENEKLER:")
        if "stroke_options" in response.available_options:
            opts = response.available_options["stroke_options"]
            print("Strok secenekleri:")
            for stroke, count in list(opts.items())[:3]:
                print(f"  - {stroke}: {count} adet")
        
        if "diameter_options" in response.available_options:
            opts = response.available_options["diameter_options"]
            print("Cap secenekleri:")
            for diameter in list(opts.keys())[:3]:
                print(f"  - {diameter}")

def main():
    print("BASIT PROGRESSIVE INQUIRY TEST")
    print("="*50)
    
    # Test queries
    test_cases = [
        "100 cap silindir",
        "100 luk silindir ariyorum canim kardesim", 
        "400 stroklu silindir lazim",
        "silindir ariyorum"
    ]
    
    for query in test_cases:
        simple_test(query)
    
    print(f"\n{'='*60}")
    print("TEST TAMAMLANDI!")

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Interactive Progressive Demo - Gerçek konuşma simülasyonu
"""

import os
import sys
from progressive_inquiry_system import ProgressiveInquirySystem

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

def demo_conversation(query: str, system: ProgressiveInquirySystem):
    """Tek sorgu demonstrasyonu"""
    
    print(f"\n{'='*60}")
    print(f"MUSTERI: '{query}'")
    print(f"{'='*60}")
    
    response = system.analyze_and_respond(query)
    
    print(f"\nAI UZMAN:")
    print("-" * 30)
    print(response.main_response)
    
    if response.follow_up_questions:
        print()
        for question in response.follow_up_questions:
            print(f"• {question}")
    
    # Show available options nicely
    if response.available_options:
        print(f"\nMEVCUT SECENEKLER:")
        print("-" * 30)
        
        if "stroke_options" in response.available_options:
            stroke_opts = response.available_options["stroke_options"]
            print("Strok Seçenekleri:")
            for stroke, count in list(stroke_opts.items())[:5]:
                print(f"  • {stroke}: {count} adet stokta")
        
        if "diameter_options" in response.available_options:
            dia_opts = response.available_options["diameter_options"]  
            print("Çap Seçenekleri:")
            for diameter in list(dia_opts.keys())[:5]:
                print(f"  • {diameter}")
        
        if "feature_options" in response.available_options:
            feat_opts = response.available_options["feature_options"]
            if feat_opts:
                print("Özellik Seçenekleri:")
                for feature, count in feat_opts.items():
                    print(f"  • {feature}: {count} çeşit mevcut")

def main():
    """Ana demo"""
    print("PROGRESSIVE INQUIRY DEMO")
    print("Gerçek B2B müşteri-AI uzman konuşması")
    print("=" * 60)
    
    system = ProgressiveInquirySystem()
    
    # Demo konuşmalar
    demo_scenarios = [
        {
            "title": "Senaryo 1: Eksik Strok Bilgisi", 
            "queries": [
                "100 çap silindir arıyorum canım kardeşim",
                # Follow-up: "145mm strok olsun"
            ]
        },
        {
            "title": "Senaryo 2: Sadece Strok Belirtildi",
            "queries": [
                "400 stroklu silindir lazım acil"
            ]
        },
        {
            "title": "Senaryo 3: Tam Bilgi",
            "queries": [
                "100 çap 200 strok manyetik sensörlü silindir"
            ]
        },
        {
            "title": "Senaryo 4: Genel Arama", 
            "queries": [
                "silindir arıyorum"
            ]
        }
    ]
    
    for scenario in demo_scenarios:
        print(f"\n{scenario['title']}")
        print("=" * 50)
        
        for query in scenario['queries']:
            demo_conversation(query, system)
    
    print(f"\n{'='*60}")
    print("DEMO TAMAMLANDI!")
    print("Sistem artık proaktif olarak eksik bilgileri soruyor")
    print("ve kullanıcıya mevcut seçenekleri sunuyor!")

if __name__ == "__main__":
    main()
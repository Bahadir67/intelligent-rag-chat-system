#!/usr/bin/env python3
"""
Smart Search Demo - Query Understanding + Product Search Integration
"""

import os
import sys
import time
import chromadb
from dotenv import load_dotenv
import requests
from query_rag_system import QueryRAGSystem, QueryUnderstanding

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL_NAME = os.getenv("MODEL", "openai/gpt-3.5-turbo")

class SmartSearchSystem:
    """Query understanding + Product search entegrasyonu"""
    
    def __init__(self):
        # Query understanding
        self.query_system = QueryRAGSystem()
        
        # Product search
        try:
            self.product_client = chromadb.PersistentClient(
                path=os.path.join(os.getcwd(), "chroma_db")
            )
            self.product_collection = self.product_client.get_collection("b2b_products")
            print("Smart Search System hazir!")
        except Exception as e:
            print(f"Product database hatasi: {e}")
    
    def smart_search(self, user_query: str):
        """Akıllı arama - Understanding + Search + Smart Response"""
        
        print("SMART SEARCH PIPELINE")
        print("=" * 60)
        
        # 1. Query Understanding
        understanding = self.query_system.understand_query(user_query)
        
        # 2. Enhanced Product Search
        enhanced_query = self._build_enhanced_query(understanding)
        print(f"\nENHANCED QUERY: {enhanced_query}")
        
        # 3. Product Search
        products = self._search_products(enhanced_query, understanding)
        
        # 4. Smart Response Generation  
        smart_response = self._generate_contextual_response(understanding, products)
        
        print("\nSMART AI RESPONSE:")
        print("-" * 40)
        print(smart_response)
        
        return understanding, products, smart_response
    
    def _build_enhanced_query(self, understanding: QueryUnderstanding) -> str:
        """Understanding'e göre gelişmiş arama sorgusu oluştur"""
        
        query_parts = []
        specs = understanding.specifications
        
        # Boyut bilgileri
        if specs.get("diameter"):
            query_parts.append(f"{specs['diameter']}mm")
            query_parts.append(f"çap {specs['diameter']}")
        
        if specs.get("stroke"):
            query_parts.append(f"{specs['stroke']}mm")
            query_parts.append(f"strok {specs['stroke']}")
        
        # Özellikler
        feature_mapping = {
            "magnetic": "manyetik sensör magnetic sensor",
            "cushioned": "yastıklamalı cushioned yumuşak durma",
            "quiet": "sessiz quiet silent",
            "high_pressure": "yüksek basınç high pressure dayanıklı"
        }
        
        for feature in specs.get("features", []):
            if feature in feature_mapping:
                query_parts.append(feature_mapping[feature])
        
        # Marka
        if specs.get("brand"):
            query_parts.append(specs["brand"])
        
        # Intent'e göre ek anahtar kelimeler
        if understanding.intent == "problem_solving":
            query_parts.append("alternatif çözüm")
        elif understanding.intent == "urgency_specification":
            query_parts.append("stokta mevcut")
        
        # Base category
        query_parts.append("silindir cylinder")
        
        return " ".join(query_parts)
    
    def _search_products(self, enhanced_query: str, understanding: QueryUnderstanding):
        """Enhanced query ile ürün ara"""
        try:
            # Filters
            where_clause = {"stock": {"$gte": 0.1}}
            
            # Marka filtresi
            if understanding.specifications.get("brand"):
                where_clause["brand"] = understanding.specifications["brand"]
            
            # Urgency'ye göre stok filtresi
            if understanding.urgency == "urgent":
                where_clause["stock"] = {"$gte": 5.0}  # Acil için daha fazla stok
            
            results = self.product_collection.query(
                query_texts=[enhanced_query],
                n_results=8,
                where=where_clause
            )
            
            products = []
            if results['documents'] and results['documents'][0]:
                for i, doc in enumerate(results['documents'][0]):
                    metadata = results['metadatas'][0][i]
                    similarity = 1 - results['distances'][0][i]
                    product_name = doc.split('\n')[0].replace('ÜRÜN: ', '')
                    
                    # Spec matching score
                    spec_match_score = self._calculate_spec_match(understanding, metadata, doc)
                    
                    products.append({
                        'malzeme_adi': product_name,
                        'brand_name': metadata['brand'],
                        'malzeme_kodu': metadata['malzeme_kodu'],
                        'current_stock': metadata['stock'],
                        'similarity_score': similarity,
                        'spec_match_score': spec_match_score,
                        'combined_score': similarity * 0.6 + spec_match_score * 0.4,
                        'full_content': doc
                    })
            
            # Combined score'a göre sırala
            products.sort(key=lambda x: x['combined_score'], reverse=True)
            
            print(f"\nPRODUCT SEARCH RESULTS: {len(products)} urun")
            for i, p in enumerate(products[:3], 1):
                print(f"{i}. {p['malzeme_adi']} - Combined: {p['combined_score']:.3f}")
            
            return products
            
        except Exception as e:
            print(f"Search hatasi: {e}")
            return []
    
    def _calculate_spec_match(self, understanding: QueryUnderstanding, metadata: dict, doc: str) -> float:
        """Spec matching skoru hesapla"""
        score = 0.0
        specs = understanding.specifications
        
        # Boyut match (metadata'da dimension bilgisi varsa)
        if specs.get("diameter") and metadata.get("diameter"):
            if abs(specs["diameter"] - metadata["diameter"]) <= 5:  # 5mm tolerance
                score += 0.3
        
        if specs.get("stroke") and metadata.get("stroke"):
            if abs(specs["stroke"] - metadata["stroke"]) <= 20:  # 20mm tolerance
                score += 0.3
        
        # Feature match
        doc_upper = doc.upper()
        feature_keywords = {
            "magnetic": ["MANYETIK", "MAGNETIC", "SENSÖR"],
            "cushioned": ["YASTIK", "CUSHION", "YUMUŞAK"],
            "quiet": ["SESSİZ", "QUIET"],
            "high_pressure": ["YÜKSEK", "BASINÇ", "PRESSURE"]
        }
        
        for feature in specs.get("features", []):
            if feature in feature_keywords:
                if any(kw in doc_upper for kw in feature_keywords[feature]):
                    score += 0.2
        
        # Brand exact match
        if specs.get("brand") and metadata.get("brand") == specs["brand"]:
            score += 0.2
        
        return min(score, 1.0)
    
    def _generate_contextual_response(self, understanding: QueryUnderstanding, products) -> str:
        """Context-aware response oluştur"""
        
        if not products:
            return "Belirttiğiniz özelliklerde ürün bulunamadı."
        
        # Tone'a göre greeting
        if understanding.tone == "friendly_informal":
            greeting = "Tabii canım! Aradığın ürünleri buldum:"
        else:
            greeting = "Arama kriterlerinize uygun ürünleri buldum:"
        
        # Specifications summary
        specs = understanding.specifications
        spec_summary = ""
        if specs.get("diameter") and specs.get("stroke"):
            spec_summary = f" {specs['diameter']}mm x {specs['stroke']}mm boyutlarında"
        elif specs.get("diameter"):
            spec_summary = f" {specs['diameter']}mm çapında"
        
        feature_text = ""
        if specs.get("features"):
            features_tr = {
                "magnetic": "manyetik sensörlü",
                "cushioned": "yastıklamalı", 
                "quiet": "sessiz çalışan",
                "high_pressure": "yüksek basınçlı"
            }
            feature_list = [features_tr.get(f, f) for f in specs["features"]]
            feature_text = f" {', '.join(feature_list)}"
        
        # AI response with context
        context_prompt = f"""
        KULLANICI PROFILI:
        - Ton: {understanding.tone}
        - Aciliyet: {understanding.urgency}
        - Aranan: {spec_summary}{feature_text} silindir
        
        EN UYGUN 3 ÜRÜN:
        """
        
        for i, product in enumerate(products[:3], 1):
            context_prompt += f"""
        {i}. {product['malzeme_adi']}
           Marka: {product['brand_name']}
           Kod: {product['malzeme_kodu']} 
           Stok: {product['current_stock']:.0f} adet
           Uygunluk: {product['combined_score']:.2f}
        """
        
        # OpenRouter'dan smart response al
        try:
            messages = [
                {
                    "role": "system",
                    "content": f"""Sen B2B ürün uzmanısın. 
                    Kullanıcı tonu: {understanding.tone}
                    {'Samimi ve arkadaşça konuş.' if understanding.tone == 'friendly_informal' else 'Professional konuş.'}
                    {'Acil ihtiyacını vurgula.' if understanding.urgency == 'urgent' else ''}
                    """
                },
                {
                    "role": "user",
                    "content": f"{context_prompt}\n\nEn uygun ürünü öner ve teknik nedenlerini açıkla."
                }
            ]
            
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": MODEL_NAME,
                    "messages": messages,
                    "temperature": 0.4,
                    "max_tokens": 350
                },
                timeout=15
            )
            
            if response.status_code == 200:
                ai_response = response.json()['choices'][0]['message']['content']
                return f"{greeting}\n\n{ai_response}"
            else:
                return f"{greeting} En uygun seçenek: {products[0]['malzeme_adi']}"
                
        except Exception as e:
            return f"{greeting} En uygun seçenek: {products[0]['malzeme_adi']}"

def main():
    """Demo test"""
    
    smart_system = SmartSearchSystem()
    
    test_queries = [
        "100 çaplı 400 stroklu magnetli silindir arıyorum canım kardeşim",
        "yastıklamalı silindir lazım acil", 
        "gürültülü çalışıyor sessiz alternatif öner dostum"
    ]
    
    for query in test_queries:
        print("\n" + "="*80)
        understanding, products, response = smart_system.smart_search(query)
        print("\n" + "="*80)

if __name__ == "__main__":
    main()
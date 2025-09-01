#!/usr/bin/env python3
"""
Query RAG System - Kullanıcı sorgularını semantic olarak anlama
"""

import os
import re
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import chromadb
from dotenv import load_dotenv
import requests

load_dotenv()

@dataclass
class QueryUnderstanding:
    """Sorgu anlama sonucu"""
    intent: str
    specifications: Dict[str, Any]
    tone: str
    urgency: str
    context_clues: List[str]
    parsed_features: List[str]
    confidence: float

class QueryRAGSystem:
    """Sorgu anlama için RAG sistemi"""
    
    def __init__(self):
        # Query patterns veritabanı
        self.query_patterns = self._create_query_patterns()
        
        # ChromaDB for query understanding
        try:
            self.query_client = chromadb.EphemeralClient()
            self.query_collection = self.query_client.create_collection("query_patterns")
            self._index_query_patterns()
            print("Query RAG sistemi hazır!")
        except Exception as e:
            print(f"Query RAG hatası: {e}")
    
    def _create_query_patterns(self) -> List[Dict]:
        """Query pattern veritabanı oluştur"""
        patterns = [
            # Boyut ifadeleri
            {
                "pattern": "100 çaplı 400 stroklu",
                "semantic": "diameter:100mm stroke:400mm",
                "intent": "size_specification",
                "features": ["dimensional_spec"],
                "examples": ["100 çaplı", "çap 100", "100mm çap", "100 bore"]
            },
            
            # Özellik ifadeleri
            {
                "pattern": "magnetli silindir",
                "semantic": "magnetic_sensor cylinder",
                "intent": "feature_specification", 
                "features": ["magnetic", "sensor", "proximity"],
                "examples": ["magnetli", "manyetik", "sensörlü", "magnetic"]
            },
            
            # Yastık ifadeleri
            {
                "pattern": "yastıklamalı silindir",
                "semantic": "cushioned_cylinder soft_landing",
                "intent": "feature_specification",
                "features": ["cushioned", "soft_stop", "damped"],
                "examples": ["yastıklamalı", "yumuşak durma", "cushioned", "damped"]
            },
            
            # Ton/Tarz ifadeleri
            {
                "pattern": "canım kardeşim",
                "semantic": "friendly_informal_tone",
                "intent": "relationship_context",
                "features": ["informal", "friendly", "familiar"],
                "examples": ["canım", "kardeşim", "dostum", "arkadaş"]
            },
            
            # Aciliyet ifadeleri
            {
                "pattern": "acil lazım",
                "semantic": "urgent_need immediate",
                "intent": "urgency_specification",
                "features": ["urgent", "immediate", "priority"],
                "examples": ["acil", "hemen", "ivedi", "urgent"]
            },
            
            # Marka ifadeleri
            {
                "pattern": "MAG marka",
                "semantic": "brand_preference MAG",
                "intent": "brand_specification",
                "features": ["brand_specific", "MAG"],
                "examples": ["MAG marka", "MAG'dan", "SMC marka", "FESTO"]
            },
            
            # Miktar ifadeleri
            {
                "pattern": "5 adet lazım",
                "semantic": "quantity_specification amount:5",
                "intent": "quantity_specification", 
                "features": ["quantity", "amount"],
                "examples": ["adet", "tane", "parça", "pieces"]
            },
            
            # Uygulama alanları
            {
                "pattern": "temizlik sektörü için",
                "semantic": "application_area cleaning_industry",
                "intent": "application_specification",
                "features": ["cleaning", "industry_specific"],
                "examples": ["temizlik", "gıda", "otomotiv", "tekstil"]
            },
            
            # Problem çözme
            {
                "pattern": "gürültülü çalışıyor sessiz lazım",
                "semantic": "problem_solving noise_issue quiet_operation",
                "intent": "problem_solving",
                "features": ["noise_problem", "quiet_needed"],
                "examples": ["gürültülü", "sesli", "sessiz", "quiet"]
            },
            
            # Performans gereksinimleri
            {
                "pattern": "yüksek basınçta çalışacak",
                "semantic": "performance_requirement high_pressure",
                "intent": "performance_specification",
                "features": ["high_pressure", "performance"],
                "examples": ["yüksek basınç", "dayanıklı", "heavy duty"]
            }
        ]
        
        return patterns
    
    def _index_query_patterns(self):
        """Query pattern'leri ChromaDB'ye indexle"""
        documents = []
        metadatas = []
        ids = []
        
        for i, pattern in enumerate(self.query_patterns):
            # Rich document oluştur
            doc_content = f"""
            PATTERN: {pattern['pattern']}
            SEMANTIC: {pattern['semantic']}
            INTENT: {pattern['intent']}
            FEATURES: {', '.join(pattern['features'])}
            
            EXAMPLES:
            {chr(10).join('- ' + ex for ex in pattern['examples'])}
            
            CONTEXT: Turkish B2B industrial product queries
            DOMAIN: Pneumatic cylinders, filters, valves
            """
            
            documents.append(doc_content.strip())
            metadatas.append({
                "pattern_id": i,
                "intent": pattern['intent'],
                "feature_count": len(pattern['features']),
                "primary_feature": pattern['features'][0] if pattern['features'] else ""
            })
            ids.append(f"pattern_{i}")
        
        self.query_collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
    
    def understand_query(self, user_query: str) -> QueryUnderstanding:
        """User query'yi semantic olarak anla"""
        print(f"\nQUERY ANALYSIS: '{user_query}'")
        print("=" * 50)
        
        # 1. Pattern matching ile temel anlama
        basic_understanding = self._basic_pattern_matching(user_query)
        
        # 2. Semantic search ile derin anlama  
        semantic_understanding = self._semantic_query_search(user_query)
        
        # 3. Combine results
        combined_understanding = self._combine_understanding(
            user_query, basic_understanding, semantic_understanding
        )
        
        self._print_understanding(combined_understanding)
        return combined_understanding
    
    def _basic_pattern_matching(self, query: str) -> Dict:
        """Temel pattern matching"""
        results = {
            "diameter": None,
            "stroke": None,
            "features": [],
            "brand": None,
            "quantity": None,
            "tone_indicators": [],
            "urgency_level": "normal"
        }
        
        query_upper = query.upper()
        
        # Boyut çıkarma
        size_patterns = [
            r'(\d+)\s*(?:ÇAP|ÇAPLI|ÇAPI|MM\s*ÇAP)',
            r'(\d+)\s*(?:STROK|STROKLU|STROKE)',
            r'(\d+)\s*[*x×]\s*(\d+)',  # 100x400 formatı
            r'Ø(\d+)',  # Ø100 formatı
        ]
        
        for pattern in size_patterns:
            matches = re.findall(pattern, query_upper)
            if matches:
                if 'ÇAP' in pattern or 'Ø' in pattern:
                    results["diameter"] = int(matches[0]) if isinstance(matches[0], str) else int(matches[0][0])
                elif 'STROK' in pattern:
                    results["stroke"] = int(matches[0])
                elif '*' in pattern or 'x' in pattern or '×' in pattern:
                    # 100x400 format
                    results["diameter"] = int(matches[0][0])
                    results["stroke"] = int(matches[0][1])
        
        # Özellik çıkarma
        feature_keywords = {
            "magnetic": ["MAGNET", "MANYETİK", "SENSÖR", "SENSOR"],
            "cushioned": ["YASTIK", "CUSHION", "YUMUŞAK", "DAMPED"],
            "quiet": ["SESSİZ", "QUIET", "SILENT"],
            "oil_resistant": ["YAĞ", "OIL", "DİRENÇ"],
            "high_pressure": ["YÜKSEK", "BASINÇ", "PRESSURE"]
        }
        
        for feature, keywords in feature_keywords.items():
            if any(kw in query_upper for kw in keywords):
                results["features"].append(feature)
        
        # Marka çıkarma
        brands = ["MAG", "SMC", "FESTO", "PARKER", "BOSCH"]
        for brand in brands:
            if brand in query_upper:
                results["brand"] = brand
                break
        
        # Ton analizi
        friendly_indicators = ["CANIM", "KARDEŞİM", "DOSTUM", "ARKADAŞ", "YAA"]
        if any(indicator in query_upper for indicator in friendly_indicators):
            results["tone_indicators"].append("friendly")
            results["tone_indicators"].append("informal")
        
        # Aciliyet
        urgent_keywords = ["ACİL", "HEMEN", "İVEDİ", "ÇOK LAZIM"]
        if any(kw in query_upper for kw in urgent_keywords):
            results["urgency_level"] = "urgent"
        
        return results
    
    def _semantic_query_search(self, query: str) -> Dict:
        """Semantic search ile query anlama"""
        try:
            # ChromaDB'de benzer pattern'leri ara
            results = self.query_collection.query(
                query_texts=[query],
                n_results=3
            )
            
            semantic_results = {
                "matched_patterns": [],
                "confidence_scores": [],
                "extracted_intents": []
            }
            
            if results['documents'] and results['documents'][0]:
                for i, doc in enumerate(results['documents'][0]):
                    metadata = results['metadatas'][0][i]
                    similarity = 1 - results['distances'][0][i]
                    
                    semantic_results["matched_patterns"].append({
                        "pattern": doc,
                        "intent": metadata['intent'],
                        "similarity": similarity,
                        "primary_feature": metadata['primary_feature']
                    })
                    
                    semantic_results["confidence_scores"].append(similarity)
                    semantic_results["extracted_intents"].append(metadata['intent'])
            
            return semantic_results
            
        except Exception as e:
            print(f"Semantic search hatası: {e}")
            return {"matched_patterns": [], "confidence_scores": [], "extracted_intents": []}
    
    def _combine_understanding(self, query: str, basic: Dict, semantic: Dict) -> QueryUnderstanding:
        """Temel ve semantic anlayışı birleştir"""
        
        # Intent belirleme
        primary_intent = "product_search"
        if semantic["extracted_intents"]:
            intent_counts = {}
            for intent in semantic["extracted_intents"]:
                intent_counts[intent] = intent_counts.get(intent, 0) + 1
            primary_intent = max(intent_counts, key=intent_counts.get)
        
        # Specifications birleştir
        specifications = {
            "diameter": basic.get("diameter"),
            "stroke": basic.get("stroke"), 
            "features": basic.get("features", []),
            "brand": basic.get("brand"),
            "quantity": basic.get("quantity")
        }
        
        # Semantic'ten ek özellikler ekle
        for pattern_info in semantic.get("matched_patterns", []):
            if pattern_info["primary_feature"] and pattern_info["similarity"] > 0.3:
                if pattern_info["primary_feature"] not in specifications["features"]:
                    specifications["features"].append(pattern_info["primary_feature"])
        
        # Ton belirleme
        tone = "professional"
        if "friendly" in basic.get("tone_indicators", []):
            tone = "friendly_informal"
        
        # Confidence hesapla
        confidence = 0.5  # Base confidence
        if specifications["diameter"] or specifications["stroke"]:
            confidence += 0.2
        if specifications["features"]:
            confidence += 0.2
        if semantic.get("confidence_scores"):
            avg_semantic_confidence = sum(semantic["confidence_scores"]) / len(semantic["confidence_scores"])
            confidence += avg_semantic_confidence * 0.3
        
        return QueryUnderstanding(
            intent=primary_intent,
            specifications=specifications,
            tone=tone,
            urgency=basic.get("urgency_level", "normal"),
            context_clues=basic.get("tone_indicators", []),
            parsed_features=specifications["features"],
            confidence=min(confidence, 1.0)
        )
    
    def _print_understanding(self, understanding: QueryUnderstanding):
        """Anlayış sonucunu yazdır"""
        print("QUERY UNDERSTANDING:")
        print("-" * 30)
        print(f"Intent: {understanding.intent}")
        print(f"Tone: {understanding.tone}")
        print(f"Urgency: {understanding.urgency}")
        print(f"Confidence: {understanding.confidence:.2f}")
        
        print("\nSPECIFICATIONS:")
        specs = understanding.specifications
        if specs.get("diameter"):
            print(f"  Çap: {specs['diameter']}mm")
        if specs.get("stroke"):
            print(f"  Strok: {specs['stroke']}mm")
        if specs.get("features"):
            print(f"  Özellikler: {', '.join(specs['features'])}")
        if specs.get("brand"):
            print(f"  Marka: {specs['brand']}")
        
        print(f"\nContext Clues: {', '.join(understanding.context_clues)}")
        print("=" * 50)
    
    def generate_smart_response(self, understanding: QueryUnderstanding, products: List[Dict]) -> str:
        """Anlayışa göre akıllı yanıt oluştur"""
        
        # Ton'a göre yanıt tarzı belirle
        greeting = ""
        if understanding.tone == "friendly_informal":
            greetings = ["Tabii canım!", "Elbette kardeşim!", "Hemen bakıyorum dostum!"]
            greeting = greetings[0]  # Simple selection
        else:
            greeting = "Ürün aramanızda yardımcı olayım."
        
        # Specifications'a göre açıklama
        spec_explanation = ""
        specs = understanding.specifications
        if specs.get("diameter") and specs.get("stroke"):
            spec_explanation = f"Aradığınız {specs['diameter']}mm çap, {specs['stroke']}mm strok özelliklerinde"
        elif specs.get("diameter"):
            spec_explanation = f"Aradığınız {specs['diameter']}mm çaplı"
        
        if specs.get("features"):
            feature_text = ", ".join(specs["features"])
            spec_explanation += f" {feature_text} özellikli"
        
        # Urgency'ye göre ton
        urgency_note = ""
        if understanding.urgency == "urgent":
            urgency_note = " Acil ihtiyacınızı anlıyorum."
        
        # Combine
        response_start = f"{greeting} {spec_explanation} silindir için{urgency_note}"
        
        return response_start

# Test fonksiyonu
def test_query_understanding():
    """Query anlama testleri"""
    
    query_rag = QueryRAGSystem()
    
    test_queries = [
        "100 çaplı 400 stroklu magnetli silindir arıyorum canım kardeşim",
        "yastıklamalı silindir lazım acil",
        "MAG marka filtre 5 adet",
        "gürültülü çalışıyor sessiz silindir önerisi", 
        "yüksek basınçta çalışacak dayanıklı ürün",
        "temizlik sektörü için uygun filtre var mı dostum"
    ]
    
    print("QUERY UNDERSTANDING TESTS")
    print("=" * 60)
    
    for query in test_queries:
        understanding = query_rag.understand_query(query)
        print()

if __name__ == "__main__":
    test_query_understanding()
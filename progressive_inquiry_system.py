#!/usr/bin/env python3
"""
Progressive Inquiry System - AI proaktif olarak daha detaylı bilgi ister
"100 çap silindir" → "100mm çaplı x adet var, strok söylersen daha iyi sonuçlar bulurum"
"""

import os
import sys
import chromadb
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import requests
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from query_rag_system import QueryRAGSystem, QueryUnderstanding

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

DB_CONNECTION = "postgresql://postgres:masterkey@localhost:5432/b2b_rag_system"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL_NAME = os.getenv("MODEL", "openai/gpt-3.5-turbo")

@dataclass
class InquiryResponse:
    """Sorgulama yanıt yapısı"""
    response_type: str  # "complete", "needs_clarification", "progressive_inquiry"
    main_response: str
    follow_up_questions: List[str]
    available_options: Dict[str, int]  # "50mm strok": 5 adet
    confidence: float

class ProgressiveInquirySystem:
    """Proaktif bilgi toplama sistemi"""
    
    def __init__(self):
        # Query understanding
        self.query_system = QueryRAGSystem()
        
        # Database connections
        self.db = psycopg2.connect(DB_CONNECTION)
        
        # ChromaDB
        try:
            self.chroma_client = chromadb.PersistentClient(
                path=os.path.join(os.getcwd(), "chroma_db")
            )
            self.collection = self.chroma_client.get_collection("b2b_products")
            print("Progressive Inquiry System hazir!")
        except Exception as e:
            print(f"ChromaDB hatasi: {e}")
    
    def analyze_and_respond(self, user_query: str) -> InquiryResponse:
        """Query'i analiz et ve progressive inquiry yap"""
        
        print(f"\nPROGRESSIVE INQUIRY: '{user_query}'")
        print("=" * 60)
        
        # 1. Query understanding
        understanding = self.query_system.understand_query(user_query)
        
        # 2. Incompleteness detection
        missing_info = self._detect_missing_information(understanding)
        
        # 3. Available options analysis
        available_options = self._analyze_available_options(understanding)
        
        # 4. Decision: Complete answer vs Progressive inquiry
        if missing_info and available_options:
            return self._generate_progressive_inquiry(understanding, missing_info, available_options)
        else:
            return self._generate_complete_response(understanding, available_options)
    
    def _detect_missing_information(self, understanding: QueryUnderstanding) -> List[str]:
        """Eksik bilgileri tespit et"""
        missing = []
        specs = understanding.specifications
        
        # Critical missing information for better search
        if specs.get("diameter") and not specs.get("stroke"):
            missing.append("stroke")
        
        if specs.get("stroke") and not specs.get("diameter"):
            missing.append("diameter")
        
        # Feature specifications missing
        product_categories = ["silindir", "cylinder"]
        if any(cat in understanding.intent.lower() for cat in product_categories):
            if not specs.get("features") or len(specs.get("features", [])) == 0:
                missing.append("features")
        
        # Application area missing for better recommendations
        if understanding.intent == "product_search" and not specs.get("application"):
            missing.append("application")
        
        # Quantity missing for stock planning
        if not specs.get("quantity"):
            missing.append("quantity")
        
        return missing
    
    def _analyze_available_options(self, understanding: QueryUnderstanding) -> Dict[str, Dict]:
        """Mevcut seçenekleri analiz et"""
        try:
            specs = understanding.specifications
            
            # Base search parameters
            search_params = {}
            if specs.get("diameter"):
                search_params["diameter_range"] = (specs["diameter"] - 10, specs["diameter"] + 10)
            if specs.get("brand"):
                search_params["brand"] = specs["brand"]
            
            # Database'den option'ları getir
            options = {}
            
            # Diameter options (if stroke is missing)
            if specs.get("diameter") and not specs.get("stroke"):
                stroke_options = self._get_stroke_options(specs["diameter"], specs.get("brand"))
                options["stroke_options"] = stroke_options
            
            # Stroke options (if diameter is missing)
            if specs.get("stroke") and not specs.get("diameter"):
                diameter_options = self._get_diameter_options(specs["stroke"], specs.get("brand"))
                options["diameter_options"] = diameter_options
            
            # Feature options
            if specs.get("diameter") or specs.get("stroke"):
                feature_options = self._get_feature_options(specs.get("diameter"), specs.get("stroke"))
                options["feature_options"] = feature_options
            
            return options
            
        except Exception as e:
            print(f"Option analysis hatasi: {e}")
            return {}
    
    def _get_stroke_options(self, diameter: int, brand: Optional[str] = None) -> Dict[str, int]:
        """Belirli çap için mevcut strok seçenekleri"""
        try:
            with self.db.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT 
                        p.malzeme_adi,
                        COALESCE(i.current_stock, 0) as stock,
                        COALESCE(b.brand_name, 'Unknown') as brand
                    FROM products p
                    LEFT JOIN inventory i ON p.id = i.product_id  
                    LEFT JOIN brands b ON p.brand_id = b.id
                    WHERE p.malzeme_adi ILIKE %s
                    AND COALESCE(i.current_stock, 0) > 0
                """
                params = [f'%{diameter}%']
                
                if brand:
                    query += " AND b.brand_name ILIKE %s"
                    params.append(f'%{brand}%')
                
                query += " ORDER BY i.current_stock DESC LIMIT 20"
                
                cur.execute(query, params)
                results = cur.fetchall()
                
                # Stroke extraction from product names
                stroke_options = {}
                
                for row in results:
                    product_name = row['malzeme_adi']
                    stock = row['stock']
                    
                    # Extract stroke from product name
                    import re
                    stroke_patterns = [
                        rf'{diameter}[*x×](\d+)',  # 100*200 format
                        rf'{diameter}/(\d+)',     # 100/200 format  
                        r'(\d+)\s*(?:STROK|STROKE|STR)',  # explicit stroke mention
                    ]
                    
                    for pattern in stroke_patterns:
                        matches = re.findall(pattern, product_name.upper())
                        if matches:
                            stroke_value = int(matches[0])
                            stroke_key = f"{stroke_value}mm strok"
                            
                            if stroke_key in stroke_options:
                                stroke_options[stroke_key] += stock
                            else:
                                stroke_options[stroke_key] = stock
                            break
                
                return stroke_options
                
        except Exception as e:
            print(f"Stroke options hatasi: {e}")
            return {}
    
    def _get_diameter_options(self, stroke: int, brand: Optional[str] = None) -> Dict[str, int]:
        """Belirli strok için mevcut çap seçenekleri"""
        try:
            with self.db.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT 
                        p.malzeme_adi,
                        COALESCE(i.current_stock, 0) as stock
                    FROM products p
                    LEFT JOIN inventory i ON p.id = i.product_id
                    LEFT JOIN brands b ON p.brand_id = b.id
                    WHERE p.malzeme_adi ILIKE %s
                    AND COALESCE(i.current_stock, 0) > 0
                """
                params = [f'%{stroke}%']
                
                if brand:
                    query += " AND b.brand_name ILIKE %s"
                    params.append(f'%{brand}%')
                
                query += " ORDER BY i.current_stock DESC LIMIT 20"
                
                cur.execute(query, params)
                results = cur.fetchall()
                
                diameter_options = {}
                
                for row in results:
                    product_name = row['malzeme_adi']
                    stock = row['stock']
                    
                    # Extract diameter
                    import re
                    diameter_patterns = [
                        rf'(\d+)[*x×]{stroke}',  # 100*200 format
                        rf'(\d+)/{stroke}',      # 100/200 format
                        r'Ø(\d+)',               # Ø100 format
                        r'(\d+)\s*(?:ÇAP|ÇAPLI|MM\s*ÇAP)',
                    ]
                    
                    for pattern in diameter_patterns:
                        matches = re.findall(pattern, product_name.upper())
                        if matches:
                            diameter_value = int(matches[0])
                            diameter_key = f"{diameter_value}mm çap"
                            
                            if diameter_key in diameter_options:
                                diameter_options[diameter_key] += stock
                            else:
                                diameter_options[diameter_key] = diameter_value
                            break
                
                return diameter_options
                
        except Exception as e:
            print(f"Diameter options hatasi: {e}")
            return {}
    
    def _get_feature_options(self, diameter: Optional[int], stroke: Optional[int]) -> Dict[str, int]:
        """Boyutlara göre mevcut özellik seçenekleri"""
        try:
            # ChromaDB'de benzer ürünleri ara
            query_parts = []
            if diameter:
                query_parts.append(f"{diameter}mm")
            if stroke:
                query_parts.append(f"{stroke}mm")
            query_parts.append("silindir")
            
            search_query = " ".join(query_parts)
            
            results = self.collection.query(
                query_texts=[search_query],
                n_results=15,
                where={"stock": {"$gte": 0.1}}
            )
            
            feature_options = {}
            
            if results['documents'] and results['documents'][0]:
                for doc in results['documents'][0]:
                    doc_upper = doc.upper()
                    
                    # Feature detection
                    if any(kw in doc_upper for kw in ['MANYETIK', 'MAGNETIC', 'SENSÖR']):
                        feature_options["Manyetik sensörlü"] = feature_options.get("Manyetik sensörlü", 0) + 1
                    
                    if any(kw in doc_upper for kw in ['YASTIK', 'CUSHION', 'YUMUŞAK']):
                        feature_options["Yastıklamalı"] = feature_options.get("Yastıklamalı", 0) + 1
                    
                    if any(kw in doc_upper for kw in ['İSO', 'STANDARD']):
                        feature_options["ISO standart"] = feature_options.get("ISO standart", 0) + 1
            
            return feature_options
            
        except Exception as e:
            print(f"Feature options hatasi: {e}")
            return {}
    
    def _generate_progressive_inquiry(self, understanding: QueryUnderstanding, missing_info: List[str], available_options: Dict) -> InquiryResponse:
        """Progressive inquiry yanıtı oluştur"""
        
        specs = understanding.specifications
        tone = understanding.tone
        
        # Ton'a göre yaklaşım
        if tone == "friendly_informal":
            greeting = "Hmm, "
            ending = " der misin? Böylece sana en uygun ürünü bulabilirim!"
        else:
            greeting = "İyi bir arama için "
            ending = " belirtirseniz daha hassas sonuçlar bulabilirim."
        
        main_response_parts = []
        follow_up_questions = []
        
        # Diameter varsa, stroke yoksa
        if specs.get("diameter") and "stroke" in missing_info:
            diameter = specs["diameter"]
            stroke_options = available_options.get("stroke_options", {})
            
            if stroke_options:
                count = len(stroke_options)
                total_stock = sum(stroke_options.values())
                
                main_response_parts.append(
                    f"{greeting}{diameter}mm çaplı silindir için {count} farklı strok seçeneği var (toplam {total_stock} adet stokta)."
                )
                
                # En popüler stroke seçeneklerini göster
                top_strokes = sorted(stroke_options.items(), key=lambda x: x[1], reverse=True)[:3]
                options_text = ", ".join([f"{stroke} ({count} adet)" for stroke, count in top_strokes])
                
                main_response_parts.append(f"Popüler seçenekler: {options_text}")
                follow_up_questions.append(f"Hangi strok uzunluğunu tercih edersiniz?{ending}")
        
        # Stroke varsa, diameter yoksa
        elif specs.get("stroke") and "diameter" in missing_info:
            stroke = specs["stroke"]
            diameter_options = available_options.get("diameter_options", {})
            
            if diameter_options:
                count = len(diameter_options)
                
                main_response_parts.append(
                    f"{greeting}{stroke}mm stroklu silindir için {count} farklı çap seçeneği bulunuyor."
                )
                
                top_diameters = list(diameter_options.keys())[:3]
                options_text = ", ".join(top_diameters)
                
                main_response_parts.append(f"Mevcut çaplar: {options_text}")
                follow_up_questions.append(f"Hangi çapı tercih edersiniz?{ending}")
        
        # Sadece genel "silindir" araması
        elif not specs.get("diameter") and not specs.get("stroke"):
            main_response_parts.append(
                f"{greeting}silindir aramanız için daha spesifik bilgiye ihtiyacım var."
            )
            follow_up_questions.extend([
                f"Çap (örn: 100mm) söylerseniz{ending}",
                f"Strok uzunluğu (örn: 200mm) belirtirseniz{ending}"
            ])
        
        # Feature önerileri
        if available_options.get("feature_options"):
            feature_opts = available_options["feature_options"]
            if len(feature_opts) > 1:
                features_text = ", ".join(feature_opts.keys())
                follow_up_questions.append(f"Özel özellik tercihiniz var mı? ({features_text})")
        
        main_response = " ".join(main_response_parts)
        
        return InquiryResponse(
            response_type="progressive_inquiry",
            main_response=main_response,
            follow_up_questions=follow_up_questions,
            available_options=available_options,
            confidence=0.8
        )
    
    def _generate_complete_response(self, understanding: QueryUnderstanding, available_options: Dict) -> InquiryResponse:
        """Tam bilgiye sahipse normal yanıt"""
        
        # Normal ürün araması yap
        try:
            specs = understanding.specifications
            query_parts = []
            
            if specs.get("diameter"):
                query_parts.append(f"{specs['diameter']}mm")
            if specs.get("stroke"):
                query_parts.append(f"{specs['stroke']}mm")
            if specs.get("features"):
                query_parts.extend(specs["features"])
            
            query_parts.append("silindir")
            search_query = " ".join(query_parts)
            
            results = self.collection.query(
                query_texts=[search_query],
                n_results=5,
                where={"stock": {"$gte": 0.1}}
            )
            
            if results['documents'] and results['documents'][0]:
                count = len(results['documents'][0])
                
                # İlk ürünün detayları
                first_product = results['documents'][0][0]
                first_meta = results['metadatas'][0][0]
                product_name = first_product.split('\n')[0].replace('ÜRÜN: ', '')
                
                response = f"Aramanıza uygun {count} ürün buldum. En uygun seçenek: {product_name} ({first_meta['brand']} - {first_meta['stock']:.0f} adet stokta)"
                
                return InquiryResponse(
                    response_type="complete",
                    main_response=response,
                    follow_up_questions=[],
                    available_options=available_options,
                    confidence=0.9
                )
            else:
                return InquiryResponse(
                    response_type="complete",
                    main_response="Belirttiğiniz özelliklerde ürün bulunamadı.",
                    follow_up_questions=["Farklı özellikler deneyebilirsiniz."],
                    available_options={},
                    confidence=0.3
                )
                
        except Exception as e:
            return InquiryResponse(
                response_type="complete", 
                main_response=f"Arama hatası: {e}",
                follow_up_questions=[],
                available_options={},
                confidence=0.1
            )
    
    def print_inquiry_response(self, response: InquiryResponse):
        """Inquiry response'ı yazdır"""
        print("\nPROGRESSIVE INQUIRY RESPONSE:")
        print("-" * 40)
        print(f"Type: {response.response_type}")
        print(f"Confidence: {response.confidence:.2f}")
        
        print(f"\nMain Response:")
        print(response.main_response)
        
        if response.follow_up_questions:
            print(f"\nFollow-up Questions:")
            for i, question in enumerate(response.follow_up_questions, 1):
                print(f"{i}. {question}")
        
        if response.available_options:
            print(f"\nAvailable Options:")
            for category, options in response.available_options.items():
                print(f"  {category}: {len(options) if isinstance(options, dict) else options}")

def test_progressive_inquiry():
    """Progressive inquiry testleri"""
    
    inquiry_system = ProgressiveInquirySystem()
    
    test_queries = [
        "100 çap silindir",  # Missing stroke
        "100 lük silindir arıyorum",  # Missing stroke, informal
        "400 stroklu silindir lazım",  # Missing diameter
        "silindir arıyorum",  # Missing both
        "100 çap 200 strok silindir",  # Complete
        "manyetik sensörlü 100mm çap silindir",  # Missing stroke but has feature
    ]
    
    print("PROGRESSIVE INQUIRY SYSTEM TESTS")
    print("=" * 60)
    
    for query in test_queries:
        response = inquiry_system.analyze_and_respond(query)
        inquiry_system.print_inquiry_response(response)
        print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    test_progressive_inquiry()
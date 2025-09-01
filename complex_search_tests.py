#!/usr/bin/env python3
"""
Complex Search Test Scenarios - RAG System Advanced Testing
Gerçek dünya B2B senaryoları ile kapsamlı test
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
import chromadb
from dotenv import load_dotenv
import requests
import json
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass

load_dotenv()

# Configuration
DB_CONNECTION = "postgresql://postgres:masterkey@localhost:5432/b2b_rag_system"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL_NAME = os.getenv("MODEL", "openai/gpt-3.5-turbo")

@dataclass
class TestScenario:
    """Test senaryosu"""
    name: str
    user_message: str
    expected_features: List[str]
    success_criteria: str
    difficulty_level: int  # 1-5

@dataclass
class SearchResult:
    """Arama sonucu"""
    products_found: int
    relevant_products: int
    ai_response: str
    execution_time: float
    test_passed: bool
    notes: str

class ComplexSearchTester:
    """Karmaşık arama senaryoları test sistemi"""
    
    def __init__(self):
        # Database
        self.db = psycopg2.connect(DB_CONNECTION)
        
        # ChromaDB
        try:
            self.chroma_client = chromadb.PersistentClient(
                path=os.path.join(os.getcwd(), "chroma_db")
            )
            self.collection = self.chroma_client.get_collection("b2b_products")
            print(f"ChromaDB yüklendi: {self.collection.count()} doküman")
        except Exception as e:
            print(f"ChromaDB hatası: {e}")
            self.collection = None
            
        # Test senaryoları - gerçek dünya örnekleri
        self.scenarios = [
            # Level 1: Basit ürün bulma
            TestScenario(
                name="Basit Silindir Arama",
                user_message="silindir arıyorum",
                expected_features=["silindir"],
                success_criteria="En az 3 silindir ürünü bulmalı",
                difficulty_level=1
            ),
            
            # Level 2: Özellik bazlı arama
            TestScenario(
                name="Özellik Spesifik Arama", 
                user_message="manyetik sensörlü silindir lazım",
                expected_features=["magnetic", "sensor", "silindir"],
                success_criteria="Manyetik özellikli ürünler bulmalı",
                difficulty_level=2
            ),
            
            TestScenario(
                name="Yumuşak Durma Özelliği",
                user_message="yastıklamalı silindir istiyorum",
                expected_features=["yastık", "cushion", "silindir"],
                success_criteria="Yastıklamalı silindir ürünleri bulmalı",
                difficulty_level=2
            ),
            
            # Level 3: Multi-kriterli arama
            TestScenario(
                name="Boyut ve Özellik Kombinasyonu",
                user_message="100mm çapında yastıklamalı silindir",
                expected_features=["100", "yastık", "silindir"],
                success_criteria="Boyut ve özellik kombinasyonu bulmalı",
                difficulty_level=3
            ),
            
            TestScenario(
                name="Marka ve Özellik",
                user_message="MAG marka filtre ürünü",
                expected_features=["MAG", "filtre"],
                success_criteria="MAG markasında filtre bulmalı",
                difficulty_level=3
            ),
            
            # Level 4: Teknik ve karmaşık sorgular
            TestScenario(
                name="Çoklu Özellik Sorgusu",
                user_message="yağ dirençli, sessiz çalışan, manyetik sensörlü silindir",
                expected_features=["yağ", "sessiz", "manyetik", "silindir"],
                success_criteria="Çoklu teknik özellikleri anlayabilmeli",
                difficulty_level=4
            ),
            
            TestScenario(
                name="Performans Bazlı Arama",
                user_message="yüksek basınca dayanıklı, uzun ömürlü silindir",
                expected_features=["basınç", "dayanık", "silindir"],
                success_criteria="Performans kriterlerini anlayabilmeli",
                difficulty_level=4
            ),
            
            # Level 5: En karmaşık senaryolar
            TestScenario(
                name="Doğal Dil Karmaşık Sorgu",
                user_message="Temizlik sektöründe kullanabileceğim, yüksek devirde çalışan, titreşimi az olan silindir var mı?",
                expected_features=["temizlik", "yüksek devir", "titreşim", "silindir"],
                success_criteria="Doğal dil ve sektör spesifik analiz",
                difficulty_level=5
            ),
            
            TestScenario(
                name="Problem Çözme Odaklı",
                user_message="Makinemde aşırı gürültü var, sessiz çalışacak alternatif silindir önerisi",
                expected_features=["gürültü", "sessiz", "alternatif", "silindir"],
                success_criteria="Problem analizi ve çözüm önerisi",
                difficulty_level=5
            ),
            
            # Özel kategoriler
            TestScenario(
                name="Filtre Kategorisi Test",
                user_message="hava filtresine ihtiyacım var",
                expected_features=["hava", "filtre"],
                success_criteria="Filtre kategorisindeki ürünleri bulmalı",
                difficulty_level=2
            ),
            
            TestScenario(
                name="Valf Kategorisi Test", 
                user_message="akış kontrol valfi arıyorum",
                expected_features=["akış", "kontrol", "valf"],
                success_criteria="Valf kategorisindeki ürünleri bulmalı",
                difficulty_level=2
            )
        ]
    
    def search_with_rag(self, query: str, limit: int = 10) -> Tuple[List[Dict], float]:
        """RAG ile arama yap"""
        import time
        
        if not self.collection:
            return [], 0.0
            
        start_time = time.time()
        
        try:
            # Vector search
            results = self.collection.query(
                query_texts=[query],
                n_results=limit,
                where={"stock": {"$gte": 0.1}}
            )
            
            products = []
            if results['documents'] and results['documents'][0]:
                for i, doc in enumerate(results['documents'][0]):
                    metadata = results['metadatas'][0][i]
                    
                    # Parse product name from document
                    product_name = doc.split('\n')[0].replace('ÜRÜN: ', '')
                    
                    products.append({
                        'id': metadata['product_id'],
                        'malzeme_kodu': metadata['malzeme_kodu'],
                        'malzeme_adi': product_name,
                        'brand_name': metadata['brand'],
                        'current_stock': metadata['stock'],
                        'category_name': metadata['category'],
                        'similarity_score': 1 - results['distances'][0][i],
                        'full_content': doc
                    })
            
            execution_time = time.time() - start_time
            return products, execution_time
            
        except Exception as e:
            print(f"RAG arama hatası: {e}")
            return [], time.time() - start_time
    
    def generate_ai_response(self, query: str, products: List[Dict]) -> str:
        """AI ile akıllı yanıt oluştur"""
        if not products:
            return "Uygun ürün bulunamadı."
            
        # Context hazırla
        context = "BULUNAN ÜRÜNLER:\\n\\n"
        for i, product in enumerate(products[:5], 1):
            context += f"{i}. ÜRÜN: {product['malzeme_adi']}\\n"
            context += f"   MARKA: {product['brand_name']}\\n"
            context += f"   KOD: {product['malzeme_kodu']}\\n"
            context += f"   STOK: {product['current_stock']:.0f} adet\\n"
            if 'similarity_score' in product:
                context += f"   UYGUNLUK: {product['similarity_score']:.2f}\\n"
            context += "\\n"
        
        # AI prompt
        messages = [
            {
                "role": "system", 
                "content": """Sen B2B endüstriyel ürün uzmanısın. Müşteri taleplerini anlayıp en uygun ürünleri öner.
                
Görevlerin:
1. Müşteri ihtiyacını analiz et
2. En uygun ürünü belirle
3. Teknik özellikleri açıkla
4. Alternatifleri öner
5. Stok durumu bilgisi ver
6. Professional ama samimi dilde yanıtla"""
            },
            {
                "role": "user",
                "content": f"MÜŞTERİ TALEBİ: {query}\\n\\n{context}\\n\\nYukarıdaki ürünler arasından en uygun olanı öner ve nedenini detaylı açıkla."
            }
        ]
        
        try:
            headers = {
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            }
            
            data = {
                "model": MODEL_NAME,
                "messages": messages,
                "temperature": 0.4,
                "max_tokens": 400
            }
            
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=15
            )
            
            if response.status_code == 200:
                return response.json()['choices'][0]['message']['content']
            else:
                return f"AI hatası: {response.status_code}"
                
        except Exception as e:
            return f"AI bağlantı hatası: {e}"
    
    def evaluate_results(self, scenario: TestScenario, products: List[Dict], ai_response: str) -> Tuple[bool, str]:
        """Sonuçları değerlendir"""
        notes = []
        
        # 1. Ürün sayısı kontrol
        if not products:
            return False, "Hiç ürün bulunamadı"
        
        # 2. Expected features kontrolü
        found_features = []
        all_text = " ".join([
            p['malzeme_adi'] + " " + p['brand_name'] + " " + p['category_name'] 
            for p in products
        ]).upper()
        
        for feature in scenario.expected_features:
            if feature.upper() in all_text:
                found_features.append(feature)
        
        feature_score = len(found_features) / len(scenario.expected_features)
        notes.append(f"Feature coverage: {feature_score:.2f} ({found_features})")
        
        # 3. Relevance check
        relevant_count = 0
        for product in products[:5]:  # Top 5 kontrolü
            product_text = f"{product['malzeme_adi']} {product['brand_name']}".upper()
            if any(feat.upper() in product_text for feat in scenario.expected_features):
                relevant_count += 1
        
        relevance_score = relevant_count / min(5, len(products))
        notes.append(f"Relevance: {relevance_score:.2f} ({relevant_count}/{min(5, len(products))})")
        
        # 4. AI response quality
        ai_quality = self.evaluate_ai_response(ai_response, scenario.expected_features)
        notes.append(f"AI quality: {ai_quality:.2f}")
        
        # 5. Overall scoring
        overall_score = (feature_score * 0.4) + (relevance_score * 0.4) + (ai_quality * 0.2)
        
        # Success criteria
        success_threshold = max(0.6 - (scenario.difficulty_level * 0.1), 0.3)  # Harder tests, lower threshold
        test_passed = overall_score >= success_threshold
        
        notes.append(f"Overall score: {overall_score:.2f} (threshold: {success_threshold:.2f})")
        
        return test_passed, " | ".join(notes)
    
    def evaluate_ai_response(self, ai_response: str, expected_features: List[str]) -> float:
        """AI yanıtının kalitesini değerlendir"""
        if not ai_response or "hata" in ai_response.lower():
            return 0.0
        
        # Feature mention check
        mentioned_features = sum(1 for feat in expected_features if feat.lower() in ai_response.lower())
        feature_ratio = mentioned_features / len(expected_features)
        
        # Response length check (reasonable length)
        length_score = min(len(ai_response) / 200, 1.0)
        
        # Professional keywords
        professional_keywords = ["öner", "uygun", "özellik", "stok", "marka", "ürün"]
        professional_score = sum(1 for kw in professional_keywords if kw in ai_response.lower()) / len(professional_keywords)
        
        return (feature_ratio * 0.5) + (length_score * 0.2) + (professional_score * 0.3)
    
    def run_test_scenario(self, scenario: TestScenario) -> SearchResult:
        """Tek senaryo test et"""
        print(f"\\n{'='*20} {scenario.name} {'='*20}")
        print(f"Level {scenario.difficulty_level}: {scenario.user_message}")
        print(f"Expected: {', '.join(scenario.expected_features)}")
        print("-" * 60)
        
        # RAG search
        products, search_time = self.search_with_rag(scenario.user_message)
        
        print(f"Arama süresi: {search_time:.3f}s")
        print(f"Bulunan ürün sayısı: {len(products)}")
        
        # Show top results
        if products:
            print("\\nİlk 3 sonuç:")
            for i, product in enumerate(products[:3], 1):
                similarity = product.get('similarity_score', 0)
                print(f"  {i}. {product['malzeme_adi']} ({product['brand_name']}) - Similarity: {similarity:.3f}")
        
        # AI response
        ai_response = self.generate_ai_response(scenario.user_message, products)
        print(f"\\nAI Yanıt: {ai_response[:150]}...")
        
        # Evaluation
        test_passed, notes = self.evaluate_results(scenario, products, ai_response)
        
        print(f"\\nSonuç: {'PASSED' if test_passed else 'FAILED'}")
        print(f"Değerlendirme: {notes}")
        
        return SearchResult(
            products_found=len(products),
            relevant_products=sum(1 for p in products if any(feat.upper() in p['malzeme_adi'].upper() for feat in scenario.expected_features)),
            ai_response=ai_response,
            execution_time=search_time,
            test_passed=test_passed,
            notes=notes
        )
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Tüm testleri çalıştır"""
        print("COMPLEX SEARCH TEST SUITE")
        print("=" * 60)
        
        results = {}
        passed_tests = 0
        total_tests = len(self.scenarios)
        
        # Level'a göre grupla
        by_level = {}
        for scenario in self.scenarios:
            level = scenario.difficulty_level
            if level not in by_level:
                by_level[level] = []
            by_level[level].append(scenario)
        
        # Her level'ı test et
        for level in sorted(by_level.keys()):
            level_scenarios = by_level[level]
            level_passed = 0
            
            print(f"\\nLEVEL {level} TESTS ({len(level_scenarios)} test)")
            print("=" * 60)
            
            for scenario in level_scenarios:
                result = self.run_test_scenario(scenario)
                results[scenario.name] = result
                
                if result.test_passed:
                    passed_tests += 1
                    level_passed += 1
            
            print(f"\\nLevel {level} Sonuç: {level_passed}/{len(level_scenarios)} passed")
        
        # Overall summary
        print("\\n" + "=" * 60)
        print("FINAL SUMMARY")
        print("=" * 60)
        print(f"Toplam: {passed_tests}/{total_tests} test passed ({passed_tests/total_tests*100:.1f}%)")
        
        # Level breakdown
        for level in sorted(by_level.keys()):
            level_scenarios = by_level[level]
            level_passed = sum(1 for s in level_scenarios if results[s.name].test_passed)
            print(f"Level {level}: {level_passed}/{len(level_scenarios)} ({level_passed/len(level_scenarios)*100:.1f}%)")
        
        # Performance stats
        avg_search_time = sum(r.execution_time for r in results.values()) / len(results)
        print(f"\\nOrtalama arama süresi: {avg_search_time:.3f}s")
        
        return {
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'success_rate': passed_tests / total_tests,
            'avg_search_time': avg_search_time,
            'results_by_test': results,
            'results_by_level': {level: [results[s.name] for s in scenarios] for level, scenarios in by_level.items()}
        }

def main():
    """Ana test fonksiyonu"""
    tester = ComplexSearchTester()
    
    if not tester.collection:
        print("ChromaDB bulunamadı! Önce rag_enhanced.py çalıştırın.")
        return
        
    # Tüm testleri çalıştır
    final_results = tester.run_all_tests()
    
    print("\\nTest suite tamamlandi!")

if __name__ == "__main__":
    main()
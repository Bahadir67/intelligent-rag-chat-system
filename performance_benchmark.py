#!/usr/bin/env python3
"""
Performance Benchmark: RAG vs SQL Approaches
Karşılaştırma testi - Semantic search vs Pattern matching
"""

import time
import psycopg2
from psycopg2.extras import RealDictCursor
import chromadb
from dotenv import load_dotenv
import os
import requests
import statistics
from typing import List, Dict, Tuple
from dataclasses import dataclass

load_dotenv()

# Configuration
DB_CONNECTION = "postgresql://postgres:masterkey@localhost:5432/b2b_rag_system"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL_NAME = os.getenv("MODEL", "openai/gpt-3.5-turbo")

@dataclass
class BenchmarkResult:
    """Benchmark sonucu"""
    method: str
    query: str
    execution_time: float
    result_count: int
    relevant_results: int
    precision: float
    ai_response_time: float = 0.0

class RAGBenchmark:
    """RAG vs SQL performance karşılaştırması"""
    
    def __init__(self):
        # PostgreSQL connection
        self.db = psycopg2.connect(DB_CONNECTION)
        
        # ChromaDB connection
        try:
            self.chroma_client = chromadb.PersistentClient(
                path=os.path.join(os.getcwd(), "chroma_db")
            )
            self.collection = self.chroma_client.get_collection("b2b_products")
            print(f"ChromaDB loaded: {self.collection.count()} documents")
        except:
            print("ChromaDB bulunamadı - önce rag_enhanced.py çalıştırın")
            self.collection = None
        
        # Test queries - gerçek dünya senaryoları
        self.test_queries = [
            # Basit ürün aramaları
            {
                "query": "silindir", 
                "description": "Genel silindir arama",
                "expected_keywords": ["silindir", "cylinder"]
            },
            {
                "query": "100mm silindir", 
                "description": "Boyut spesifik arama",
                "expected_keywords": ["100", "silindir"]
            },
            
            # Semantic search avantajlı durumlar
            {
                "query": "yastıklamalı silindir lazım", 
                "description": "Doğal dil sorgu",
                "expected_keywords": ["yast", "cushion", "silindir"]
            },
            {
                "query": "sessiz çalışan silindir", 
                "description": "Özellik tabanlı arama",
                "expected_keywords": ["yast", "sessiz", "noise"]
            },
            {
                "query": "manyetik sensörlü silindir", 
                "description": "Teknik özellik arama",
                "expected_keywords": ["mag", "magnetic", "sensör"]
            },
            
            # Marka ve kategori aramaları
            {
                "query": "MAG marka filtre", 
                "description": "Marka spesifik arama",
                "expected_keywords": ["mag", "filtre"]
            },
            {
                "query": "yüksek basınca dayanıklı", 
                "description": "Performans özelliği",
                "expected_keywords": ["basınç", "dayanık", "pressure"]
            },
            
            # Karmaşık sorular
            {
                "query": "yağ dirençli, sessiz çalışan 100mm silindir", 
                "description": "Multi-feature sorgu",
                "expected_keywords": ["100", "silindir", "yağ", "sessiz"]
            }
        ]
    
    def sql_search(self, query: str, limit: int = 10) -> Tuple[List[Dict], float]:
        """Geleneksel SQL pattern matching arama"""
        start_time = time.time()
        
        # Basit keyword extraction
        keywords = query.upper().split()
        
        with self.db.cursor(cursor_factory=RealDictCursor) as cur:
            # ILIKE pattern matching
            where_conditions = []
            params = []
            
            for keyword in keywords:
                where_conditions.append("(p.malzeme_adi ILIKE %s OR COALESCE(b.brand_name, '') ILIKE %s)")
                params.extend([f'%{keyword}%', f'%{keyword}%'])
            
            where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
            
            sql_query = f"""
                SELECT 
                    p.id, p.malzeme_kodu, p.malzeme_adi,
                    COALESCE(b.brand_name, 'Unknown') as brand_name,
                    COALESCE(i.current_stock, 0) as current_stock,
                    COALESCE(pc.category_name, 'Genel') as category_name
                FROM products p
                LEFT JOIN brands b ON p.brand_id = b.id
                LEFT JOIN inventory i ON p.id = i.product_id
                LEFT JOIN product_categories pc ON p.category_id = pc.id
                WHERE {where_clause}
                AND COALESCE(i.current_stock, 0) > 0
                ORDER BY i.current_stock DESC
                LIMIT %s
            """
            params.append(limit)
            
            cur.execute(sql_query, params)
            results = cur.fetchall()
            
            execution_time = time.time() - start_time
            return [dict(row) for row in results], execution_time
    
    def rag_search(self, query: str, limit: int = 10) -> Tuple[List[Dict], float]:
        """ChromaDB semantic search"""
        if not self.collection:
            return [], 0.0
            
        start_time = time.time()
        
        # Vector search
        chroma_results = self.collection.query(
            query_texts=[query],
            n_results=limit,
            where={"stock": {"$gte": 0.1}}  # Stokta olanları filtrele
        )
        
        results = []
        if chroma_results['documents'] and chroma_results['documents'][0]:
            for i, doc in enumerate(chroma_results['documents'][0]):
                metadata = chroma_results['metadatas'][0][i]
                results.append({
                    'id': metadata['product_id'],
                    'malzeme_kodu': metadata['malzeme_kodu'],
                    'malzeme_adi': doc.split('\n')[0].replace('ÜRÜN: ', ''),
                    'brand_name': metadata['brand'],
                    'current_stock': metadata['stock'],
                    'category_name': metadata['category'],
                    'similarity_score': 1 - chroma_results['distances'][0][i]
                })
        
        execution_time = time.time() - start_time
        return results, execution_time
    
    def calculate_relevance(self, results: List[Dict], expected_keywords: List[str]) -> Tuple[int, float]:
        """Sonuçların relevance skorunu hesapla"""
        relevant_count = 0
        
        for result in results:
            product_text = f"{result['malzeme_adi']} {result['brand_name']}".upper()
            
            # En az bir expected keyword varsa relevant sayılır
            if any(keyword.upper() in product_text for keyword in expected_keywords):
                relevant_count += 1
        
        precision = relevant_count / len(results) if results else 0
        return relevant_count, precision
    
    def generate_ai_response(self, query: str, results: List[Dict]) -> float:
        """AI response generation time test"""
        if not results:
            return 0.0
            
        start_time = time.time()
        
        # Context hazırla
        context = "BULUNAN ÜRÜNLER:\n"
        for i, result in enumerate(results[:3], 1):
            context += f"{i}. {result['malzeme_adi']} - {result['brand_name']} "
            context += f"(Stok: {result['current_stock']:.0f})\n"
        
        # AI prompt
        messages = [
            {
                "role": "system",
                "content": "B2B ürün uzmanısın. Kısa ve teknik cevap ver."
            },
            {
                "role": "user", 
                "content": f"Soru: {query}\n\n{context}\n\nEn uygun ürünü kısaca öner."
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
                "temperature": 0.3,
                "max_tokens": 150
            }
            
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=10
            )
            
            ai_time = time.time() - start_time
            return ai_time
            
        except Exception as e:
            print(f"AI response hatası: {e}")
            return time.time() - start_time
    
    def run_benchmark(self) -> List[BenchmarkResult]:
        """Tam benchmark çalıştır"""
        results = []
        
        print("RAG vs SQL Performance Benchmark")
        print("=" * 50)
        
        for i, test_case in enumerate(self.test_queries, 1):
            query = test_case["query"]
            description = test_case["description"]
            expected_keywords = test_case["expected_keywords"]
            
            print(f"\n{i}. Test: {description}")
            print(f"   Query: '{query}'")
            print("-" * 30)
            
            # SQL Test
            try:
                sql_results, sql_time = self.sql_search(query)
                sql_relevant, sql_precision = self.calculate_relevance(sql_results, expected_keywords)
                sql_ai_time = self.generate_ai_response(query, sql_results)
                
                sql_benchmark = BenchmarkResult(
                    method="SQL",
                    query=query,
                    execution_time=sql_time,
                    result_count=len(sql_results),
                    relevant_results=sql_relevant,
                    precision=sql_precision,
                    ai_response_time=sql_ai_time
                )
                results.append(sql_benchmark)
                
                print(f"   SQL: {sql_time:.3f}s, {len(sql_results)} sonuç, {sql_precision:.2f} precision")
                
            except Exception as e:
                print(f"   SQL Error: {e}")
            
            # RAG Test
            try:
                rag_results, rag_time = self.rag_search(query)
                rag_relevant, rag_precision = self.calculate_relevance(rag_results, expected_keywords)
                rag_ai_time = self.generate_ai_response(query, rag_results)
                
                rag_benchmark = BenchmarkResult(
                    method="RAG",
                    query=query,
                    execution_time=rag_time,
                    result_count=len(rag_results),
                    relevant_results=rag_relevant,
                    precision=rag_precision,
                    ai_response_time=rag_ai_time
                )
                results.append(rag_benchmark)
                
                print(f"   RAG: {rag_time:.3f}s, {len(rag_results)} sonuç, {rag_precision:.2f} precision")
                
                # Similarity score info for RAG
                if rag_results and 'similarity_score' in rag_results[0]:
                    avg_similarity = statistics.mean([r['similarity_score'] for r in rag_results])
                    print(f"   RAG Avg Similarity: {avg_similarity:.3f}")
                
            except Exception as e:
                print(f"   RAG Error: {e}")
        
        return results
    
    def analyze_results(self, results: List[BenchmarkResult]):
        """Sonuçları analiz et ve raporla"""
        print("\n" + "=" * 50)
        print("BENCHMARK ANALIZI")
        print("=" * 50)
        
        # Method'a göre grupla
        sql_results = [r for r in results if r.method == "SQL"]
        rag_results = [r for r in results if r.method == "RAG"]
        
        if sql_results:
            print("\nSQL Pattern Matching:")
            sql_avg_time = statistics.mean([r.execution_time for r in sql_results])
            sql_avg_precision = statistics.mean([r.precision for r in sql_results])
            sql_avg_ai_time = statistics.mean([r.ai_response_time for r in sql_results])
            
            print(f"   Ortalama Arama Süresi: {sql_avg_time:.3f}s")
            print(f"   Ortalama Precision: {sql_avg_precision:.2f}")
            print(f"   Ortalama AI Response: {sql_avg_ai_time:.3f}s")
            print(f"   Toplam Süre: {sql_avg_time + sql_avg_ai_time:.3f}s")
        
        if rag_results:
            print("\nRAG Semantic Search:")
            rag_avg_time = statistics.mean([r.execution_time for r in rag_results])
            rag_avg_precision = statistics.mean([r.precision for r in rag_results])
            rag_avg_ai_time = statistics.mean([r.ai_response_time for r in rag_results])
            
            print(f"   Ortalama Arama Süresi: {rag_avg_time:.3f}s")
            print(f"   Ortalama Precision: {rag_avg_precision:.2f}")
            print(f"   Ortalama AI Response: {rag_avg_ai_time:.3f}s")
            print(f"   Toplam Süre: {rag_avg_time + rag_avg_ai_time:.3f}s")
        
        # Karşılaştırma
        if sql_results and rag_results:
            print("\nKARSILASTIRMA:")
            
            speed_diff = sql_avg_time - rag_avg_time
            if speed_diff > 0:
                print(f"   RAG {speed_diff:.3f}s daha hızlı")
            else:
                print(f"   SQL {abs(speed_diff):.3f}s daha hızlı")
            
            precision_diff = rag_avg_precision - sql_avg_precision
            if precision_diff > 0:
                print(f"   RAG precision {precision_diff:.2f} daha yüksek")
            else:
                print(f"   SQL precision {abs(precision_diff):.2f} daha yüksek")
        
        # Query-specific insights
        print("\nQUERY BAZLI ANALIZ:")
        
        query_pairs = {}
        for result in results:
            if result.query not in query_pairs:
                query_pairs[result.query] = {}
            query_pairs[result.query][result.method] = result
        
        for query, methods in query_pairs.items():
            if "SQL" in methods and "RAG" in methods:
                sql_r = methods["SQL"]
                rag_r = methods["RAG"]
                
                print(f"\n   '{query}':")
                print(f"   SQL: {sql_r.execution_time:.3f}s, {sql_r.precision:.2f} precision")
                print(f"   RAG: {rag_r.execution_time:.3f}s, {rag_r.precision:.2f} precision")
                
                if rag_r.precision > sql_r.precision:
                    print(f"   -> RAG daha relevant sonuclar veriyor")

def main():
    """Ana benchmark fonksiyonu"""
    benchmark = RAGBenchmark()
    
    # Warmup
    print("Warmup runs...")
    benchmark.sql_search("test")
    if benchmark.collection:
        benchmark.rag_search("test")
    
    # Gerçek benchmark
    results = benchmark.run_benchmark()
    
    # Analiz
    benchmark.analyze_results(results)
    
    print("\nBenchmark tamamlandi!")

if __name__ == "__main__":
    main()
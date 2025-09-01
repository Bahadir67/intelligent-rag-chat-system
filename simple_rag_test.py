#!/usr/bin/env python3
"""
Simple RAG Test - Sadece birkaç ürün ile test
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
import chromadb
import requests
from dotenv import load_dotenv

load_dotenv()

DB_CONNECTION = "postgresql://postgres:masterkey@localhost:5432/b2b_rag_system"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL_NAME = os.getenv("MODEL", "openai/gpt-3.5-turbo")

def create_simple_rag():
    """Basit RAG sistemi - 10 ürün ile test"""
    
    # ChromaDB setup
    client = chromadb.EphemeralClient()  # Memory-only, no file issues
    collection = client.create_collection("test_products")
    
    # PostgreSQL'den 10 ürün al
    conn = psycopg2.connect(DB_CONNECTION)
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT 
                p.id, p.malzeme_kodu, p.malzeme_adi,
                COALESCE(b.brand_name, 'Unknown') as brand_name,
                COALESCE(i.current_stock, 0) as current_stock
            FROM products p
            LEFT JOIN brands b ON p.brand_id = b.id
            LEFT JOIN inventory i ON p.id = i.product_id
            WHERE p.malzeme_adi ILIKE '%silindir%' 
            AND i.current_stock > 0
            LIMIT 10
        """)
        
        products = cur.fetchall()
        print(f"Found {len(products)} products for RAG test")
        
        # Create rich documents
        documents = []
        metadatas = []
        ids = []
        
        for product in products:
            # Rich content
            content = f"""
            ÜRÜN: {product['malzeme_adi']}
            MARKA: {product['brand_name']}
            KOD: {product['malzeme_kodu']}
            STOK: {product['current_stock']:.0f} adet
            
            ÖZELLİKLER:
            - Endüstriyel silindir
            - Pnömatik tahrik sistemi
            """
            
            if 'YAST' in product['malzeme_adi'].upper():
                content += "- Yastıklamalı (yumuşak durma)\n- Titreşim azaltma\n"
            if 'MAG' in product['malzeme_adi'].upper():
                content += "- Manyetik sensör destekli\n- Konum geri bildirimi\n"
            
            content += """
            UYGULAMA:
            - Endüstriyel otomasyon
            - Materyel transfer
            - Konumlandırma sistemleri
            """
            
            documents.append(content.strip())
            metadatas.append({
                "product_id": product['id'],
                "brand": str(product['brand_name']),
                "stock": float(product['current_stock']),
                "malzeme_kodu": str(product['malzeme_kodu'])
            })
            ids.append(f"product_{product['id']}")
        
        # Index to ChromaDB
        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        
        print("ChromaDB indexing completed!")
        return collection

def test_rag_search(collection):
    """RAG arama testi"""
    
    test_queries = [
        "yastıklamalı silindir lazım",
        "manyetik sensörlü silindir",
        "yumuşak durma özelliği",
        "endüstriyel otomasyon için silindir"
    ]
    
    for query in test_queries:
        print(f"\nARAMA: '{query}'")
        print("-" * 50)
        
        # Vector search
        results = collection.query(
            query_texts=[query],
            n_results=3
        )
        
        if results['documents'] and results['documents'][0]:
            print("BULUNAN URUNLER:")
            for i, doc in enumerate(results['documents'][0]):
                distance = results['distances'][0][i] if results['distances'] else 0
                metadata = results['metadatas'][0][i]
                
                print(f"\n{i+1}. {metadata['malzeme_kodu']} - {metadata['brand']}")
                print(f"   Similarity: {1-distance:.3f}")
                print(f"   Stok: {metadata['stock']:.0f} adet")
                
                # Show relevant content snippet
                lines = doc.split('\n')
                for line in lines[:3]:
                    if line.strip():
                        print(f"   {line.strip()}")
                        
            # AI Response Test
            print(f"\nAI RESPONSE:")
            ai_response = generate_ai_response(query, results)
            print(ai_response)

def generate_ai_response(query, search_results):
    """AI ile akıllı cevap oluştur"""
    
    if not search_results['documents'] or not search_results['documents'][0]:
        return "Uygun ürün bulunamadı."
    
    # Context hazırla
    context = "MEVCUT ÜRÜNLER:\n"
    for i, doc in enumerate(search_results['documents'][0][:2]):
        context += f"\n{i+1}. {doc}\n"
    
    # AI prompt
    messages = [
        {
            "role": "system",
            "content": "Sen B2B endüstriyel ürün uzmanısın. Müşteri sorularına teknik ve net cevap ver. Sadece verilen ürün bilgilerini kullan."
        },
        {
            "role": "user",
            "content": f"Soru: {query}\n\n{context}\n\nBu ürünler arasından en uygun olanı öner ve nedenini açıkla. Kısa ve net yanıtla."
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
            "max_tokens": 200
        }
        
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=data
        )
        
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            return f"AI hatası: {response.status_code}"
            
    except Exception as e:
        return f"Bağlantı hatası: {e}"

if __name__ == "__main__":
    print("=== SIMPLE RAG TEST ===")
    
    # Create RAG
    collection = create_simple_rag()
    
    # Test searches
    test_rag_search(collection)
    
    print("\n=== TEST COMPLETED ===")
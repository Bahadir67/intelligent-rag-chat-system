#!/usr/bin/env python3
"""
Manual RAG Test - Elle test yapın
"""

import os
import sys
import time
import chromadb
from dotenv import load_dotenv
import requests

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL_NAME = os.getenv("MODEL", "openai/gpt-3.5-turbo")

def single_search(query):
    """Tek arama yap"""
    print(f"\n🔍 ARAMA: '{query}'")
    print("=" * 50)
    
    try:
        # ChromaDB
        chroma_client = chromadb.PersistentClient(
            path=os.path.join(os.getcwd(), "chroma_db")
        )
        collection = chroma_client.get_collection("b2b_products")
        
        # Arama
        start_time = time.time()
        results = collection.query(
            query_texts=[query],
            n_results=5,
            where={"stock": {"$gte": 0.1}}
        )
        search_time = time.time() - start_time
        
        print(f"⏱️ Süre: {search_time:.3f}s")
        print(f"📊 Sonuç: {len(results['documents'][0]) if results['documents'] and results['documents'][0] else 0} ürün")
        
        if results['documents'] and results['documents'][0]:
            print("\n📦 BULUNAN ÜRÜNLER:")
            print("-" * 30)
            
            for i, doc in enumerate(results['documents'][0], 1):
                metadata = results['metadatas'][0][i-1]
                similarity = 1 - results['distances'][0][i-1]
                product_name = doc.split('\n')[0].replace('ÜRÜN: ', '')
                
                print(f"{i}. {product_name}")
                print(f"   🏷️ {metadata['brand']} | 📋 {metadata['malzeme_kodu']}")
                print(f"   📦 Stok: {metadata['stock']:.0f} | 🎯 Uygunluk: {similarity:.3f}")
                print()
            
            # AI yanıt
            print("🤖 AI UZMAN GÖRÜŞÜ:")
            print("-" * 30)
            ai_response = get_ai_response(query, results)
            print(ai_response)
        else:
            print("❌ Ürün bulunamadı")
            
    except Exception as e:
        print(f"❌ Hata: {e}")

def get_ai_response(query, results):
    """AI yanıt al"""
    if not results['documents'] or not results['documents'][0]:
        return "Uygun ürün bulunamadı."
    
    context = "ÜRÜNLER:\n"
    for i, doc in enumerate(results['documents'][0][:3], 1):
        metadata = results['metadatas'][0][i-1]
        product_name = doc.split('\n')[0].replace('ÜRÜN: ', '')
        similarity = 1 - results['distances'][0][i-1]
        
        context += f"{i}. {product_name}\n"
        context += f"   Marka: {metadata['brand']}, Stok: {metadata['stock']:.0f}\n"
    
    messages = [
        {"role": "system", "content": "Sen B2B ürün uzmanısın. Kısa ve net tavsiye ver."},
        {"role": "user", "content": f"Soru: {query}\n\n{context}\n\nEn uygun ürünü öner, kısaca açıkla."}
    ]
    
    try:
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
                "max_tokens": 200
            },
            timeout=10
        )
        
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            return f"AI hatası: {response.status_code}"
            
    except Exception as e:
        return f"AI bağlantı hatası: {e}"

def main():
    print("🚀 B2B RAG MANUEL TEST")
    print("=" * 40)
    
    example_queries = [
        "silindir arıyorum",
        "100mm silindir", 
        "MAG marka filtre",
        "yastıklamalı silindir",
        "manyetik sensörlü",
        "hava filtresi"
    ]
    
    print("💡 ÖRNEK SORGULAR:")
    for i, q in enumerate(example_queries, 1):
        print(f"{i}. {q}")
    
    print("\n" + "=" * 40)
    print("İstediğiniz sorguyu yazın:")
    
    # Örnek kullanım
    print("\n[ÖRNEK TEST]")
    single_search("100mm silindir")
    
    print("\n" + "=" * 40)
    print("✅ Test tamamlandı!")
    print("Diğer sorgular için bu scripti tekrar çalıştırabilirsiniz.")

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Simple RAG Test Script
Basit test ve demo için
"""

import os
import sys
import time
import chromadb
from dotenv import load_dotenv
import requests

# UTF-8 encoding fix
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

# Configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL_NAME = os.getenv("MODEL", "openai/gpt-3.5-turbo")

def test_search(query):
    """Tek bir arama testi"""
    print(f"\n{'='*60}")
    print(f"ARAMA: {query}")
    print('='*60)
    
    try:
        # ChromaDB connection
        chroma_client = chromadb.PersistentClient(
            path=os.path.join(os.getcwd(), "chroma_db")
        )
        collection = chroma_client.get_collection("b2b_products")
        
        # Search
        start_time = time.time()
        results = collection.query(
            query_texts=[query],
            n_results=5,
            where={"stock": {"$gte": 0.1}}
        )
        search_time = time.time() - start_time
        
        print(f"Arama suresi: {search_time:.3f} saniye")
        
        if results['documents'] and results['documents'][0]:
            print(f"Bulunan urun sayisi: {len(results['documents'][0])}")
            print("\nSONUCLAR:")
            print("-" * 40)
            
            for i, doc in enumerate(results['documents'][0], 1):
                metadata = results['metadatas'][0][i-1]
                similarity = 1 - results['distances'][0][i-1]
                
                # Parse product name
                product_name = doc.split('\n')[0].replace('ÜRÜN: ', '')
                
                print(f"{i}. {product_name}")
                print(f"   Marka: {metadata['brand']}")
                print(f"   Kod: {metadata['malzeme_kodu']}")
                print(f"   Stok: {metadata['stock']:.0f} adet")
                print(f"   Benzerlik: {similarity:.3f}")
                print()
            
            # AI Response
            print("AI YANITINI OLUSTURUYOR...")
            ai_response = generate_ai_response(query, results)
            print("\nAI UZMANI:")
            print("-" * 40)
            print(ai_response)
            
        else:
            print("Hic urun bulunamadi.")
            
    except Exception as e:
        print(f"Hata: {e}")

def generate_ai_response(query, search_results):
    """AI yanıt oluştur"""
    if not search_results['documents'] or not search_results['documents'][0]:
        return "Uygun urun bulunamadi."
    
    # Context hazırla
    context = "MEVCUT URUNLER:\n\n"
    for i, doc in enumerate(search_results['documents'][0][:3], 1):
        metadata = search_results['metadatas'][0][i-1]
        product_name = doc.split('\n')[0].replace('ÜRÜN: ', '')
        similarity = 1 - search_results['distances'][0][i-1]
        
        context += f"{i}. URUN: {product_name}\n"
        context += f"   MARKA: {metadata['brand']}\n"
        context += f"   KOD: {metadata['malzeme_kodu']}\n"
        context += f"   STOK: {metadata['stock']:.0f} adet\n"
        context += f"   UYGUNLUK: {similarity:.2f}\n\n"
    
    # AI prompt
    messages = [
        {
            "role": "system",
            "content": "Sen B2B endustriyel urun uzmanısın. Musteri sorularına teknik ve net cevap ver."
        },
        {
            "role": "user",
            "content": f"MUSTERI TALEBI: {query}\n\n{context}\n\nEn uygun urunu oner ve nedenini acikla. Kisa ve net yanitla."
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
            "max_tokens": 300
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
            return f"AI hata kodu: {response.status_code}"
            
    except Exception as e:
        return f"AI baglanti hatasi: {e}"

def main():
    """Ana test fonksiyonu"""
    print("B2B RAG SISTEM TESTI")
    print("=" * 40)
    
    # Test sorguları
    test_queries = [
        "silindir ariyorum",
        "100mm silindir", 
        "manyetik sensorlu silindir",
        "MAG marka filtre",
        "yastiklamali silindir",
        "hava filtresine ihtiyacim var"
    ]
    
    print("OTOMATIK TESTLER:")
    for query in test_queries:
        test_search(query)
        print("\n" + "="*60 + "\n")
    
    print("MANUEL TEST:")
    print("Istediginiz bir sorgu yazin (veya Enter ile cikis):")
    
    while True:
        try:
            user_query = input("\n> ").strip()
            if not user_query:
                break
            test_search(user_query)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Hata: {e}")
            break
    
    print("\nTest tamamlandi!")

if __name__ == "__main__":
    main()
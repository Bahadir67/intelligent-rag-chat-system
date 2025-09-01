#!/usr/bin/env python3
"""
Enhanced RAG System - ChromaDB + AI Conversation Engine
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime

import psycopg2
from psycopg2.extras import RealDictCursor
import chromadb
from chromadb.config import Settings
from dotenv import load_dotenv
import requests

# Load environment
load_dotenv()

# Configuration
DB_CONNECTION = "postgresql://postgres:masterkey@localhost:5432/b2b_rag_system"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL_NAME = os.getenv("MODEL", "openai/gpt-3.5-turbo")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ProductDocument:
    """RAG için ürün dokümanı"""
    product_id: int
    malzeme_kodu: str
    content: str
    metadata: Dict[str, Any]

@dataclass  
class SearchResult:
    """Arama sonucu"""
    product_id: int
    content: str
    score: float
    metadata: Dict[str, Any]

class DocumentGenerator:
    """Ürünler için RAG dokümanları oluşturur"""
    
    def __init__(self):
        self.db = psycopg2.connect(DB_CONNECTION)
        
    def create_product_document(self, product_row: Dict) -> ProductDocument:
        """Bir ürün için zenginleştirilmiş doküman oluştur"""
        
        # Temel bilgiler
        name = product_row['malzeme_adi'] or "Bilinmeyen Ürün"
        brand = product_row['brand_name'] or "Bilinmeyen Marka"
        category = product_row['category_name'] or "Genel"
        stock = float(product_row['current_stock'] or 0)
        
        # Teknik özellikleri çıkar
        features = self._extract_technical_features(name)
        
        # RAG dokümanı oluştur
        content = self._build_rich_content(
            name=name,
            brand=brand, 
            category=category,
            features=features,
            stock=stock,
            code=product_row['malzeme_kodu']
        )
        
        # Metadata - ChromaDB only supports str, int, float, bool
        metadata = {
            "product_id": product_row['id'],
            "malzeme_kodu": str(product_row['malzeme_kodu']),
            "brand": str(brand),
            "category": str(category),
            "stock": float(stock),
            "searchable_text": str(name.upper()),
            # Flatten features for ChromaDB
            "diameter": features.get('diameter', 0),
            "stroke": features.get('stroke', 0),
            "size": features.get('size', 0),
            "has_cushion": 'yastıklamalı' in features.get('capabilities', []),
            "has_magnetic": 'manyetik_sensör' in features.get('capabilities', []),
            "capabilities": ' '.join(features.get('capabilities', []))  # String olarak
        }
        
        return ProductDocument(
            product_id=product_row['id'],
            malzeme_kodu=product_row['malzeme_kodu'],
            content=content,
            metadata=metadata
        )
    
    def _extract_technical_features(self, product_name: str) -> Dict[str, Any]:
        """Ürün adından teknik özellikleri çıkar"""
        name_upper = product_name.upper()
        features = {}
        
        # Boyut çıkarma
        import re
        
        # Çap x Stroke
        size_match = re.search(r'(\d+)\s*[*x×]\s*(\d+)', name_upper)
        if size_match:
            features['diameter'] = int(size_match.group(1))
            features['stroke'] = int(size_match.group(2))
        
        # Tek boyut
        single_size = re.search(r'(\d+)\s*MM|\b(\d+)\s*(?=\s)', name_upper)
        if single_size and not size_match:
            size_val = single_size.group(1) or single_size.group(2)
            if size_val:
                features['size'] = int(size_val)
        
        # Özel özellikler
        feature_flags = []
        
        if 'YAST' in name_upper or 'CUSHION' in name_upper:
            feature_flags.append('yastıklamalı')
            feature_flags.append('yumuşak_durma')
            feature_flags.append('titreşim_azaltma')
            
        if 'MAG' in name_upper or 'MAGNETIC' in name_upper:
            feature_flags.append('manyetik_sensör')
            feature_flags.append('konum_geri_bildirimi')
            
        if 'FILTRE' in name_upper or 'FILTER' in name_upper:
            feature_flags.append('filtreleme')
            feature_flags.append('temizleme')
            
        if 'VALF' in name_upper or 'VALVE' in name_upper:
            feature_flags.append('akış_kontrolü')
            feature_flags.append('basınç_kontrolü')
            
        features['capabilities'] = feature_flags
        
        return features
    
    def _build_rich_content(self, name: str, brand: str, category: str, 
                          features: Dict, stock: float, code: str) -> str:
        """Zenginleştirilmiş RAG içeriği oluştur"""
        
        content = f"""ÜRÜN: {name}
MARKA: {brand}
KOD: {code}
KATEGORİ: {category}
STOK DURUMU: {stock:.0f} adet mevcut

"""
        
        # Teknik özellikler
        if features.get('diameter') and features.get('stroke'):
            content += f"TEKNİK ÖZELLİKLER:\n"
            content += f"- Çap: {features['diameter']}mm\n"
            content += f"- Stroke: {features['stroke']}mm\n"
        elif features.get('size'):
            content += f"TEKNİK ÖZELLİKLER:\n"
            content += f"- Boyut: {features['size']}mm\n"
        
        # Yetenekler
        if features.get('capabilities'):
            content += f"\nÖZELLİKLER:\n"
            for capability in features['capabilities']:
                content += f"- {capability.replace('_', ' ').title()}\n"
        
        # Kategori bazlı ek bilgiler
        content += f"\n{self._get_category_info(category, features)}"
        
        # Uygulama alanları
        content += f"\nUYGULAMA ALANLARI:\n{self._get_application_areas(category, features)}"
        
        return content
    
    def _get_category_info(self, category: str, features: Dict) -> str:
        """Kategori bazlı ek bilgi"""
        
        if 'Silindir' in category:
            info = "SILINDIR HAKKINDA:\n"
            info += "Pnömatik tahrik sistemi bileşeni. "
            
            if 'yastıklamalı' in features.get('capabilities', []):
                info += "Yastıklamalı tip yumuşak durma sağlar ve titreşimi azaltır. "
            
            if 'manyetik_sensör' in features.get('capabilities', []):
                info += "Manyetik sensör konum geri bildirimi verir. "
                
            info += "Endüstriyel otomasyonda kullanılır."
            return info
            
        elif 'Filtre' in category:
            return "FILTRE HAKKINDA:\nHava ve sıvı sistemlerinde kirletici maddeleri ayırır. Sistem güvenilirliğini artırır."
            
        elif 'Valf' in category:
            return "VALF HAKKINDA:\nAkış kontrolü ve yön değiştirme için kullanılır. Sistem kontrolünün temel elemanıdır."
            
        return "Endüstriyel otomasyon bileşeni."
    
    def _get_application_areas(self, category: str, features: Dict) -> str:
        """Uygulama alanları"""
        
        base_areas = [
            "- Endüstriyel otomasyon sistemleri",
            "- Üretim hatları", 
            "- Makine yapımı"
        ]
        
        if 'Silindir' in category:
            if 'yastıklamalı' in features.get('capabilities', []):
                base_areas.extend([
                    "- Hassas konumlandırma uygulamaları",
                    "- Yüksek döngü sayılı operasyonlar"
                ])
            base_areas.extend([
                "- Materyel transfer sistemleri",
                "- Presleme ve sıkma uygulamaları"
            ])
            
        elif 'Filtre' in category:
            base_areas.extend([
                "- Hava hazırlama üniteleri",
                "- Temiz hava sistemleri",
                "- Koruyucu filtreleme"
            ])
            
        return "\n".join(base_areas)
    
    def generate_all_documents(self) -> List[ProductDocument]:
        """Tüm ürünler için dokümanlar oluştur"""
        
        with self.db.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    p.id, p.malzeme_kodu, p.malzeme_adi,
                    COALESCE(b.brand_name, 'Bilinmeyen') as brand_name,
                    COALESCE(pc.category_name, 'Genel') as category_name,
                    COALESCE(i.current_stock, 0) as current_stock
                FROM products p
                LEFT JOIN brands b ON p.brand_id = b.id
                LEFT JOIN product_categories pc ON p.category_id = pc.id  
                LEFT JOIN inventory i ON p.id = i.product_id
                WHERE p.malzeme_adi IS NOT NULL
                ORDER BY p.id
            """)
            
            products = cur.fetchall()
            logger.info(f"Toplam {len(products)} ürün için doküman oluşturuluyor...")
            
            documents = []
            for i, product in enumerate(products):
                if i % 1000 == 0:
                    logger.info(f"İşlenen: {i}/{len(products)}")
                    
                doc = self.create_product_document(dict(product))
                documents.append(doc)
            
            logger.info(f"Toplam {len(documents)} doküman oluşturuldu")
            return documents

class ChromaRAG:
    """ChromaDB tabanlı RAG sistemi"""
    
    def __init__(self):
        # ChromaDB client - Windows safe path
        import tempfile
        db_path = os.path.join(os.getcwd(), "chroma_db")
        
        self.client = chromadb.PersistentClient(
            path=db_path,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Collection oluştur/al
        try:
            self.collection = self.client.get_collection("b2b_products")
            logger.info("Mevcut ChromaDB collection yüklendi")
        except:
            self.collection = self.client.create_collection(
                name="b2b_products",
                metadata={"description": "B2B ürün kataloğu"}
            )
            logger.info("Yeni ChromaDB collection oluşturuldu")
        
        # OpenRouter client
        self.api_key = OPENROUTER_API_KEY
        
    def index_documents(self, documents: List[ProductDocument], batch_size: int = 100):
        """Dokümanları ChromaDB'ye indexle"""
        
        logger.info(f"ChromaDB'ye {len(documents)} doküman indexleniyor...")
        
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            
            # Batch verilerini hazırla
            ids = [f"product_{doc.product_id}" for doc in batch]
            contents = [doc.content for doc in batch]
            metadatas = [doc.metadata for doc in batch]
            
            # ChromaDB'ye ekle
            self.collection.add(
                ids=ids,
                documents=contents,
                metadatas=metadatas
            )
            
            logger.info(f"Batch {i//batch_size + 1}/{(len(documents)-1)//batch_size + 1} indexlendi")
        
        logger.info("ChromaDB indexleme tamamlandı")
    
    def search(self, query: str, n_results: int = 5, 
              filters: Optional[Dict] = None) -> List[SearchResult]:
        """Semantic search"""
        
        logger.info(f"ChromaDB'de aranıyor: '{query}'")
        
        # ChromaDB query
        where_clause = {}
        if filters:
            if filters.get('min_stock'):
                where_clause['stock'] = {"$gte": filters['min_stock']}
            if filters.get('category'):
                where_clause['category'] = filters['category']
            if filters.get('brand'):
                where_clause['brand'] = filters['brand']
        
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where_clause if where_clause else None
        )
        
        # Format results
        search_results = []
        if results['documents'] and results['documents'][0]:
            for i, doc in enumerate(results['documents'][0]):
                search_results.append(SearchResult(
                    product_id=results['metadatas'][0][i]['product_id'],
                    content=doc,
                    score=results['distances'][0][i] if results['distances'] else 0.0,
                    metadata=results['metadatas'][0][i]
                ))
        
        logger.info(f"{len(search_results)} sonuç bulundu")
        return search_results
    
    def generate_ai_response(self, query: str, search_results: List[SearchResult]) -> str:
        """Retrieved context ile AI response oluştur"""
        
        # Context hazırlama
        context = "MEVCUT ÜRÜNLER:\n\n"
        for i, result in enumerate(search_results[:3], 1):
            context += f"{i}. {result.content}\n"
            context += f"   (Benzerlik skoru: {result.score:.3f})\n\n"
        
        # AI prompt
        messages = [
            {
                "role": "system",
                "content": """Sen bir B2B endüstriyel ürün uzmanısın. Müşteri sorularına teknik bilgiyle cevap ver.

Kurallar:
1. Sadece verilen ürün bilgilerini kullan
2. Teknik özellikleri açıkla
3. Uygun ürünleri öner
4. Stok durumunu belirt
5. Kısa ve net cevaplar ver
6. Türkçe yanıtla"""
            },
            {
                "role": "user", 
                "content": f"SORU: {query}\n\n{context}\n\nYukarıdaki ürünler arasından en uygun olanları öner ve nedenini açıkla."
            }
        ]
        
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            
            data = {
                "model": MODEL_NAME,
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": 400
            }
            
            response = requests.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                headers=headers,
                json=data
            )
            
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']
            else:
                logger.error(f"OpenRouter hatası: {response.status_code}")
                return self._fallback_response(search_results)
                
        except Exception as e:
            logger.error(f"AI response hatası: {e}")
            return self._fallback_response(search_results)
    
    def _fallback_response(self, results: List[SearchResult]) -> str:
        """AI başarısız olursa basit response"""
        if not results:
            return "Üzgünüm, aradığınız kriterlerde ürün bulunamadı."
        
        response = f"{len(results)} uygun ürün bulundu:\n\n"
        for i, result in enumerate(results[:3], 1):
            meta = result.metadata
            response += f"{i}. {meta.get('malzeme_kodu', 'N/A')} - "
            response += f"{meta.get('brand', 'N/A')} "
            response += f"(Stok: {meta.get('stock', 0):.0f} adet)\n"
        
        return response

def setup_rag_system():
    """RAG sistemini kur"""
    logger.info("=== B2B RAG Sistemi Kurulumu ===")
    
    # 1. Doküman oluştur
    logger.info("1. Ürün dokümanları oluşturuluyor...")
    doc_generator = DocumentGenerator()
    documents = doc_generator.generate_all_documents()
    
    # 2. ChromaDB'ye indexle
    logger.info("2. ChromaDB indexleniyor...")
    rag = ChromaRAG()
    rag.index_documents(documents)
    
    logger.info("RAG sistemi hazır!")
    return rag

def test_rag_system():
    """RAG sistemini test et"""
    
    # RAG sistemi yükle/kur
    try:
        rag = ChromaRAG()
        # Collection var mı kontrol et
        count = rag.collection.count()
        if count == 0:
            logger.info("ChromaDB boş, indexleme gerekiyor...")
            rag = setup_rag_system()
        else:
            logger.info(f"ChromaDB hazır: {count} doküman")
    except:
        rag = setup_rag_system()
    
    # Test sorguları
    test_queries = [
        "100mm çapında yastıklamalı silindir",
        "Manyetik sensörlü silindir lazım", 
        "MAG marka filtre",
        "Yüksek basınca dayanıklı ürün",
        "Sessiz çalışan silindir"
    ]
    
    print("\n=== RAG SİSTEMİ TEST ===")
    
    for query in test_queries:
        print(f"\n🔍 SORU: {query}")
        print("-" * 50)
        
        # Vector search
        results = rag.search(query, n_results=3, filters={"min_stock": 0.1})
        
        if results:
            # AI response
            ai_response = rag.generate_ai_response(query, results)
            print(f"🤖 AI CEVAP:\n{ai_response}")
        else:
            print("❌ Sonuç bulunamadı")

if __name__ == "__main__":
    test_rag_system()
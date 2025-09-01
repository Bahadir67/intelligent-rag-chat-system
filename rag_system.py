#!/usr/bin/env python3
"""
B2B RAG System - AI Satış Danışmanı
Ürün keşfi → Derinlemesine sorular → Sipariş oluşturma
"""

import os
import re
import json
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

import psycopg2
from psycopg2.extras import RealDictCursor

# Embeddings şu an disable - basit arama kullanacağız
EMBEDDINGS_AVAILABLE = False
# try:
#     from sentence_transformers import SentenceTransformer
#     import numpy as np
#     from sklearn.metrics.pairwise import cosine_similarity
#     EMBEDDINGS_AVAILABLE = True
# except ImportError:
#     EMBEDDINGS_AVAILABLE = False

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
DB_CONNECTION = "postgresql://postgres:masterkey@localhost:5432/b2b_rag_system"

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL_NAME = os.getenv("MODEL", "openai/gpt-3.5-turbo")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

@dataclass
class Product:
    """Ürün bilgileri"""
    id: int
    malzeme_kodu: str
    malzeme_adi: str
    brand_name: str
    current_stock: float
    category_name: str
    search_keywords: str
    unit_price: Optional[float] = None

@dataclass 
class ConversationState:
    """Konuşma durumu"""
    customer_id: int
    intent: str  # "product_search", "specification", "ordering"
    search_criteria: Dict = None
    shortlist: List[Product] = None
    selected_product: Optional[Product] = None
    conversation_history: List[Dict] = None
    
    def __post_init__(self):
        if self.search_criteria is None:
            self.search_criteria = {}
        if self.shortlist is None:
            self.shortlist = []
        if self.conversation_history is None:
            self.conversation_history = []

class DatabaseManager:
    """PostgreSQL veritabanı yöneticisi"""
    
    def __init__(self):
        self.connection = psycopg2.connect(DB_CONNECTION)
        
    def search_products(self, search_terms: List[str], limit: int = 50) -> List[Product]:
        """Ürün arama"""
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            # Build dynamic WHERE clause
            where_conditions = []
            params = []
            
            for term in search_terms:
                where_conditions.append("(p.malzeme_adi ILIKE %s OR p.search_keywords ILIKE %s)")
                params.extend([f'%{term}%', f'%{term}%'])
            
            where_clause = " AND ".join(where_conditions)
            
            query = f"""
                SELECT 
                    p.id,
                    p.malzeme_kodu,
                    p.malzeme_adi,
                    COALESCE(b.brand_name, 'Unknown') as brand_name,
                    COALESCE(i.current_stock, 0) as current_stock,
                    COALESCE(pc.category_name, 'Genel') as category_name,
                    COALESCE(p.search_keywords, '') as search_keywords
                FROM products p
                LEFT JOIN brands b ON p.brand_id = b.id
                LEFT JOIN inventory i ON p.id = i.product_id
                LEFT JOIN product_categories pc ON p.category_id = pc.id
                WHERE {where_clause}
                ORDER BY i.current_stock DESC, p.malzeme_adi
                LIMIT %s
            """
            params.append(limit)
            
            cur.execute(query, params)
            rows = cur.fetchall()
            
            return [Product(**dict(row)) for row in rows]
    
    def get_product_details(self, product_id: int) -> Optional[Product]:
        """Ürün detayları"""
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            query = """
                SELECT 
                    p.id, p.malzeme_kodu, p.malzeme_adi,
                    COALESCE(b.brand_name, 'Unknown') as brand_name,
                    COALESCE(i.current_stock, 0) as current_stock,
                    COALESCE(pc.category_name, 'Genel') as category_name,
                    COALESCE(p.search_keywords, '') as search_keywords,
                    -- Son satış fiyatını al
                    (SELECT oi.birim_fiyat FROM order_items oi 
                     WHERE oi.product_id = p.id 
                     ORDER BY oi.id DESC LIMIT 1) as unit_price
                FROM products p
                LEFT JOIN brands b ON p.brand_id = b.id
                LEFT JOIN inventory i ON p.id = i.product_id
                LEFT JOIN product_categories pc ON p.category_id = pc.id
                WHERE p.id = %s
            """
            cur.execute(query, (product_id,))
            row = cur.fetchone()
            
            return Product(**dict(row)) if row else None
    
    def get_product_variants(self, base_product: Product) -> List[Product]:
        """Benzer ürün varyantları"""
        # Extract base product features for finding variants
        base_features = self._extract_features(base_product.malzeme_adi)
        
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            # Find products with similar base name but different specs
            query = """
                SELECT 
                    p.id, p.malzeme_kodu, p.malzeme_adi,
                    COALESCE(b.brand_name, 'Unknown') as brand_name,
                    COALESCE(i.current_stock, 0) as current_stock,
                    COALESCE(pc.category_name, 'Genel') as category_name,
                    COALESCE(p.search_keywords, '') as search_keywords
                FROM products p
                LEFT JOIN brands b ON p.brand_id = b.id
                LEFT JOIN inventory i ON p.id = i.product_id
                LEFT JOIN product_categories pc ON p.category_id = pc.id
                WHERE p.category_id = %s 
                AND b.brand_name = %s 
                AND p.id != %s
                AND i.current_stock > 0
                ORDER BY p.malzeme_adi
                LIMIT 10
            """
            cur.execute(query, (base_product.category_name, base_product.brand_name, base_product.id))
            rows = cur.fetchall()
            
            return [Product(**dict(row)) for row in rows]
    
    def create_order(self, customer_id: int, product_id: int, quantity: float) -> Dict:
        """Sipariş oluştur"""
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                # Generate order number
                order_number = f"AI-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
                
                # Create order
                cur.execute("""
                    INSERT INTO orders (belge_numarasi, belge_tipi, customer_id, belge_tarihi, is_alani)
                    VALUES (%s, 'AI', %s, CURRENT_DATE, 'AI Sales')
                    RETURNING id, belge_numarasi
                """, (order_number, customer_id))
                
                order = cur.fetchone()
                order_id = order['id']
                
                # Get product details for pricing
                product = self.get_product_details(product_id)
                unit_price = product.unit_price or 100.0  # Default price
                total_amount = unit_price * quantity
                
                # Create order item
                cur.execute("""
                    INSERT INTO order_items (
                        order_id, kalem_no, product_id, miktar, birim, 
                        birim_fiyat, ciro_tutari, net_ciro
                    )
                    VALUES (%s, 1, %s, %s, 'AD', %s, %s, %s)
                    RETURNING id
                """, (order_id, product_id, quantity, unit_price, total_amount, total_amount))
                
                order_item = cur.fetchone()
                
                # Update order totals
                cur.execute("""
                    UPDATE orders 
                    SET total_ciro = %s, total_net_ciro = %s
                    WHERE id = %s
                """, (total_amount, total_amount, order_id))
                
                self.connection.commit()
                
                return {
                    "success": True,
                    "order_id": order_id,
                    "order_number": order_number,
                    "product": product,
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "total_amount": total_amount
                }
                
            except Exception as e:
                self.connection.rollback()
                logger.error(f"Sipariş oluşturma hatası: {e}")
                return {"success": False, "error": str(e)}
    
    def _extract_features(self, product_name: str) -> Dict:
        """Ürün özelliklerini çıkar"""
        features = {}
        
        # Size patterns
        size_match = re.search(r'(\d+)\s*[*x×]\s*(\d+)', product_name.upper())
        if size_match:
            features['diameter'] = size_match.group(1)
            features['stroke'] = size_match.group(2)
        
        # Single size
        single_size = re.search(r'(\d+)\s*MM|\b(\d+)\s*[^\d*x×]', product_name.upper())
        if single_size and not size_match:
            features['size'] = single_size.group(1) or single_size.group(2)
        
        # Special features
        if 'YAST' in product_name.upper() or 'CUSHION' in product_name.upper():
            features['cushioned'] = True
        if 'MAG' in product_name.upper() or 'MAGNETIC' in product_name.upper():
            features['magnetic'] = True
            
        return features

class OpenRouterClient:
    """OpenRouter API client"""
    
    def __init__(self):
        self.api_key = OPENROUTER_API_KEY
        self.base_url = OPENROUTER_BASE_URL
        
    def generate_response(self, messages: List[Dict], model: str = None) -> str:
        """OpenRouter ile response generate et"""
        if not model:
            model = MODEL_NAME
            
        try:
            import requests
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            
            data = {
                "model": model,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 500
            }
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=data
            )
            
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']
            else:
                logger.error(f"OpenRouter API hatası: {response.status_code} - {response.text}")
                return "Üzgünüm, bir hata oluştu. Lütfen tekrar deneyin."
                
        except Exception as e:
            logger.error(f"OpenRouter API bağlantı hatası: {e}")
            return "Üzgünüm, AI hizmetine bağlanamıyorum. Lütfen tekrar deneyin."

class ConversationEngine:
    """AI Konuşma Motoru"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.ai_client = OpenRouterClient()
        self.sessions = {}  # In-memory session store
        
        # Load sentence transformer for embeddings
        if EMBEDDINGS_AVAILABLE:
            try:
                self.embedder = SentenceTransformer('sentence-transformers/distiluse-base-multilingual-cased')
            except:
                logger.warning("Sentence transformer yüklenemedi, basit arama kullanılacak")
                self.embedder = None
        else:
            logger.info("Embeddings kütüphaneleri yok, basit arama kullanılacak")
            self.embedder = None
    
    def process_message(self, customer_id: int, user_message: str) -> str:
        """Kullanıcı mesajını işle ve yanıt ver"""
        
        # Get or create session
        session_key = f"customer_{customer_id}"
        if session_key not in self.sessions:
            self.sessions[session_key] = ConversationState(customer_id=customer_id, intent="product_search")
        
        state = self.sessions[session_key]
        
        # Add to conversation history
        state.conversation_history.append({"role": "user", "content": user_message})
        
        # Intent detection and response generation
        if state.intent == "product_search":
            return self._handle_product_search(state, user_message)
        elif state.intent == "specification":
            return self._handle_specification_questions(state, user_message)
        elif state.intent == "ordering":
            return self._handle_ordering(state, user_message)
        else:
            return "Nasıl yardımcı olabilirim?"
    
    def _handle_product_search(self, state: ConversationState, user_message: str) -> str:
        """Ürün arama aşaması"""
        
        # Extract search terms
        search_terms = self._extract_search_terms(user_message)
        
        if not search_terms:
            return "Hangi ürünü arıyorsunuz? Örneğin: '100'lük silindir' veya 'MAG marka filtre'"
        
        # Search products
        products = self.db.search_products(search_terms, limit=20)
        
        if not products:
            return f"'{' '.join(search_terms)}' için ürün bulunamadı. Farklı anahtar kelimeler deneyin."
        
        # Filter only in-stock products
        in_stock_products = [p for p in products if p.current_stock > 0]
        
        if not in_stock_products:
            return f"'{' '.join(search_terms)}' ürünleri stokta yok. Farklı ürünler önerebilirim."
        
        state.shortlist = in_stock_products[:10]  # Top 10
        
        # Generate smart follow-up questions based on product variety
        if len(in_stock_products) > 5:
            state.intent = "specification"
            return self._generate_specification_questions(state)
        elif len(in_stock_products) >= 1:
            # Show options and ask for selection
            state.intent = "specification"  # Sayı seçimi için specification moduna geç
            
            response = f"{len(in_stock_products)} adet ürün bulundu:\n\n"
            for i, product in enumerate(in_stock_products[:5], 1):
                response += f"{i}. {product.malzeme_adi} - {product.brand_name} (Stok: {product.current_stock:.0f} adet)\n"
            
            if len(in_stock_products) > 5:
                response += f"... ve {len(in_stock_products) - 5} ürün daha\n"
            
            response += "\nHangisi size uygun? Numara söyleyebilir veya daha spesifik özellik belirtebilirsiniz."
            
            return response
    
    def _handle_specification_questions(self, state: ConversationState, user_message: str) -> str:
        """Özellik detaylandırma aşaması"""
        
        # Check for number selection first
        number_match = re.search(r'\b([1-9])\b', user_message)
        if number_match:
            selection_num = int(number_match.group(1))
            if 1 <= selection_num <= len(state.shortlist):
                # User selected by number
                state.selected_product = state.shortlist[selection_num - 1]
                state.intent = "ordering"
                
                product = state.selected_product
                response = f"✅ Seçtiğiniz ürün:\n\n"
                response += f"📦 {product.malzeme_adi}\n"
                response += f"🏷️ Marka: {product.brand_name}\n"
                response += f"📊 Stok: {product.current_stock:.0f} adet\n"
                if product.unit_price:
                    response += f"💰 Fiyat: {product.unit_price:.2f} TL\n"
                response += "\nKaç adet sipariş vermek istiyorsunuz?"
                
                return response
            else:
                return f"Lütfen 1-{len(state.shortlist)} arasında bir numara seçin."
        
        # Parse user response for specifications
        user_specs = self._parse_specifications(user_message)
        state.search_criteria.update(user_specs)
        
        # Filter products based on new criteria
        filtered_products = self._filter_by_specifications(state.shortlist, state.search_criteria)
        
        if len(filtered_products) == 1:
            # Perfect match found
            state.selected_product = filtered_products[0]
            state.intent = "ordering"
            
            product = state.selected_product
            response = f"✅ Tam sizin istediğiniz ürün:\n\n"
            response += f"📦 {product.malzeme_adi}\n"
            response += f"🏷️ Marka: {product.brand_name}\n"
            response += f"📊 Stok: {product.current_stock:.0f} adet\n"
            response += f"💰 Fiyat: {product.unit_price:.2f} TL (tahmini)\n\n"
            response += "Kaç adet sipariş vermek istiyorsunuz?"
            
            return response
            
        elif len(filtered_products) > 1:
            # Still multiple options, ask more specific questions
            state.shortlist = filtered_products
            return self._generate_specification_questions(state)
            
        else:
            # No matches, suggest alternatives
            return "Bu özelliklerde ürün bulunamadı. Alternatif özellikler önerebilirim veya farklı ürünlere bakabiliriz."
    
    def _handle_ordering(self, state: ConversationState, user_message: str) -> str:
        """Sipariş oluşturma aşaması"""
        
        # Extract quantity
        quantity_match = re.search(r'(\d+)\s*adet|\b(\d+)\b', user_message)
        if quantity_match:
            quantity = float(quantity_match.group(1) or quantity_match.group(2))
            
            # Check stock availability
            if quantity > state.selected_product.current_stock:
                return f"Üzgünüm, stokta sadece {state.selected_product.current_stock:.0f} adet var. Bu miktarla sipariş verebilirim."
            
            # Create order
            order_result = self.db.create_order(state.customer_id, state.selected_product.id, quantity)
            
            if order_result["success"]:
                response = f"🎉 Sipariş başarıyla oluşturuldu!\n\n"
                response += f"📄 Sipariş No: {order_result['order_number']}\n"
                response += f"📦 Ürün: {order_result['product'].malzeme_adi}\n"
                response += f"🔢 Miktar: {quantity:.0f} adet\n"
                response += f"💰 Toplam: {order_result['total_amount']:.2f} TL\n\n"
                response += "Siparişiniz işleme alınmıştır. Başka bir ürün arayabilirsiniz!"
                
                # Reset session for new search
                state.intent = "product_search"
                state.shortlist = []
                state.selected_product = None
                state.search_criteria = {}
                
                return response
            else:
                return f"Sipariş oluşturulurken hata oluştu: {order_result['error']}"
        else:
            return "Kaç adet sipariş vermek istiyorsunuz? Lütfen sayı belirtin."
    
    def _extract_search_terms(self, message: str) -> List[str]:
        """Mesajdan arama terimlerini çıkar"""
        message_upper = message.upper()
        terms = []
        
        # Common product terms (hem Türkçe hem İngilizce)
        product_keywords = [
            ('SİLİNDİR', 'SILINDIR', 'CYLINDER'), 
            ('FİLTRE', 'FILTRE', 'FILTER'),
            ('VALF', 'VALVE'), 
            ('POMPA', 'PUMP'), 
            ('MOTOR', 'MOTOR'),
            ('RULMAN', 'BEARING'), 
            ('CONTA', 'SEAL')
        ]
        
        for keyword_variants in product_keywords:
            for variant in keyword_variants:
                if variant in message_upper:
                    terms.append(variant)
                    break  # Bir varyant bulunca diğerlerine bakmaya gerek yok
        
        # Size patterns - daha geniş arama
        size_patterns = [
            r'(\d+)\s*[LÜK]+',  # 100lük, 100luk
            r'(\d+)\s*MM',      # 100mm, 100 mm
            r'(\d+)\s*İNCH',    # 3inch
            r'(\d+)\s*[*x×]\s*(\d+)',  # 100*200, 100x200
            r'\b(\d+)\s*(?=\s|$)'  # Sadece sayı (100 ariyorum gibi)
        ]
        
        for pattern in size_patterns:
            matches = re.findall(pattern, message_upper)
            for match in matches:
                if isinstance(match, tuple):
                    terms.extend([m for m in match if m])  # Tuple içindeki tüm grupları al
                else:
                    terms.append(match)
        
        # Brand names (from our database)
        brand_keywords = ['MAG', 'SMC', 'FESTO', 'PARKER', 'BOSCH', 'PNEUMAX']
        for brand in brand_keywords:
            if brand in message_upper:
                terms.append(brand)
        
        # Debug için
        logger.info(f"Arama terimleri çıkarıldı: '{message}' -> {terms}")
        
        return list(set(terms))  # Duplicate'leri kaldır
    
    def _generate_specification_questions(self, state: ConversationState) -> str:
        """Akıllı özellik soruları oluştur"""
        
        # Analyze product variety to determine best discriminating question
        products = state.shortlist
        
        # Check variety in different dimensions
        brands = set(p.brand_name for p in products)
        categories = set(p.category_name for p in products)
        
        # Extract common specifications from product names
        has_magnetic = any('MAG' in p.malzeme_adi.upper() for p in products)
        has_cushioned = any('YAST' in p.malzeme_adi.upper() for p in products)
        
        # Generate contextual questions
        if len(brands) > 2:
            brand_list = ', '.join(list(brands)[:3])
            return f"{len(products)} farklı ürün var. Hangi markayı tercih edersiniz?\n\nMevcut markalar: {brand_list}"
        
        elif has_magnetic and has_cushioned:
            return "Manyetik sensörlü mü yoksa yastıklamalı tip mi istiyorsunuz?"
        
        elif has_magnetic:
            return "Manyetik sensör gerekli mi?"
        
        elif has_cushioned:
            return "Yastıklamalı (yumuşak durma) olması gerekli mi?"
        
        else:
            # Show top options
            response = f"{len(products)} seçenek var:\n\n"
            for i, product in enumerate(products[:3], 1):
                response += f"{i}. {product.malzeme_adi} - {product.brand_name}\n"
            response += "\nHangisini tercih edersiniz?"
            return response
    
    def _parse_specifications(self, message: str) -> Dict:
        """Kullanıcı mesajından özellikleri çıkar"""
        message_upper = message.upper()
        specs = {}
        
        # Magnetic sensor
        if any(word in message_upper for word in ['MANYETİK', 'MAGNETIC', 'SENSÖR']):
            specs['magnetic'] = True
        elif any(word in message_upper for word in ['MANYETİK YOK', 'SENSÖR YOK']):
            specs['magnetic'] = False
        
        # Cushioned
        if any(word in message_upper for word in ['YASTIK', 'CUSHION', 'YUMUŞAK']):
            specs['cushioned'] = True
        elif any(word in message_upper for word in ['YASTIK YOK', 'SERT']):
            specs['cushioned'] = False
        
        # Brand preference
        brands = ['MAG', 'SMC', 'FESTO', 'PARKER', 'BOSCH']
        for brand in brands:
            if brand in message_upper:
                specs['brand'] = brand
        
        # Size specifications
        size_match = re.search(r'(\d+)\s*MM', message_upper)
        if size_match:
            specs['size'] = size_match.group(1)
        
        return specs
    
    def _filter_by_specifications(self, products: List[Product], criteria: Dict) -> List[Product]:
        """Ürünleri özelliklere göre filtrele"""
        filtered = []
        
        for product in products:
            match = True
            name_upper = product.malzeme_adi.upper()
            
            # Check magnetic requirement
            if 'magnetic' in criteria:
                has_magnetic = 'MAG' in name_upper
                if criteria['magnetic'] != has_magnetic:
                    match = False
                    continue
            
            # Check cushioned requirement
            if 'cushioned' in criteria:
                has_cushioned = 'YAST' in name_upper
                if criteria['cushioned'] != has_cushioned:
                    match = False
                    continue
            
            # Check brand
            if 'brand' in criteria:
                if criteria['brand'].upper() not in product.brand_name.upper():
                    match = False
                    continue
            
            # Check size
            if 'size' in criteria:
                if criteria['size'] not in name_upper:
                    match = False
                    continue
            
            if match:
                filtered.append(product)
        
        return filtered

# Test interface
def test_conversation():
    """Test konuşma motoru"""
    engine = ConversationEngine()
    customer_id = 1  # Koçak müşterisi
    
    print("🤖 B2B AI Satış Danışmanı")
    print("Merhaba! Hangi ürünü arıyorsunuz?")
    print("(Çıkmak için 'quit' yazın)\n")
    
    while True:
        user_input = input("👤 Siz: ").strip()
        
        if user_input.lower() in ['quit', 'exit', 'çık']:
            print("👋 Görüşmek üzere!")
            break
        
        if not user_input:
            continue
        
        try:
            response = engine.process_message(customer_id, user_input)
            print(f"🤖 AI: {response}\n")
        except Exception as e:
            print(f"❌ Hata: {e}\n")

if __name__ == "__main__":
    test_conversation()
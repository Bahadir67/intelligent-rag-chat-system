#!/usr/bin/env python3
"""
B2B Conversation System - Context takibi ile sipariş sürecine kadar
Kullanım: python conversation_system.py
"""

import sys, re, json
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from typing import Dict, List, Optional

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

class ConversationContext:
    """Konuşma context'ini takip eder"""
    def __init__(self):
        self.user_query_history = []
        self.extracted_specs = {
            'diameter': None,
            'stroke': None,
            'features': [],
            'quantity': None,
            'brand_preference': None
        }
        self.conversation_stage = 'initial'  # initial, spec_gathering, product_selection, order_creation
        self.selected_products = []
        self.user_tone = 'professional'
        self.customer_info = None
        self.current_order = None  # Selected product for order

    def add_query(self, query: str):
        self.user_query_history.append({
            'query': query,
            'timestamp': datetime.now().isoformat()
        })

    def update_specs(self, new_specs: Dict):
        """Yeni spesifikasyonları mevcut bilgilerle birleştir"""
        for key, value in new_specs.items():
            if value is not None:
                if key == 'features' and isinstance(value, list):
                    self.extracted_specs[key].extend(value)
                    self.extracted_specs[key] = list(set(self.extracted_specs[key]))  # Unique
                else:
                    self.extracted_specs[key] = value

class B2BConversationSystem:
    def __init__(self, db_connection: str):
        self.db_connection = db_connection
        self.context = ConversationContext()
        
        # Turkish friendly words
        self.friendly_words = ['canım', 'canim', 'kardeşim', 'kardesim', 'dostum', 'abi', 'abla', 'reis']
        
        # Product features
        self.feature_keywords = {
            'magnetic': ['manyetik', 'magnetik', 'magnet'],
            'cushioned': ['amortisörlü', 'amortisör', 'yastıklı'],
            'double_acting': ['çift etkili', 'double acting'],
            'single_acting': ['tek etkili', 'single acting'],
            'stainless': ['paslanmaz', 'inox', 'stainless'],
            'pneumatic': ['pnömatik', 'havalı']
        }

    def parse_user_input(self, query: str) -> Dict:
        """Kullanıcı girdisini parse et"""
        query_upper = query.upper()
        parsed = {
            'diameter': None,
            'stroke': None,
            'features': [],
            'quantity': None,
            'tone': 'professional'
        }
        
        # Çap detection
        cap_patterns = [
            r'(\d+)\s*(?:CAP|CAPLI|ÇAP|ÇAPLI|LUK|MM\s*ÇAP)',
            r'Ø(\d+)',
            r'(\d+)\s*MM(?!\s*STROK)'
        ]
        for pattern in cap_patterns:
            matches = re.findall(pattern, query_upper)
            if matches:
                parsed['diameter'] = int(matches[0])
                break
        
        # Strok detection
        strok_patterns = [r'(\d+)\s*(?:STROK|STROKLU|MM\s*STROK)']
        for pattern in strok_patterns:
            matches = re.findall(pattern, query_upper)
            if matches:
                parsed['stroke'] = int(matches[0])
                break
        
        # Quantity detection - only if it's clearly quantity, not dimension
        quantity_patterns = [r'(\d+)\s*(?:ADET|TANE|PARÇA|PIECE)']
        for pattern in quantity_patterns:
            matches = re.findall(pattern, query_upper)
            if matches:
                parsed['quantity'] = int(matches[0])
                break
        
        # Feature detection
        for feature, keywords in self.feature_keywords.items():
            if any(keyword.upper() in query_upper for keyword in keywords):
                parsed['features'].append(feature)
        
        # Tone detection
        if any(word in query.lower() for word in self.friendly_words):
            parsed['tone'] = 'friendly'
        
        return parsed

    def get_stroke_options(self, diameter: int) -> Dict:
        """Belirli çap için strok seçenekleri getir"""
        try:
            with psycopg2.connect(self.db_connection) as db:
                with db.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT p.malzeme_adi, i.current_stock, p.id
                        FROM products p 
                        LEFT JOIN inventory i ON p.id = i.product_id
                        WHERE p.malzeme_adi ILIKE %s AND COALESCE(i.current_stock, 0) > 0
                        LIMIT 20
                    """, (f'%{diameter}%',))
                    
                    results = cur.fetchall()
                    strokes = {}
                    
                    for row in results:
                        name, stock, product_id = row['malzeme_adi'], row['current_stock'], row['id']
                        
                        # Multiple stroke patterns
                        stroke_patterns = [
                            rf'{diameter}[*x×](\d+)',
                            rf'(\d+)[*x×]\s*{diameter}',
                            rf'{diameter}\s*/\s*(\d+)',
                        ]
                        
                        for pattern in stroke_patterns:
                            match = re.search(pattern, name.upper())
                            if match:
                                s = int(match.group(1))
                                if s != diameter:  # Don't count diameter as stroke
                                    if s not in strokes:
                                        strokes[s] = {'total_stock': 0, 'products': []}
                                    strokes[s]['total_stock'] += stock
                                    strokes[s]['products'].append({
                                        'id': product_id,
                                        'name': name,
                                        'stock': stock
                                    })
                                break
                    
                    return strokes
        except Exception as e:
            print(f"Veritabanı hatası: {e}")
            return {}

    def search_exact_product(self, diameter: int, stroke: int, features: List[str] = None) -> List[Dict]:
        """Tam spesifikasyonla ürün ara"""
        try:
            with psycopg2.connect(self.db_connection) as db:
                with db.cursor(cursor_factory=RealDictCursor) as cur:
                    # Base query
                    query = """
                        SELECT p.id, p.malzeme_adi, p.brand, p.unit_price, i.current_stock
                        FROM products p 
                        LEFT JOIN inventory i ON p.id = i.product_id
                        WHERE p.malzeme_adi ILIKE %s AND COALESCE(i.current_stock, 0) > 0
                        ORDER BY i.current_stock DESC LIMIT 10
                    """
                    
                    # Create search pattern
                    pattern = f'%{diameter}%{stroke}%'
                    cur.execute(query, (pattern,))
                    
                    results = []
                    for row in cur.fetchall():
                        product = {
                            'id': row['id'],
                            'name': row['malzeme_adi'],
                            'brand': row['brand'],
                            'price': float(row['unit_price']) if row['unit_price'] else 0,
                            'stock': row['current_stock'],
                            'match_score': 0.8  # Base score
                        }
                        
                        # Feature matching bonus
                        if features:
                            name_lower = product['name'].lower()
                            matched_features = 0
                            for feature in features:
                                if any(keyword in name_lower for keyword in self.feature_keywords.get(feature, [])):
                                    matched_features += 1
                            product['match_score'] += (matched_features / len(features)) * 0.2
                        
                        results.append(product)
                    
                    return sorted(results, key=lambda x: (x['match_score'], x['stock']), reverse=True)
        except Exception as e:
            print(f"Ürün arama hatası: {e}")
            return []

    def generate_response(self, user_input: str) -> str:
        """Kullanıcı girdisine göre yanıt üret"""
        # Parse input
        parsed = self.parse_user_input(user_input)
        self.context.add_query(user_input)
        self.context.user_tone = parsed['tone']
        
        # Update context with new information
        self.context.update_specs(parsed)
        
        # Response generation based on conversation stage and available information
        diameter = self.context.extracted_specs['diameter']
        stroke = self.context.extracted_specs['stroke']
        features = self.context.extracted_specs['features']
        quantity = self.context.extracted_specs['quantity']
        
        response = ""
        
        if diameter and not stroke:
            # Stage: Need stroke information
            stroke_options = self.get_stroke_options(diameter)
            
            if stroke_options:
                total = sum(opt['total_stock'] for opt in stroke_options.values())
                count = len(stroke_options)
                
                if self.context.user_tone == 'friendly':
                    response = f"Hmm canım, {diameter}mm çaplı silindir için {count} farklı strok seçeneği var "
                    response += f"(toplam {total:.0f} adet stokta). Hangi strok uzunluğunu istiyorsun?\n\n"
                else:
                    response = f"{diameter}mm çaplı silindir için {count} farklı strok seçeneği mevcut "
                    response += f"(toplam {total:.0f} adet stokta). Hangi strok uzunluğunu tercih edersiniz?\n\n"
                
                response += "🔧 MEVCUT SEÇENEKLER:\n"
                for stroke_val, info in sorted(stroke_options.items(), key=lambda x: x[1]['total_stock'], reverse=True)[:5]:
                    response += f"  • {stroke_val}mm strok: {info['total_stock']:.0f} adet stokta\n"
                
                self.context.conversation_stage = 'spec_gathering'
            else:
                response = f"Maalesef {diameter}mm çaplı silindir stokta yok. Başka bir çap deneyelim mi?"
        
        elif stroke and not diameter:
            # Stage: Need diameter information
            if self.context.user_tone == 'friendly':
                response = f"Canım, {stroke}mm strok için çap bilgisi lazım! "
                response += "Çap söylersen en uygun ürünü bulayım."
            else:
                response = f"{stroke}mm stroklu silindir için çap belirtirseniz "
                response += "size en uygun seçenekleri sunabilirim."
            
            self.context.conversation_stage = 'spec_gathering'
        
        elif diameter and stroke:
            # Stage: Complete specs - show products
            products = self.search_exact_product(diameter, stroke, features)
            
            if products:
                if self.context.user_tone == 'friendly':
                    response = f"Süper! {diameter}mm x {stroke}mm silindir buldum. "
                else:
                    response = f"Mükemmel! {diameter}mm x {stroke}mm silindir için {len(products)} seçenek mevcut:\n\n"
                
                response += "🎯 ÜRÜN SEÇENEKLERİ:\n"
                for i, product in enumerate(products[:3], 1):
                    response += f"{i}. {product['name']} ({product['brand']})\n"
                    response += f"   💰 Fiyat: {product['price']:.2f} TL | 📦 Stok: {product['stock']:.0f} adet\n\n"
                
                if self.context.user_tone == 'friendly':
                    response += "Hangi ürünü seçmek istiyorsun? Numara söyle, sipariş hazırlayayım!"
                else:
                    response += "Hangi ürünü tercih edersiniz? Numarasını belirtirseniz sipariş işlemine başlayabiliriz."
                
                self.context.selected_products = products
                self.context.conversation_stage = 'product_selection'
            else:
                response = f"Maalesef {diameter}mm x {stroke}mm silindir şu an stokta yok. "
                response += "Alternatif boyutlar önerebilirim?"
        
        else:
            # Stage: Initial - need basic info
            if self.context.user_tone == 'friendly':
                response = "Canım, hangi silindir arıyorsun? Çap ve strok bilgisi versen "
                response += "sana en uygun ürünleri bulabilirim!\n\n"
                response += "💡 Örnek: '100mm çap, 400mm strok silindir istiyorum'"
            else:
                response = "Silindir aramanız için boyut bilgilerine ihtiyacım var.\n\n"
                response += "📋 Gerekli bilgiler:\n"
                response += "  • Çap (örn: 100mm)\n"
                response += "  • Strok uzunluğu (örn: 400mm)\n"
                response += "  • Adet (opsiyonel)\n"
                response += "  • Özel özellikler (magnetik, amortisörlü, vb.)"
            
            self.context.conversation_stage = 'initial'
        
        return response

    def handle_product_selection(self, selection: str) -> str:
        """Ürün seçimi işle"""
        try:
            selection_num = int(selection.strip())
            if 1 <= selection_num <= len(self.context.selected_products):
                selected_product = self.context.selected_products[selection_num - 1]
                
                response = f"✅ Seçiminiz: {selected_product['name']}\n"
                response += f"💰 Birim Fiyat: {selected_product['price']:.2f} TL\n"
                response += f"📦 Mevcut Stok: {selected_product['stock']:.0f} adet\n\n"
                
                # Store selected product for later use
                self.context.current_order = (selected_product, None)  # Product, quantity will be set later
                
                if self.context.user_tone == 'friendly':
                    response += "Kaç adet istiyorsun? Sipariş detaylarını hazırlayayım!"
                else:
                    response += "Kaç adet sipariş vermek istiyorsunuz?"
                
                self.context.conversation_stage = 'order_creation'
                return response
            else:
                return "Geçersiz seçim. Lütfen listelenen numaralardan birini seçin."
        except ValueError:
            return "Lütfen ürün numarasını yazın (örn: 1, 2, 3)"

    def handle_quantity_input(self, quantity_str: str) -> str:
        """Adet girdisini işle"""
        try:
            quantity = int(quantity_str.strip())
            if quantity <= 0:
                return "Lütfen geçerli bir adet sayısı girin (1 veya daha fazla)."
            
            if not self.context.current_order:
                return "Ürün seçimi bulunamadı. Lütfen tekrar başlayın."
            
            product, _ = self.context.current_order
            
            if quantity > product['stock']:
                if self.context.user_tone == 'friendly':
                    return f"Canım, stokta sadece {product['stock']:.0f} adet var. Daha az yazabilir misin?"
                else:
                    return f"Maalesef stokta {product['stock']:.0f} adet mevcut. Lütfen daha az adet belirtin."
            
            # Update order with quantity
            self.context.current_order = (product, quantity)
            self.context.conversation_stage = 'order_confirmation'
            
            return self.create_order_summary(quantity, product)
            
        except ValueError:
            return "Lütfen geçerli bir sayı girin."

    def create_order_summary(self, quantity: int, product: Dict) -> str:
        """Sipariş özeti oluştur"""
        total_price = quantity * product['price']
        
        response = "📋 SİPARİŞ ÖZETİ\n"
        response += "=" * 30 + "\n"
        response += f"Ürün: {product['name']}\n"
        response += f"Marka: {product['brand']}\n"
        response += f"Adet: {quantity}\n"
        response += f"Birim Fiyat: {product['price']:.2f} TL\n"
        response += f"Toplam: {total_price:.2f} TL\n\n"
        
        if self.context.user_tone == 'friendly':
            response += "Sipariş bilgileri tamam mı canım? 'Evet' dersen kaydet edeyim!"
        else:
            response += "Sipariş bilgilerini onaylıyor musunuz? (Evet/Hayır)"
        
        return response

    def save_order(self, product: Dict, quantity: int) -> bool:
        """Siparişi veritabanına kaydet"""
        try:
            with psycopg2.connect(self.db_connection) as db:
                with db.cursor() as cur:
                    # Get customer ID for testing (CONV001)
                    cur.execute("SELECT id FROM customers WHERE customer_code = 'CONV001' LIMIT 1")
                    customer_row = cur.fetchone()
                    customer_id = customer_row[0] if customer_row else 1
                    
                    total_price = quantity * product['price']
                    
                    # Create conversation context
                    context_data = {
                        'specs': self.context.extracted_specs,
                        'conversation_history': self.context.user_query_history[-5:],  # Last 5 queries
                        'selected_product_info': product,
                        'user_tone': self.context.user_tone
                    }
                    
                    # Insert order
                    cur.execute("""
                        INSERT INTO conversation_orders 
                        (customer_id, product_id, quantity, unit_price, total_price, 
                         conversation_context, order_status, user_query, ai_response)
                        VALUES (%s, %s, %s, %s, %s, %s, 'confirmed', %s, %s)
                        RETURNING id
                    """, (
                        customer_id,
                        product['id'],
                        quantity,
                        product['price'],
                        total_price,
                        json.dumps(context_data),
                        self.context.user_query_history[-1]['query'] if self.context.user_query_history else '',
                        'Sipariş başarıyla oluşturuldu'
                    ))
                    
                    order_id = cur.fetchone()[0]
                    db.commit()
                    
                    return order_id
        except Exception as e:
            print(f"Sipariş kayıt hatası: {e}")
            return False

    def handle_order_confirmation(self, confirmation: str) -> str:
        """Sipariş onaylama işle"""
        if not self.context.current_order:
            return "Sipariş bilgisi bulunamadı. Lütfen tekrar başlayın."
        
        if confirmation.lower() in ['evet', 'yes', 'tamam', 'onayla', 'kaydet']:
            product, quantity = self.context.current_order
            order_id = self.save_order(product, quantity)
            
            if order_id:
                response = "✅ SİPARİŞ BAŞARILI!\n"
                response += f"📋 Sipariş No: {order_id}\n"
                response += f"🎯 Ürün: {product['name']}\n"
                response += f"📦 Adet: {quantity}\n"
                response += f"💰 Toplam: {quantity * product['price']:.2f} TL\n\n"
                
                if self.context.user_tone == 'friendly':
                    response += "Siparişin hazır canım! Başka bir şey lazım mı?"
                else:
                    response += "Siparişiniz sisteme kaydedildi. Başka yardım edebileceğim bir konu var mı?"
                
                # Reset conversation
                self.context.conversation_stage = 'initial'
                self.context.current_order = None
                return response
            else:
                return "❌ Sipariş kaydedilirken hata oluştu. Lütfen tekrar deneyin."
        else:
            response = "Sipariş iptal edildi. "
            if self.context.user_tone == 'friendly':
                response += "Başka bir ürün bakalım mı canım?"
            else:
                response += "Başka bir ürün araması yapabilirsiniz."
            
            self.context.conversation_stage = 'initial'
            self.context.current_order = None
            return response

def main():
    """Ana conversation loop"""
    print("🤖 B2B Silindir AI - Konuşmalı Sipariş Sistemi")
    print("=" * 50)
    print("Merhaba! Size nasıl yardımcı olabilirim?")
    print("Çıkmak için 'quit' yazın.")
    print("-" * 50)
    
    # Initialize system
    db_connection = "postgresql://postgres:masterkey@localhost:5432/b2b_rag_system"
    conversation_system = B2BConversationSystem(db_connection)
    
    while True:
        try:
            user_input = input("\n👤 Siz: ").strip()
            
            if user_input.lower() in ['quit', 'q', 'exit', 'çıkış']:
                print("\n🤖 AI: İyi günler! Yardımcı olabildiysem ne mutlu bana!")
                break
            
            if not user_input:
                continue
            
            # Handle different conversation stages
            stage = conversation_system.context.conversation_stage
            
            if stage == 'product_selection' and user_input.isdigit():
                response = conversation_system.handle_product_selection(user_input)
            elif stage == 'order_creation' and user_input.isdigit():
                response = conversation_system.handle_quantity_input(user_input)
            elif stage == 'order_confirmation':
                response = conversation_system.handle_order_confirmation(user_input)
            else:
                response = conversation_system.generate_response(user_input)
            
            print(f"\n🤖 AI: {response}")
            
        except (KeyboardInterrupt, EOFError):
            print("\n\n🤖 AI: İyi günler!")
            break
        except Exception as e:
            print(f"\n❌ Hata: {e}")
            continue

if __name__ == "__main__":
    main()
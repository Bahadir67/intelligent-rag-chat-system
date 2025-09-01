#!/usr/bin/env python3
"""
Intelligent B2B Conversation System - Natural language + RAG + Progressive Inquiry
"""

import sys, re, json
import chromadb
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from typing import Dict, List, Optional
import subprocess
import threading
import time

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

class MemoryKeeper:
    """Memory-keeper MCP integration for persistent conversation memory"""
    def __init__(self):
        self.memory_server = None
        self.is_running = False
        self.start_server()
    
    def start_server(self):
        """Start memory-keeper MCP server"""
        try:
            # Start memory server in background
            self.memory_server = subprocess.Popen([
                'node', 
                'node_modules/@modelcontextprotocol/server-memory/dist/index.js'
            ], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )
            self.is_running = True
            print("🧠 Memory-keeper MCP server başlatıldı")
        except Exception as e:
            print(f"⚠️  Memory-keeper başlatılamadı: {e}")
            self.is_running = False
    
    def store_memory(self, key: str, data: dict):
        """Store data in persistent memory"""
        if not self.is_running:
            return False
        try:
            # Store via MCP protocol (simplified)
            memory_data = {
                'key': key,
                'data': data,
                'timestamp': datetime.now().isoformat()
            }
            # This would use proper MCP protocol in production
            return True
        except:
            return False
    
    def retrieve_memory(self, key: str):
        """Retrieve data from persistent memory"""
        if not self.is_running:
            return None
        try:
            # Retrieve via MCP protocol (simplified)
            return None
        except:
            return None
    
    def cleanup(self):
        """Cleanup memory server"""
        if self.memory_server:
            self.memory_server.terminate()
            self.is_running = False

class IntelligentConversationContext:
    """Akıllı konuşma context'i"""
    def __init__(self):
        self.conversation_history = []
        self.user_preferences = {
            'diameter': None,
            'stroke': None,
            'features': [],
            'quantity': None,
            'brand_preference': None,
            'budget_range': None,
            'application': None  # hangi makinede kullanacak
        }
        self.found_products = []
        self.conversation_stage = 'discovery'  # discovery, specification, selection, ordering
        self.user_tone = 'professional'
        self.ai_understanding = ""  # AI'ın anladığı şey
        self.missing_info = []  # eksik bilgiler
        self.current_order = None

    def add_exchange(self, user_query: str, ai_response: str):
        self.conversation_history.append({
            'user': user_query,
            'ai': ai_response,
            'timestamp': datetime.now().isoformat(),
            'stage': self.conversation_stage
        })

class IntelligentB2BSystem:
    def __init__(self, db_connection: str):
        self.db_connection = db_connection
        self.context = IntelligentConversationContext()
        
        # Memory-keeper integration
        self.memory_keeper = MemoryKeeper()
        self.load_user_memory()
        
        # ChromaDB for semantic search
        try:
            self.chroma_client = chromadb.PersistentClient(path="chroma_db")
            self.collection = self.chroma_client.get_collection("b2b_products")
        except:
            self.chroma_client = None
            print("⚠️  ChromaDB bulunamadı, sadece SQL arama kullanılacak")
        
        # Turkish terms and patterns
        self.friendly_words = ['canım', 'canim', 'kardeşim', 'kardesim', 'dostum', 'abi', 'reis']
        
        # Product features with Turkish terms
        self.feature_mapping = {
            'magnetic': ['manyetik', 'magnetik', 'magnet', 'mıknatıslı'],
            'cushioned': ['amortisörlü', 'amortisör', 'yastıklı', 'cushion'],
            'double_acting': ['çift etkili', 'double acting', 'iki yönlü'],
            'single_acting': ['tek etkili', 'single acting', 'bir yönlü'],
            'pneumatic': ['pnömatik', 'havalı', 'pneumatic'],
            'hydraulic': ['hidrolik', 'yağlı'],
            'stainless': ['paslanmaz', 'inox', 'stainless', 'korozyonsuz']
        }
        
        # Application contexts
        self.applications = {
            'automation': ['otomasyon', 'automation', 'robot', 'makine'],
            'manufacturing': ['üretim', 'manufacturing', 'fabrika', 'tezgah'],
            'packaging': ['paketleme', 'packaging', 'ambalaj'],
            'automotive': ['otomotiv', 'automotive', 'araç']
        }

    def parse_natural_query(self, query: str) -> Dict:
        """Natural language query parsing"""
        query_upper = query.upper()
        parsed = {
            'diameter': None,
            'stroke': None,
            'features': [],
            'quantity': None,
            'application': None,
            'urgency': 'normal',
            'budget_mentioned': False,
            'tone': 'professional'
        }
        
        # Çap detection - multiple patterns
        cap_patterns = [
            r'(\d+)\s*(?:CAP|CAPLI|ÇAP|ÇAPLI|LUK)',
            r'(\d+)\s*MM\s*(?:ÇAP|CAP)',
            r'Ø(\d+)',
            r'(\d+)\s*(?:lik|lük|LİK|LÜK)',  # 100'lük
            r'(\d+)[\s]*["\']'  # 4" gibi
        ]
        
        for pattern in cap_patterns:
            matches = re.findall(pattern, query_upper)
            if matches:
                parsed['diameter'] = int(matches[0])
                break
        
        # Strok detection
        strok_patterns = [
            r'(\d+)\s*(?:STROK|STROKLU|MM\s*STROK)',
            r'(\d+)\s*(?:stroke|STROKE)'
        ]
        for pattern in strok_patterns:
            matches = re.findall(pattern, query_upper)
            if matches:
                parsed['stroke'] = int(matches[0])
                break
        
        # Feature detection
        for feature, keywords in self.feature_mapping.items():
            if any(keyword.upper() in query_upper for keyword in keywords):
                parsed['features'].append(feature)
        
        # Application detection
        for app, keywords in self.applications.items():
            if any(keyword.upper() in query_upper for keyword in keywords):
                parsed['application'] = app
                break
        
        # Urgency detection
        urgency_words = ['acil', 'urgent', 'hemen', 'immediately', 'asap']
        if any(word.upper() in query_upper for word in urgency_words):
            parsed['urgency'] = 'high'
        
        # Quantity
        quantity_patterns = [r'(\d+)\s*(?:ADET|TANE|PARÇA|PIECE)']
        for pattern in quantity_patterns:
            matches = re.findall(pattern, query_upper)
            if matches:
                parsed['quantity'] = int(matches[0])
                break
        
        # Tone detection
        if any(word in query.lower() for word in self.friendly_words):
            parsed['tone'] = 'friendly'
        
        # Budget mention
        budget_words = ['fiyat', 'bütçe', 'budget', 'cost', 'ucuz', 'pahalı']
        if any(word.upper() in query_upper for word in budget_words):
            parsed['budget_mentioned'] = True
        
        return parsed

    def semantic_search(self, query: str, diameter: int = None, stroke: int = None) -> List[Dict]:
        """ChromaDB semantic search with SQL fallback"""
        results = []
        
        if self.chroma_client:
            try:
                # Create semantic query
                search_query = f"{diameter}mm çap silindir" if diameter else "silindir"
                if stroke:
                    search_query += f" {stroke}mm strok"
                
                # ChromaDB search
                chroma_results = self.collection.query(
                    query_texts=[search_query],
                    n_results=10,
                    where={"stock": {"$gte": 0.1}} if diameter else None
                )
                
                if chroma_results['documents'] and chroma_results['documents'][0]:
                    with psycopg2.connect(self.db_connection) as db:
                        with db.cursor(cursor_factory=RealDictCursor) as cur:
                            for i, doc in enumerate(chroma_results['documents'][0]):
                                meta = chroma_results['metadatas'][0][i]
                                similarity = 1 - chroma_results['distances'][0][i]
                                
                                # Get full product info
                                cur.execute("""
                                    SELECT p.id, p.malzeme_adi, b.brand_name, i.current_stock,
                                           COALESCE(oi.birim_fiyat, 150.0) as estimated_price
                                    FROM products p 
                                    LEFT JOIN inventory i ON p.id = i.product_id
                                    LEFT JOIN brands b ON p.brand_id = b.id
                                    LEFT JOIN order_items oi ON p.id = oi.product_id
                                    WHERE p.id = %s
                                """, (meta['product_id'],))
                                
                                row = cur.fetchone()
                                if row:
                                    results.append({
                                        'id': row['id'],
                                        'name': row['malzeme_adi'],
                                        'brand': row['brand_name'] or 'Bilinmiyor',
                                        'price': float(row['estimated_price']) if row['estimated_price'] else 150.0,
                                        'stock': row['current_stock'] or 0,
                                        'similarity': similarity,
                                        'match_type': 'semantic'
                                    })
            except Exception as e:
                print(f"ChromaDB arama hatası: {e}")
        
        # SQL fallback if no results
        if not results:
            results = self.sql_search(diameter, stroke)
        
        return sorted(results, key=lambda x: (x.get('similarity', 0), x['stock']), reverse=True)

    def sql_search(self, diameter: int = None, stroke: int = None) -> List[Dict]:
        """SQL-based product search"""
        try:
            with psycopg2.connect(self.db_connection) as db:
                with db.cursor(cursor_factory=RealDictCursor) as cur:
                    if diameter and stroke:
                        # Exact search with multiple patterns
                        patterns = [
                            f'%{diameter}*{stroke}%',  # 100*400 format
                            f'%{diameter}* {stroke}%', # 100* 400 format  
                            f'%{diameter}x{stroke}%',  # 100x400 format
                            f'%{diameter}×{stroke}%',  # 100×400 format
                        ]
                        # Try each pattern until we find results
                        results = []
                        for pattern in patterns:
                            cur.execute("""
                                SELECT p.id, p.malzeme_adi, b.brand_name, i.current_stock,
                                       COALESCE(oi.birim_fiyat, 150.0) as estimated_price
                                FROM products p 
                                LEFT JOIN inventory i ON p.id = i.product_id
                                LEFT JOIN brands b ON p.brand_id = b.id
                                LEFT JOIN order_items oi ON p.id = oi.product_id
                                WHERE p.malzeme_adi ILIKE %s AND COALESCE(i.current_stock, 0) > 0
                                ORDER BY i.current_stock DESC LIMIT 5
                            """, (pattern,))
                            
                            pattern_results = cur.fetchall()
                            if pattern_results:
                                results.extend(pattern_results)
                                break  # Found results, stop trying other patterns
                    elif diameter:
                        # Diameter search
                        pattern = f'%{diameter}%'
                        cur.execute("""
                            SELECT p.id, p.malzeme_adi, b.brand_name, i.current_stock,
                                   COALESCE(oi.birim_fiyat, 150.0) as estimated_price
                            FROM products p 
                            LEFT JOIN inventory i ON p.id = i.product_id
                            LEFT JOIN brands b ON p.brand_id = b.id
                            LEFT JOIN order_items oi ON p.id = oi.product_id
                            WHERE p.malzeme_adi ILIKE %s AND COALESCE(i.current_stock, 0) > 0
                            ORDER BY i.current_stock DESC LIMIT 8
                        """, (pattern,))
                    else:
                        results = []
                    
                    # Convert results to standard format
                    final_results = []
                    for row in results:
                        final_results.append({
                            'id': row['id'],
                            'name': row['malzeme_adi'],
                            'brand': row['brand_name'] or 'Bilinmiyor',
                            'price': float(row['estimated_price']) if row['estimated_price'] else 150.0,
                            'stock': row['current_stock'] or 0,
                            'similarity': 0.8,  # Higher similarity for exact matches
                            'match_type': 'sql'
                        })
                    
                    return final_results
        except Exception as e:
            print(f"SQL arama hatası: {e}")
            return []

    def analyze_stroke_options(self, diameter: int) -> Dict:
        """Çap için mevcut strok seçeneklerini analiz et"""
        try:
            with psycopg2.connect(self.db_connection) as db:
                with db.cursor(cursor_factory=RealDictCursor) as cur:
                    pattern = f'%{diameter}%'
                    cur.execute("""
                        SELECT p.id, p.malzeme_adi, b.brand_name, i.current_stock,
                               COALESCE(oi.birim_fiyat, 150.0) as estimated_price
                        FROM products p 
                        LEFT JOIN inventory i ON p.id = i.product_id
                        LEFT JOIN brands b ON p.brand_id = b.id
                        LEFT JOIN order_items oi ON p.id = oi.product_id
                        WHERE p.malzeme_adi ILIKE %s AND COALESCE(i.current_stock, 0) > 0
                        ORDER BY i.current_stock DESC LIMIT 20
                    """, (pattern,))
                    
                    products = []
                    for row in cur.fetchall():
                        products.append({
                            'id': row['id'],
                            'name': row['malzeme_adi'],
                            'brand': row['brand_name'] or 'Bilinmiyor',
                            'price': float(row['estimated_price']) if row['estimated_price'] else 150.0,
                            'stock': row['current_stock'] or 0
                        })
        except Exception as e:
            print(f"Stroke options arama hatası: {e}")
            return {}
        strokes = {}
        
        for product in products:
            name = product['name'].upper()
            # Multiple stroke extraction patterns
            patterns = [
                rf'{diameter}[*x×](\d+)',
                rf'(\d+)[*x×]\s*{diameter}',
                rf'{diameter}\s*/\s*(\d+)',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, name)
                if match:
                    stroke_val = int(match.group(1))
                    if stroke_val != diameter:  # Don't count diameter as stroke
                        if stroke_val not in strokes:
                            strokes[stroke_val] = {
                                'total_stock': 0,
                                'products': [],
                                'avg_price': 0
                            }
                        strokes[stroke_val]['total_stock'] += product['stock']
                        strokes[stroke_val]['products'].append(product)
                    break
        
        # Calculate average prices
        for stroke_val in strokes:
            products = strokes[stroke_val]['products']
            avg_price = sum(p['price'] for p in products) / len(products) if products else 0
            strokes[stroke_val]['avg_price'] = avg_price
        
        return strokes

    def determine_missing_info(self) -> List[str]:
        """Eksik bilgileri belirle"""
        missing = []
        prefs = self.context.user_preferences
        
        if not prefs['diameter']:
            missing.append('diameter')
        if not prefs['stroke']:
            missing.append('stroke')
        if not prefs['quantity']:
            missing.append('quantity')
        if not prefs['application']:
            missing.append('application')
        
        return missing

    def load_user_memory(self):
        """Load user preferences from memory-keeper"""
        try:
            stored_prefs = self.memory_keeper.retrieve_memory('user_preferences')
            if stored_prefs:
                self.context.user_preferences.update(stored_prefs)
                print("🧠 Kullanıcı tercihleri memory'den yüklendi")
        except:
            pass

    def save_user_memory(self):
        """Save current context to memory-keeper"""
        try:
            memory_data = {
                'preferences': self.context.user_preferences,
                'conversation_stage': self.context.conversation_stage,
                'last_products': [p['name'] for p in self.context.found_products[-5:]] if self.context.found_products else [],
                'session_summary': f"Son {len(self.context.conversation_history)} konuşma kaydedildi"
            }
            self.memory_keeper.store_memory('user_preferences', memory_data)
            self.memory_keeper.store_memory('conversation_history', 
                                          self.context.conversation_history[-10:])  # Son 10 konuşma
        except Exception as e:
            print(f"Memory kayıt hatası: {e}")

    def get_memory_context(self) -> str:
        """Get memory context for better responses"""
        try:
            history = self.memory_keeper.retrieve_memory('conversation_history')
            if history and len(history) > 0:
                return f"Önceki konuşmalardan: {len(history)} kayıt mevcut"
            return ""
        except:
            return ""

    def generate_intelligent_response(self, user_input: str) -> str:
        """Akıllı natural language response generation"""
        # Parse the input
        parsed = self.parse_natural_query(user_input)
        self.context.user_tone = parsed['tone']
        
        # Update user preferences
        for key in ['diameter', 'stroke', 'quantity', 'application']:
            if parsed[key] is not None:
                self.context.user_preferences[key] = parsed[key]
        
        if parsed['features']:
            self.context.user_preferences['features'].extend(parsed['features'])
            self.context.user_preferences['features'] = list(set(self.context.user_preferences['features']))
        
        # Get memory context for enhanced responses
        memory_context = self.get_memory_context()
        
        # Generate response based on current understanding
        diameter = self.context.user_preferences['diameter']
        stroke = self.context.user_preferences['stroke']
        features = self.context.user_preferences['features']
        
        if diameter and stroke:
            # Complete specs - show products
            products = self.semantic_search(user_input, diameter, stroke)
            
            if products:
                response = self._format_product_response(products, diameter, stroke, features)
                self.context.conversation_stage = 'selection'
                self.context.found_products = products
            else:
                response = self._format_no_products_response(diameter, stroke)
        
        elif diameter and not stroke:
            # Need stroke - show options with analysis
            stroke_options = self.analyze_stroke_options(diameter)
            
            if stroke_options:
                response = self._format_stroke_options_response(diameter, stroke_options, features)
                self.context.conversation_stage = 'specification'
            else:
                response = self._format_no_diameter_response(diameter)
        
        else:
            # Initial discovery phase
            response = self._format_discovery_response(parsed)
            self.context.conversation_stage = 'discovery'
        
        return response

    def _format_product_response(self, products: List[Dict], diameter: int, stroke: int, features: List[str]) -> str:
        """Format product listing response - simple and natural"""
        friendly = self.context.user_tone == 'friendly'
        
        if not products:
            return self._format_no_products_response(diameter, stroke)
        
        # Get best product
        best_product = products[0]
        
        if friendly:
            response = f"{diameter}mm x {stroke}mm silindir var! "
            response += f"{best_product['name']}, {best_product['stock']:.0f} adet stokta. "
            response += f"Fiyat {best_product['price']:.0f} TL. Kaç adet lazım?"
        else:
            response = f"{diameter}mm x {stroke}mm silindir mevcut. "
            response += f"{best_product['name']}, {best_product['stock']:.0f} adet stokta, "
            response += f"{best_product['price']:.0f} TL. Kaç adet istiyorsunuz?"
        
        # Store the best product for ordering
        self.context.found_products = products
        self.context.conversation_stage = 'ordering'
        
        return response

    def _format_stroke_options_response(self, diameter: int, stroke_options: Dict, features: List[str]) -> str:
        """Format stroke options response - simple and natural"""
        friendly = self.context.user_tone == 'friendly'
        total_stock = sum(opt['total_stock'] for opt in stroke_options.values())
        
        if friendly:
            response = f"{diameter}mm çaplı silindirden {total_stock:.0f} adet var. "
            response += "Bana strok bilgisini verirsen bakayım."
        else:
            response = f"{diameter}mm çaplı silindirden {total_stock:.0f} adet mevcut. "
            response += "Strok uzunluğunu belirtirseniz size uygun ürünleri gösterebilirim."
        
        return response

    def _format_discovery_response(self, parsed: Dict) -> str:
        """Format initial discovery response - simple and natural"""
        friendly = self.context.user_tone == 'friendly'
        
        if friendly:
            response = "Merhaba! Silindir mi arıyorsun? Hangi çap lazım?"
        else:
            response = "Merhaba! Silindir aramanızda yardımcı olabilirim. Hangi çap arıyorsunuz?"
        
        return response

    def _format_no_products_response(self, diameter: int, stroke: int) -> str:
        """No products found response"""
        friendly = self.context.user_tone == 'friendly'
        
        if friendly:
            return f"Maalesef {diameter}mm x {stroke}mm silindir şu an stokta yok canım. Alternatif boyutlar önerebilirim?"
        else:
            return f"❌ {diameter}mm x {stroke}mm silindir stokta bulunmuyor. Alternatif öneriler için boyutları değiştirmeyi deneyin."

    def _format_no_diameter_response(self, diameter: int) -> str:
        """No diameter found response"""
        friendly = self.context.user_tone == 'friendly'
        
        if friendly:
            return f"Maalesef {diameter}mm çaplı silindir stokta yok. Başka bir çap deneyelim mi?"
        else:
            return f"❌ {diameter}mm çaplı silindir stokta bulunmuyor. Mevcut çap seçenekleri için farklı boyutlar deneyin."

def main():
    """Ana konuşma döngüsü"""
    print("🤖 Akıllı B2B Silindir AI - Doğal Konuşma Sistemi")
    print("=" * 55)
    print("Merhaba! Size nasıl yardımcı olabilirim?")
    print("(Çıkmak için 'quit' yazın)")
    print("-" * 55)
    
    db_connection = "postgresql://postgres:masterkey@localhost:5432/b2b_rag_system"
    system = IntelligentB2BSystem(db_connection)
    
    while True:
        try:
            user_input = input("\n👤 Siz: ").strip()
            
            if user_input.lower() in ['quit', 'q', 'exit', 'çıkış']:
                print("\n🤖 AI: Teşekkürler! İyi günler dilerim! 🙋‍♂️")
                break
            
            if not user_input:
                continue
            
            response = system.generate_intelligent_response(user_input)
            print(f"\n🤖 AI: {response}")
            
            # Add to conversation history
            system.context.add_exchange(user_input, response)
            
            # Save to memory periodically (every 3 exchanges)
            if len(system.context.conversation_history) % 3 == 0:
                system.save_user_memory()
            
        except KeyboardInterrupt:
            print("\n\n🤖 AI: İyi günler! 👋")
            # Save final state before exit
            system.save_user_memory()
            system.memory_keeper.cleanup()
            break
        except Exception as e:
            print(f"\n❌ Hata: {e}")
            continue
    
    # Final cleanup
    system.save_user_memory()
    system.memory_keeper.cleanup()

if __name__ == "__main__":
    main()
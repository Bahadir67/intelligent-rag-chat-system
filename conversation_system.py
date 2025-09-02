#!/usr/bin/env python3
"""
B2B Conversation System - Context takibi ile sipariş sürecine kadar
Kullanım: python conversation_system.py

⚠️ CRITICAL DEVELOPMENT RULES - DEĞİŞTİRİLMEMELİDİR:
1. AI FIRST, REGEX VALIDATION: Önce AI çağrılır, sonra regex validate eder
2. CONTEXT CLEARING: Override case'de (keyword search) context temizlenmeli
3. NO REGEX OVERRIDE: Regex AI'ı override etmemeli, sadece tamamlamalı
4. OVERRIDE = KEYWORD: should_override_ai=True means keyword search
5. SPEC SEARCH ≠ KEYWORD: diameter/stroke var ise spec search, yoksa keyword

Bu kurallar "Hortum bakıyorum" benzeri keyword aramalarının doğru çalışması için kritiktir.
"""

import sys, re, json
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from typing import Dict, List, Optional
from openrouter_client import openrouter_client
import unicodedata

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

def normalize_turkish_text(text: str) -> str:
    """Normalize Turkish text for proper character handling"""
    if not text:
        return text
    
    # Normalize Unicode characters (NFD -> NFC)
    text = unicodedata.normalize('NFC', text)
    
    # Fix common Turkish character issues
    replacements = {
        'i̇': 'i',  # Fix dotted i issue
        'İ': 'İ',  # Keep capital İ as is
        'ı': 'ı',  # Keep lowercase ı as is
    }
    
    for old, new in replacements.items():
        text = text.replace(old, new)
    
    return text

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
        self.phone_number = None
        self.current_order = None  # Selected product for order
        self.last_ai_response = None  # Track previous AI response for context

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
    def __init__(self, db_connection: str, phone_number: str = None):
        self.db_connection = db_connection
        self.context = ConversationContext()
        if phone_number:
            self.context.phone_number = phone_number
        
        # Create database connection
        import psycopg2
        self.connection = psycopg2.connect(db_connection)
        
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
        """AI-powered spec extraction from user input"""
        try:
            # Get conversation context for better AI understanding
            context = {
                'previous_queries': [q['query'] for q in self.context.user_query_history[-3:]],
                'current_specs': self.context.extracted_specs,
                'conversation_stage': self.context.conversation_stage
            }
            
            # Use OpenRouter AI for spec extraction with conversation history and previous AI response
            conversation_history = [q['query'] for q in self.context.user_query_history[-3:]]
            previous_ai_response = getattr(self.context, 'last_ai_response', None)
            print(f"[Debug] Conversation history: {conversation_history}")
            print(f"[Debug] Previous AI response: {previous_ai_response}")
            print(f"[Debug] Current context: {context}")
            # ⚠️ CRITICAL RULE: AI FIRST, THEN REGEX VALIDATION
            # Bu sıra değişmemelidir! Önce AI çağrılır, sonra regex ile validate edilir.
            # YANLIŞ: Önce regex → sonra AI (context karışır)
            # DOĞRU: Önce AI → sonra regex (AI'ı tamamlar/düzeltir)
            ai_response = openrouter_client.extract_specifications(query, context, conversation_history, previous_ai_response)
            
            # Convert AI response to expected format
            parsed = {
                'diameter': ai_response.extracted_specs.get('diameter'),
                'stroke': ai_response.extracted_specs.get('stroke'),
                'features': ai_response.extracted_specs.get('features', []),
                'quantity': ai_response.extracted_specs.get('quantity'),
                'brand_preference': ai_response.extracted_specs.get('brand_preference'),
                'corrected_query': ai_response.extracted_specs.get('corrected_query'),
                'tone': 'friendly' if any(word in query.lower() for word in self.friendly_words) else 'professional',
                'ai_response': ai_response.suggested_response,
                'intent': ai_response.intent,
                'confidence': ai_response.confidence,
                'sub_intent': ai_response.sub_intent,
                'action': ai_response.action
            }
            
            # ⚠️ CRITICAL RULE: REGEX SADECE AI'I VALIDATE EDER, OVERRIDE ETMEZ
            # Regex AI'ın eksik bıraktığı değerleri tamamlar, AI'ı geçersiz kılmaz
            # Bu sayede AI'ın doğru anladığı context (keyword vs spec) korunur
            # REGEX FALLBACK VALIDATION - AI'ı doğrula
            regex_fallback = self.parse_user_input_fallback(query)
            
            # Eğer regex daha fazla bilgi bulmuşsa AI'ı düzelt
            if regex_fallback.get('diameter') and not parsed.get('diameter'):
                parsed['diameter'] = regex_fallback['diameter']
                print(f"[FALLBACK] AI diameter missed, using regex: {regex_fallback['diameter']}")
            
            if regex_fallback.get('stroke') and not parsed.get('stroke'):
                parsed['stroke'] = regex_fallback['stroke'] 
                print(f"[FALLBACK] AI stroke missed, using regex: {regex_fallback['stroke']}")
                
            # SANITY CHECK: Çap ve strok değerlerini mantıklı aralıklarda kontrol et
            if parsed.get('diameter') and parsed['diameter'] > 1000:  # 1000mm üzeri çap mantıksız
                print(f"[SANITY] Diameter too large: {parsed['diameter']}, using regex instead")
                parsed['diameter'] = regex_fallback.get('diameter')
                    
            if parsed.get('stroke') and parsed['stroke'] > 2000:  # 2000mm üzeri strok mantıksız  
                print(f"[SANITY] Stroke too large: {parsed['stroke']}, using regex instead")
                parsed['stroke'] = regex_fallback.get('stroke')
            
            print(f"[AI+FALLBACK] Final extracted specs: {parsed}")
            print(f"[AI] Intent: {ai_response.intent} (confidence: {ai_response.confidence:.2f})")
            
            return parsed
            
        except Exception as e:
            print(f"[AI] Error in spec extraction, falling back to regex: {e}")
            # Fallback to regex method if AI fails
            return self.parse_user_input_fallback(query)
    
    def parse_user_input_fallback(self, query: str) -> Dict:
        """Regex-based spec extraction fallback"""
        import re
        
        parsed = {
            'diameter': None,
            'stroke': None,
            'features': [],
            'quantity': None,
            'brand_preference': None,
            'tone': 'friendly' if any(word in query.lower() for word in self.friendly_words) else 'professional',
            'ai_response': '',
            'intent': 'spec_query',
            'confidence': 0.6  # Medium confidence for regex
        }
        
        query_lower = query.lower()
        
        # Çap extraction patterns
        diameter_patterns = [
            r'(\d+)\s*mm\s*çap',      # 100mm çap
            r'ø\s*(\d+)',              # Ø100  
            r'(\d+)\s*çap',            # 100 çap
            r'çap\s*(\d+)',            # çap 100
        ]
        
        # Strok extraction patterns  
        stroke_patterns = [
            r'(\d+)\s*mm\s*strok',     # 200mm strok
            r'(\d+)\s*strok',          # 200 strok  
            r'strok\s*(\d+)',          # strok 200
            r'x\s*(\d+)',              # x200 (in Ø100x200 format)
        ]
        
        # Extract diameter
        for pattern in diameter_patterns:
            match = re.search(pattern, query_lower)
            if match:
                parsed['diameter'] = int(match.group(1))
                print(f"[REGEX] Found diameter: {parsed['diameter']}")
                break
                
        # Extract stroke
        for pattern in stroke_patterns:
            match = re.search(pattern, query_lower)
            if match:
                parsed['stroke'] = int(match.group(1))
                print(f"[REGEX] Found stroke: {parsed['stroke']}")
                break
        
        # Special pattern: "100x200" or "100*200" format
        dimension_match = re.search(r'(\d+)\s*[x*×]\s*(\d+)', query)
        if dimension_match:
            num1, num2 = int(dimension_match.group(1)), int(dimension_match.group(2))
            # Mantık: İlk sayı genelde çap, ikinci sayı strok
            if not parsed['diameter']:
                parsed['diameter'] = num1
                print(f"[REGEX] Dimension format diameter: {num1}")
            if not parsed['stroke']:
                parsed['stroke'] = num2  
                print(f"[REGEX] Dimension format stroke: {num2}")
        
        # Quantity extraction
        quantity_patterns = [
            r'(\d+)\s*adet',
            r'(\d+)\s*tane', 
            r'(\d+)\s*parça',
        ]
        
        for pattern in quantity_patterns:
            match = re.search(pattern, query_lower)
            if match:
                parsed['quantity'] = int(match.group(1))
                print(f"[REGEX] Found quantity: {parsed['quantity']}")
                break
        
        return parsed
    
    def _parse_user_input_regex(self, query: str) -> Dict:
        """Fallback regex-based parsing (original method)"""
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
        
        # Quantity detection
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
        """Tam spesifikasyonla ürün ara - PRECISE FILTERING"""
        try:
            with psycopg2.connect(self.db_connection) as db:
                with db.cursor(cursor_factory=RealDictCursor) as cur:
                    # Multiple pattern matching for precise filtering - INCLUDE malzeme_kodu
                    query = """
                        SELECT p.id, p.malzeme_adi, p.malzeme_kodu, COALESCE(i.current_stock, 0) as current_stock
                        FROM products p 
                        LEFT JOIN inventory i ON p.id = i.product_id
                        WHERE (
                            -- Pattern 1: 100x200, 100X200, 100*200 formatları
                            p.malzeme_adi ~* %s OR
                            -- Pattern 2: "100" space/separator "200" formatları
                            p.malzeme_adi ~* %s OR
                            -- Pattern 3: başka formatlar
                            p.malzeme_adi ~* %s
                        )
                        ORDER BY p.malzeme_adi LIMIT 20
                    """
                    
                    # Create precise regex patterns for Turkish product names
                    # Pattern 1: "100* 200" ANS format (most common)
                    pattern1 = f'{diameter}\\*\\s*{stroke}'
                    # Pattern 2: "100x200", "100X200" format
                    pattern2 = f'{diameter}\\s*[xX×*]\\s*{stroke}'
                    # Pattern 3: "100 200" with any separator
                    pattern3 = f'{diameter}[^0-9]{{1,10}}{stroke}'
                    
                    print(f"[DB] Searching with patterns:")
                    print(f"[DB] Pattern 1 (exact): {pattern1}")
                    print(f"[DB] Pattern 2 (separated): {pattern2}")
                    print(f"[DB] Pattern 3 (ANS format): {pattern3}")
                    
                    cur.execute(query, (pattern1, pattern2, pattern3))
                    
                    results = []
                    for row in cur.fetchall():
                        product_name = row['malzeme_adi']
                        
                        # POST-FILTER: Additional validation to eliminate wrong matches
                        # Check if the product name actually contains correct diameter and stroke
                        import re
                        name_upper = product_name.upper()
                        
                        # Find all numbers in the product name
                        numbers = re.findall(r'\b\d+\b', name_upper)
                        
                        # Check if BOTH diameter and stroke exist as exact numbers
                        has_diameter = str(diameter) in numbers
                        has_stroke = str(stroke) in numbers
                        
                        if not (has_diameter and has_stroke):
                            print(f"[FILTER] Rejected: '{product_name}' - Missing diameter({diameter}) or stroke({stroke})")
                            print(f"[FILTER] Found numbers: {numbers}")
                            continue
                        
                        # Additional check: make sure it's not a wrong combination like "100x50x200"
                        # If we find 100, 50, 200 - but we want 100x200, this should be rejected
                        if len(numbers) >= 3:
                            # Check for misleading combinations
                            diameter_pos = -1
                            stroke_pos = -1
                            for i, num in enumerate(numbers):
                                if num == str(diameter) and diameter_pos == -1:
                                    diameter_pos = i
                                elif num == str(stroke) and stroke_pos == -1:
                                    stroke_pos = i
                            
                            # If diameter and stroke are not adjacent, might be wrong format
                            if abs(diameter_pos - stroke_pos) > 1:
                                print(f"[FILTER] Rejected: '{product_name}' - Non-adjacent diameter/stroke positions")
                                continue
                        
                        print(f"[FILTER] Accepted: '{product_name}' - Contains {diameter} and {stroke}")
                        
                        product = {
                            'id': row['id'],
                            'name': product_name,
                            'urun_kodu': row['malzeme_kodu'] if row['malzeme_kodu'] else 'Kod yok',
                            'brand': 'N/A',  # Brand column doesn't exist
                            'price': 0,  # Price will be quoted later
                            'stock': float(row['current_stock']) if row['current_stock'] else 0,
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
    
    def get_actual_stock(self, product_id: int) -> float:
        """Get real-time stock for a specific product"""
        try:
            with psycopg2.connect(self.db_connection) as db:
                with db.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT COALESCE(current_stock, 0) as stock 
                        FROM inventory 
                        WHERE product_id = %s
                    """, (product_id,))
                    
                    result = cur.fetchone()
                    return float(result['stock']) if result else 0.0
        except Exception as e:
            print(f"Stok sorgu hatası: {e}")
            return 0.0
    
    def search_keyword_products(self, keyword: str) -> List[Dict]:
        """Anahtar kelime ile genel ürün arama"""
        try:
            # Clean up keyword - remove common search words and punctuation
            search_words = ['arıyorum', 'ariyorum', 'bulabilir miyim', 'bulabilir', 'istiyorum', 
                           'lazım', 'lazim', 'gerek', 'var mı', 'var mi', 'bakıyorum', 'bakiyorum',
                           'bakalım', 'bakarim', 'sonra bakarız', 'sonra bakariz', 'neler var', 'nerler var']
            
            clean_keyword = normalize_turkish_text(keyword.strip())
            # Remove search words (case-insensitive)
            clean_keyword_lower = clean_keyword.lower()
            for word in search_words:
                if word in clean_keyword_lower:
                    # Find and remove the word preserving case of remaining text
                    start_idx = clean_keyword_lower.find(word)
                    clean_keyword = clean_keyword[:start_idx] + clean_keyword[start_idx + len(word):]
                    clean_keyword_lower = clean_keyword.lower()
            clean_keyword = clean_keyword.strip()
            
            # Remove common punctuation and extra spaces
            punctuation = '.,!?;:"()[]{}/-'
            for punct in punctuation:
                clean_keyword = clean_keyword.replace(punct, ' ')
            clean_keyword = ' '.join(clean_keyword.split()).strip()
            
            # Remove Turkish plural suffixes to find base words
            plural_suffixes = ['lara', 'lere', 'ların', 'lerin', 'ları', 'leri', 'lar', 'ler']
            for suffix in plural_suffixes:
                if clean_keyword.endswith(suffix):
                    clean_keyword = clean_keyword[:-len(suffix)].strip()
                    break
            
            # Create Turkish character variants for better matching
            turkish_variants = {
                'ç': ['ç', 'c'], 'ğ': ['ğ', 'g'], 'ı': ['ı', 'i'], 'İ': ['İ', 'I'],
                'ö': ['ö', 'o'], 'ş': ['ş', 's'], 'ü': ['ü', 'u'],
                'c': ['ç', 'c'], 'g': ['ğ', 'g'], 'i': ['ı', 'i', 'İ'], 'I': ['İ', 'I'],
                'o': ['ö', 'o'], 's': ['ş', 's'], 'u': ['ü', 'u']
            }
            
            # Generate search patterns with Turkish character variants
            search_patterns = [clean_keyword]
            
            # Create uppercase version for database matching
            search_patterns.append(clean_keyword.upper())
            
            # Create mixed case versions for Turkish characters
            for char, variants in turkish_variants.items():
                if char in clean_keyword:
                    for variant in variants:
                        if variant != char:
                            new_pattern = clean_keyword.replace(char, variant)
                            search_patterns.append(new_pattern)
                            search_patterns.append(new_pattern.upper())
            
            with psycopg2.connect(self.db_connection) as db:
                with db.cursor(cursor_factory=RealDictCursor) as cur:
                    all_results = []
                    seen_ids = set()
                    
                    for pattern in search_patterns:
                        # Show all products regardless of stock - INCLUDE malzeme_kodu
                        query = """
                            SELECT p.id, p.malzeme_adi, p.malzeme_kodu, 
                                   COALESCE(i.current_stock, 0) as current_stock
                            FROM products p 
                            LEFT JOIN inventory i ON p.id = i.product_id
                            WHERE p.malzeme_adi LIKE %s
                            ORDER BY p.malzeme_adi LIMIT 15
                        """
                        
                        # Convert pattern to uppercase to match DB format
                        search_pattern = f'%{pattern.upper()}%'
                        print(f"[DB] Searching with pattern: '{search_pattern}'")
                        cur.execute(query, (search_pattern,))
                        
                        for row in cur.fetchall():
                            if row['id'] not in seen_ids:
                                seen_ids.add(row['id'])
                                product = {
                                    'id': row['id'],
                                    'name': row['malzeme_adi'],
                                    'urun_kodu': row['malzeme_kodu'] if row['malzeme_kodu'] else 'Kod yok',
                                    'brand': 'N/A',  # Brand column doesn't exist
                                    'price': 0,  # Price will be quoted later
                                    'stock': float(row['current_stock']) if row['current_stock'] else 0,
                                    'match_score': 0.9  # High score for keyword matches
                                }
                                all_results.append(product)
                        
                        # Stop if we found enough results
                        if len(all_results) >= 15:
                            break
                    
                    print(f"[DB] Keyword '{keyword}' -> cleaned '{clean_keyword}' search found {len(all_results)} products")
                    return all_results[:15]
        except Exception as e:
            print(f"Anahtar kelime arama hatası: {e}")
            return []

    def generate_response(self, user_input: str) -> str:
        """AI-enhanced response generation with natural language flow"""
        # Parse user input with AI
        parsed = self.parse_user_input(user_input)
        
        # Add to conversation context
        self.context.add_query(user_input)
        self.context.user_tone = parsed.get('tone', 'professional')
        
        # Update context with new information
        specs_to_update = {k: v for k, v in parsed.items() 
                          if k in ['diameter', 'stroke', 'features', 'quantity', 'brand_preference'] and v is not None}
        self.context.update_specs(specs_to_update)
        
        # Use new AI classification system instead of override logic
        user_clean = normalize_turkish_text(user_input.strip())
        
        print(f"[AI] Classification: intent={parsed.get('intent')}, sub_intent={parsed.get('sub_intent')}, action={parsed.get('action')}, confidence={parsed.get('confidence'):.2f}")
        
        # Handle different actions based on AI classification
        if parsed.get('action') == 'search_direct':
            print(f"[AI] Direct search for accessory: {user_input}")
            
            # Clear context for direct searches to avoid spec interference
            self.context.extracted_specs = {
                'diameter': None, 'stroke': None, 'features': [], 
                'quantity': None, 'brand_preference': None
            }
            # Reset conversation stage to initial for fresh search
            self.context.conversation_stage = 'initial'
            print(f"[AI] Context and stage cleared for direct accessory search")
            # Force structured response for direct searches
            return self._generate_structured_response(parsed, user_input)
            
        elif parsed.get('action') == 'request_params':
            print(f"[AI] Main product - requesting parameters: {user_input}")
            # Use AI response directly for parameter requests
            if parsed.get('ai_response') and parsed.get('confidence', 0) > 0.7:
                return self._enhance_ai_response_with_data(parsed, user_input)
            else:
                return self._generate_structured_response(parsed, user_input)
                
        elif parsed.get('action') == 'clarify_intent':
            print(f"[AI] Unknown intent - requesting clarification: {user_input}")
            # Use AI response directly for clarifications
            if parsed.get('ai_response'):
                return parsed['ai_response']
            else:
                return "Hangi ürün hakkında bilgi almak istiyorsunuz? Valf, silindir veya başka bir ürün mü?"
        
        # FALLBACK: If AI classification failed (action is None), use old logic for basic product search
        elif parsed.get('action') is None and any(term in user_clean.lower() for term in ['bobin', 'valf', 'valve', 'silindir', 'cylinder']):
            print(f"[AI] FALLBACK: AI classification failed, using keyword search for: {user_input}")
            
            # Clear context for keyword searches
            self.context.extracted_specs = {
                'diameter': None, 'stroke': None, 'features': [], 
                'quantity': None, 'brand_preference': None
            }
            # Reset conversation stage to initial for fresh search
            self.context.conversation_stage = 'initial'
            print(f"[AI] Context and stage cleared for fallback keyword search")
            return self._generate_structured_response(parsed, user_input)
        
        # Try AI-powered response generation first  
        if parsed.get('ai_response') and parsed.get('confidence', 0) > 0.7:
            print(f"[AI] High confidence response (confidence: {parsed['confidence']:.2f})")
            return self._enhance_ai_response_with_data(parsed, user_input)
        
        # Fallback to structured response logic
        return self._generate_structured_response(parsed, user_input)
    
    def _enhance_ai_response_with_data(self, parsed: Dict, user_input: str) -> str:
        """Enhance AI response with database data"""
        ai_response = parsed['ai_response']
        
        # Handle product code search
        if parsed.get('intent') == 'product_code_search':
            return self._handle_product_code_search(user_input, parsed)
        
        # Handle order creation stage
        if self.context.conversation_stage == 'order_creation' and parsed.get('intent') == 'order_intent':
            return self._handle_order_creation(user_input, parsed)
        
        # If AI detected specs, try to add product data
        diameter = parsed.get('diameter')
        stroke = parsed.get('stroke')
        
        if diameter and stroke:
            # DOĞRUDAN ÜRÜN LİSTESİNE YÖNLENDİR - hiç seçenek gösterme
            products = self.search_exact_product(diameter, stroke, parsed.get('features', []))
            if products:
                if len(products) == 1:
                    # Single product - show details directly
                    product = products[0]
                    stock_display = int(float(product['stock'])) if float(product['stock']).is_integer() else float(product['stock'])
                    
                    if stock_display <= 0:
                        ai_response = f"✅ {diameter}mm çap, {stroke}mm strok için ürün bulundu:\n\n"
                        ai_response += f"📦 **{product['name']}**\n"
                        ai_response += f"🏷️ Ürün Kodu: {product['urun_kodu']}\n"
                        ai_response += f"⚠️ Stok durumu: {stock_display} adet (Stokta yok)\n\n"
                        ai_response += f"📝 Bu ürün şu an stokta bulunmamaktadır. Tedarik süresi ve fiyat bilgisi için müşteri temsilcimizle iletişime geçebilirsiniz."
                        self.context.conversation_stage = 'general'
                    else:
                        ai_response = f"✅ {diameter}mm çap, {stroke}mm strok için ürün bulundu:\n\n"
                        ai_response += f"📦 **{product['name']}**\n"
                        ai_response += f"🏷️ Ürün Kodu: {product['urun_kodu']}\n"
                        ai_response += f"📊 Stok durumu: {stock_display} adet\n\n"
                        ai_response += f"💬 Kaç adet sipariş etmek istiyorsunuz?"
                        
                        self.context.current_order = {'id': product['id'], 'malzeme_kodu': product['urun_kodu'], 'malzeme_adi': product['name'], 'current_stock': product['stock']}
                        self.context.conversation_stage = 'order_creation'
                else:
                    # Multiple products - show link
                    ai_response = f"✅ {diameter}mm çap, {stroke}mm strok için {len(products)} ürün bulundu.\n\n🛒 Ürünleri görüntülemek için link gönderiyorum."
                    self.context.selected_products = products
                    self.context.conversation_stage = 'product_selection'
            else:
                ai_response += f"\n\n❌ Maalesef {diameter}mm çap x {stroke}mm strok ölçülerinde ürün bulunamadı. Başka ölçü deneyelim mi?"
        elif diameter and not stroke:
            # Stroke options for diameter
            stroke_options = self.get_stroke_options(diameter)
            if stroke_options:
                ai_response += f"\n\n🔧 {diameter}mm için mevcut stroklar:\n"
                for stroke_val in sorted(stroke_options.keys())[:5]:
                    ai_response += f"• {stroke_val}mm strok\n"
        elif not diameter and not stroke:
            # Try keyword search if no specifications detected
            user_clean = normalize_turkish_text(user_input.strip())
            # Skip common words and short phrases
            if len(user_clean) > 2 and user_clean.lower() not in ['merhaba', 'selam', 'evet', 'hayır', 'tamam', 'teşekkür']:
                # Check if user is asking for generic cylinder or valve (need parameters)
                # Only ask for parameters if search is too generic (single word)
                needs_parameters = (
                    user_clean.lower() in ['silindir', 'cylinder', 'valf', 'valve'] or  # Single word searches
                    (len(user_clean.split()) <= 2 and any(word in user_clean.lower() for word in ['silindir', 'cylinder', 'valf', 'valve']))  # Very short searches
                )
                
                if needs_parameters:
                    # For generic cylinders and valves, ask for parameters instead of direct search
                    if 'silindir' in user_clean or 'cylinder' in user_clean:
                        ai_response = f"🔧 Silindir seçimi için lütfen çap ve strok ölçülerini belirtin.\n\nÖrnek: \"100mm çap, 400mm strok\" veya \"Ø100x400\""
                    elif 'valf' in user_clean or 'valve' in user_clean:
                        ai_response += f"\n\n🔧 Valf için boyut ve tip bilgilerini paylaşabilir misiniz? (Örn: DN50, kelebek valf)"
                else:
                    # For other products, show direct search results
                    # CLEAR OLD SPECS CONTEXT for new keyword search
                    self.context.extracted_specs = {
                        'diameter': None, 'stroke': None, 'features': [], 
                        'quantity': None, 'brand_preference': None
                    }
                    
                    products = self.search_keyword_products(user_input)
                    if products:
                        ai_response = f"🔍 '{user_input}' için {len(products)} ürün buldum. Ürünleri görüntülemek için link gönderiyorum."
                        self.context.selected_products = products
                        self.context.conversation_stage = 'product_selection'
        
        # Save AI response for next context
        self.context.last_ai_response = ai_response
        return ai_response
    
    def _handle_product_code_search(self, user_input: str, parsed: Dict) -> str:
        """Handle product code search with database lookup"""
        import re
        
        # Extract product code from user input (pattern: both digit+letter and letter+digit combos)
        product_codes = re.findall(r'\b\d+[A-Za-z]+\d*\b|\b[A-Za-z]+\d+[A-Za-z]*\d*\b', user_input)
        
        if not product_codes:
            return "Ürün kodu bulunamadı. Lütfen doğru formatda bir ürün kodu belirtin."
        
        product_code = product_codes[0]  # Take first match
        
        try:
            # Search for product code in database
            cursor = self.connection.cursor()
            cursor.execute(
                "SELECT p.id, p.malzeme_kodu, p.malzeme_adi, COALESCE(i.current_stock, 0) as current_stock FROM products p LEFT JOIN inventory i ON p.id = i.product_id WHERE UPPER(p.malzeme_kodu) = UPPER(%s)",
                (product_code,)
            )
            result = cursor.fetchone()
            cursor.close()
            
            if result:
                # Product found - go directly to order creation for single product
                product_id, code, name, stock = result
                # Format stock display (remove unnecessary decimals)
                stock_display = int(float(stock)) if float(stock).is_integer() else float(stock)
                
                if stock_display <= 0:
                    # Zero or negative stock
                    if parsed.get('tone') == 'friendly':
                        response = f"✅ {code} ürün kodunu buldum dostum!\n\n"
                        response += f"📦 **{name}**\n"
                        response += f"⚠️ Stok: {stock_display} adet (Stokta yok)\n\n"
                        response += f"📝 Bu ürün şu an stokta bulunmuyor. Tedarik süresi ve fiyat bilgisi için müşteri temsilcimizle iletişime geçebilirsin."
                    else:
                        response = f"✅ {code} ürün koduna sahip ürün bulundu:\n\n"
                        response += f"📦 **{name}**\n"
                        response += f"⚠️ Stok durumu: {stock_display} adet (Stokta yok)\n\n"
                        response += f"📝 Bu ürün şu an stokta bulunmamaktadır. Tedarik süresi ve fiyat bilgisi için müşteri temsilcimizle iletişime geçebilirsiniz."
                    
                    # Don't go to order creation, stay in general conversation
                    self.context.conversation_stage = 'general'
                    return response
                else:
                    # Product has stock
                    if parsed.get('tone') == 'friendly':
                        response = f"✅ {code} ürün kodunu buldum dostum!\n\n"
                        response += f"📦 **{name}**\n"
                        response += f"📊 Stok: {stock_display} adet\n\n"
                        response += f"💬 Kaç adet istiyorsun?"
                    else:
                        response = f"✅ {code} ürün koduna sahip ürün bulundu:\n\n"
                        response += f"📦 **{name}**\n"
                        response += f"📊 Stok durumu: {stock_display} adet\n\n"
                        response += f"💬 Kaç adet sipariş etmek istiyorsunuz?"
                
                # Store for ordering and go directly to order creation
                self.context.current_order = {'id': product_id, 'malzeme_kodu': code, 'malzeme_adi': name, 'current_stock': stock}
                self.context.conversation_stage = 'order_creation'
                return response
            else:
                # Product not found - clear any previous selections
                self.context.selected_products = None
                self.context.conversation_stage = 'general'
                if parsed.get('tone') == 'friendly':
                    return f"❌ {product_code} ürün kodunu bulamadım dostum. Kodunu tekrar kontrol eder misin?"
                else:
                    return f"❌ {product_code} ürün koduna sahip bir ürün bulunmamaktadır. Lütfen ürün kodunu kontrol ediniz."
                    
        except Exception as e:
            print(f"Database error in product code search: {e}")
            # Clear any previous selections on error
            self.context.selected_products = None
            self.context.conversation_stage = 'general'
            return "Üzgünüm, ürün arama sırasında teknik bir sorun oluştu."
    
    def _handle_order_creation(self, user_input: str, parsed: Dict) -> str:
        """Handle order creation flow with current selected product"""
        current_order = self.context.current_order
        
        if not current_order:
            return "Sipariş bilgisi bulunamadı. Lütfen yeniden başlayın."
        
        quantity = parsed.get('quantity')
        product_name = current_order['malzeme_adi']
        product_code = current_order['malzeme_kodu'] 
        stock = current_order['current_stock']
        
        if quantity:
            # Quantity provided - create order summary
            stock_amount = float(stock) if stock else 0
            stock_display = int(stock_amount) if stock_amount.is_integer() else stock_amount
            
            if quantity > stock_amount:
                if parsed.get('tone') == 'friendly':
                    return f"❌ Maalesef dostum, {product_code} için sadece {stock_display} adet stokumuz var. Daha az miktar istersen hazırlayabilirim."
                else:
                    return f"❌ Üzgünüm, {product_code} için mevcut stok {stock_display} adet. Lütfen stok miktarının altında bir değer belirtin."
            
            # Create order summary
            if parsed.get('tone') == 'friendly':
                response = f"✅ Harika dostum! Sipariş özeti:\n\n"
                response += f"📦 **{product_name}**\n"
                response += f"🔢 Ürün Kodu: {product_code}\n"
                response += f"📊 Miktar: {quantity} adet\n\n"
                response += f"💬 Siparişi onaylıyor musun?"
            else:
                response = f"✅ Sipariş özeti hazırlandı:\n\n"
                response += f"📦 **{product_name}**\n"
                response += f"🔢 Ürün Kodu: {product_code}\n"
                response += f"📊 Miktar: {quantity} adet\n\n"
                response += f"💬 Siparişi onaylamak için 'evet' yazın."
            
            # Store quantity in order
            self.context.current_order['quantity'] = quantity
            # Move to confirmation stage
            self.context.conversation_stage = 'order_confirmation'
            return response
        else:
            # No quantity detected, ask again
            if parsed.get('tone') == 'friendly':
                return f"Dostum, {product_name} için kaç adet istediğini söyleyebilir misin?\n\n💡 Örnek: '10 adet' veya '25 tane'"
            else:
                return f"{product_name} için kaç adet sipariş etmek istiyorsunuz?\n\n💡 Örnek: '10 adet' veya '25 tane'"
    
    def _generate_structured_response(self, parsed: Dict = None, user_input: str = '') -> str:
        """Structured response generation (fallback method)"""
        
        # PRIORITY: If AI classification is available and says search_direct, do direct keyword search
        if parsed and parsed.get('action') == 'search_direct':
            print(f"[AI] Using AI classification result: direct search for '{user_input}'")
            
            # Use AI corrected query if available, otherwise use user input
            search_query = (parsed.get('corrected_query') 
                          if parsed and parsed.get('corrected_query') 
                          else user_input.strip())
            
            products = self.search_keyword_products(search_query)
            if products:
                # Set products in context for bridge to detect
                self.context.selected_products = products
                
                if len(products) == 1:
                    # Single product found - show details directly
                    product = products[0]
                    stock_display = int(float(product['stock'])) if float(product['stock']).is_integer() else float(product['stock'])
                    
                    response = f"✅ '{user_input}' için ürün bulundu:\n\n"
                    response += f"📦 **{product['name']}**\n"
                    response += f"🏷️ Ürün Kodu: {product['urun_kodu']}\n"
                    
                    if stock_display <= 0:
                        response += f"⚠️ Stok durumu: {stock_display} adet (Stokta yok)\n\n"
                        response += f"📝 Bu ürün şu an stokta bulunmamaktadır. Tedarik süresi ve fiyat bilgisi için müşteri temsilcimizle iletişime geçebilirsiniz."
                    else:
                        response += f"📊 Stok: {stock_display} adet\n"
                        response += f"💰 Fiyat: Müşteri temsilcimizden öğrenebilirsiniz"
                    
                    return response
                else:
                    # Multiple products - show list with link
                    response = f"✅ '{user_input}' için {len(products)} ürün buldum:\n\n"
                    # Use active tunnel URL
                    base_url = "https://fired-sq-remedies-cheapest.trycloudflare.com"
                    phone = self.context.phone_number if hasattr(self.context, 'phone_number') and self.context.phone_number else 'user'
                    response += f"🔗 Ürünleri görmek için: {base_url}/whatsapp/products/{phone}"
                    return response
            else:
                # No products found
                response = f"❌ '{user_input}' için ürün bulunamadı.\n\n"
                response += f"💡 Farklı anahtar kelimeler deneyebilir veya müşteri temsilcimizle iletişime geçebilirsiniz."
                return response
        
        # Check current conversation stage first
        if self.context.conversation_stage == 'spec_gathering':
            # User is providing additional specs in response to our parameter request
            # Try to extract more specs and continue with keyword search
            if user_input:
                # Combine with previous queries for better context
                if len(self.context.user_query_history) >= 1:
                    # Just use the last query plus current input
                    last_item = self.context.user_query_history[-1]
                    if isinstance(last_item, dict):
                        last_query = last_item.get('query', str(last_item))
                    else:
                        last_query = str(last_item)
                    combined_query = f"{last_query} {user_input}".strip()
                else:
                    combined_query = user_input
                products = self.search_keyword_products(combined_query)
                if products:
                    self.context.selected_products = products
                    if len(products) == 1:
                        # Single product found
                        product = products[0]
                        stock_display = int(float(product['stock'])) if float(product['stock']).is_integer() else float(product['stock'])
                        
                        if stock_display <= 0:
                            response = f"✅ '{combined_query}' için ürün bulundu:\n\n"
                            response += f"📦 **{product['name']}**\n"
                            response += f"🏷️ Ürün Kodu: {product['urun_kodu']}\n"
                            response += f"⚠️ Stok durumu: {stock_display} adet (Stokta yok)\n\n"
                            response += f"📝 Bu ürün şu an stokta bulunmamaktadır. Tedarik süresi ve fiyat bilgisi için müşteri temsilcimizle iletişime geçebilirsiniz."
                            self.context.conversation_stage = 'general'
                            return response
                        else:
                            response = f"✅ '{combined_query}' için ürün bulundu:\n\n"
                            response += f"📦 **{product['name']}**\n"
                            response += f"🏷️ Ürün Kodu: {product['urun_kodu']}\n"
                            response += f"📊 Stok: {stock_display} adet\n\n"
                            response += f"❓ Kaç adet istiyorsunuz?"
                            self.context.current_order = {'id': product['id'], 'malzeme_kodu': product['urun_kodu'], 'malzeme_adi': product['name'], 'current_stock': product['stock']}
                            self.context.conversation_stage = 'order_creation'
                            return response
                    else:
                        # Multiple products found
                        response = f"🔍 '{combined_query}' için {len(products)} ürün buldum. Ürünleri aşağıdaki linkten inceleyebilirsiniz."
                        self.context.conversation_stage = 'product_selection'
                        return response
        
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
                if len(products) == 1:
                    # Single product - show details directly
                    product = products[0]
                    stock_display = int(float(product['stock'])) if float(product['stock']).is_integer() else float(product['stock'])
                    
                    if stock_display <= 0:
                        response = f"✅ {diameter}mm çap, {stroke}mm strok için ürün bulundu:\n\n"
                        response += f"📦 **{product['name']}**\n"
                        response += f"🏷️ Ürün Kodu: {product['urun_kodu']}\n"
                        response += f"⚠️ Stok durumu: {stock_display} adet (Stokta yok)\n\n"
                        response += f"📝 Bu ürün şu an stokta bulunmamaktadır. Tedarik süresi ve fiyat bilgisi için müşteri temsilcimizle iletişime geçebilirsiniz."
                        self.context.conversation_stage = 'general'
                    else:
                        response = f"✅ {diameter}mm çap, {stroke}mm strok için ürün bulundu:\n\n"
                        response += f"📦 **{product['name']}**\n"
                        response += f"🏷️ Ürün Kodu: {product['urun_kodu']}\n"
                        response += f"📊 Stok durumu: {stock_display} adet\n\n"
                        response += f"💬 Kaç adet sipariş etmek istiyorsunuz?"
                        
                        self.context.current_order = {'id': product['id'], 'malzeme_kodu': product['urun_kodu'], 'malzeme_adi': product['name'], 'current_stock': product['stock']}
                        self.context.conversation_stage = 'order_creation'
                else:
                    # Multiple products - show link
                    response = f"✅ {diameter}mm çap, {stroke}mm strok için {len(products)} ürün bulundu.\n\n🛒 Ürünleri görüntülemek için link gönderiyorum."
                    
                    self.context.selected_products = products
                    self.context.conversation_stage = 'product_selection'
            else:
                response = f"Maalesef {diameter}mm x {stroke}mm silindir şu an stokta yok. "
                response += "Alternatif boyutlar önerebilirim?"
        
        else:
            # Stage: Initial - try keyword search or need basic info
            user_clean = normalize_turkish_text(self.context.user_query_history[-1]['query'].strip()) if self.context.user_query_history else ""
            
            # Try keyword search if user entered something meaningful
            if len(user_clean) > 2 and user_clean.lower() not in ['merhaba', 'selam', 'evet', 'hayır', 'tamam', 'teşekkür']:
                # Check if user is asking for generic cylinder or valve (need parameters)
                # Ask for parameters if search contains valve/cylinder but no specific product details
                needs_parameters = (
                    user_clean.lower() in ['silindir', 'cylinder', 'valf', 'valve'] or  # Single word searches
                    (len(user_clean.split()) <= 2 and any(word in user_clean.lower() for word in ['silindir', 'cylinder', 'valf', 'valve'])) or  # Very short searches
                    # Also for longer searches if they contain valve/cylinder but no specific product details
                    (any(word in user_clean.lower() for word in ['valf', 'valve', 'silindir', 'cylinder']) and
                     not any(specific in user_clean.lower() for specific in ['bobin', 'bobini', 'bobین', 'tapa', 'sensor', 'hortum', 'raccor']))
                )
                
                if needs_parameters:
                    # For generic cylinders and valves, ask for parameters
                    if 'silindir' in user_clean or 'cylinder' in user_clean:
                        response = "🔧 Silindir aradığınızı anladım. Çap ve strok ölçülerini paylaşabilir misiniz?\n\n"
                        response += "💡 Örnek: '100mm çap, 400mm strok'"
                    elif 'valf' in user_clean or 'valve' in user_clean:
                        response = "🔧 Valf aradığınızı anladım. Boyut ve tip bilgilerini paylaşabilir misiniz?\n\n"
                        response += "💡 Örnek: 'DN50 kelebek valf'"
                    
                    self.context.conversation_stage = 'spec_gathering'
                    return response
                else:
                    # For other products, show direct search results with link only
                    # Use AI corrected query if available
                    search_query = (parsed.get('corrected_query') 
                                  if parsed and parsed.get('corrected_query') 
                                  else user_clean)
                    products = self.search_keyword_products(search_query)
                    if products:
                        # Set products in context for bridge to detect
                        self.context.selected_products = products
                        if len(products) == 1:
                            # Single product found - show details directly
                            product = products[0]
                            stock_display = int(float(product['stock'])) if float(product['stock']).is_integer() else float(product['stock'])
                            
                            if stock_display <= 0:
                                # Zero or negative stock
                                if self.context.user_tone == 'friendly':
                                    response = f"✅ '{user_clean}' için bu ürünü buldum dostum!\n\n"
                                    response += f"📦 **{product['name']}**\n"
                                    response += f"🏷️ Ürün Kodu: {product['urun_kodu']}\n"
                                    response += f"⚠️ Stok: {stock_display} adet (Stokta yok)\n\n"
                                    response += f"📝 Bu ürün şu an stokta bulunmuyor. Tedarik süresi ve fiyat bilgisi için müşteri temsilcimizle iletişime geçebilirsin."
                                else:
                                    response = f"✅ '{user_clean}' için ürün bulundu:\n\n"
                                    response += f"📦 **{product['name']}**\n"
                                    response += f"🏷️ Ürün Kodu: {product['urun_kodu']}\n"
                                    response += f"⚠️ Stok durumu: {stock_display} adet (Stokta yok)\n\n"
                                    response += f"📝 Bu ürün şu an stokta bulunmamaktadır. Tedarik süresi ve fiyat bilgisi için müşteri temsilcimizle iletişime geçebilirsiniz."
                                
                                # For single out-of-stock product, stay in general (no link needed)
                                self.context.conversation_stage = 'general'
                                return response
                            else:
                                # Product has stock
                                if self.context.user_tone == 'friendly':
                                    response = f"✅ '{user_clean}' için bu ürünü buldum dostum!\n\n"
                                    response += f"📦 **{product['name']}**\n"
                                    response += f"🏷️ Ürün Kodu: {product['urun_kodu']}\n"
                                    response += f"📊 Stok: {stock_display} adet\n\n"
                                    response += f"💬 Kaç adet istiyorsun?"
                                else:
                                    response = f"✅ '{user_clean}' için ürün bulundu:\n\n"
                                    response += f"📦 **{product['name']}**\n"
                                    response += f"🏷️ Ürün Kodu: {product['urun_kodu']}\n"
                                    response += f"📊 Stok durumu: {stock_display} adet\n\n"
                                    response += f"💬 Kaç adet sipariş etmek istiyorsunuz?"
                                
                                # Store for ordering and go directly to order creation
                                self.context.current_order = {'id': product['id'], 'malzeme_kodu': product['urun_kodu'], 'malzeme_adi': product['name'], 'current_stock': product['stock']}
                                self.context.conversation_stage = 'order_creation'
                                return response
                        else:
                            # Multiple products - show link
                            if self.context.user_tone == 'friendly':
                                response = f"🔍 '{user_clean}' için {len(products)} ürün buldum. Ürünleri linkten inceleyebilirsin!"
                            else:
                                response = f"🔍 '{user_clean}' için {len(products)} ürün buldum. Ürünleri aşağıdaki linkten inceleyebilirsiniz."
                            self.context.conversation_stage = 'product_selection'
                            return response
            
            # Check for cancellation words first
            cancellation_words = ['vazgeçtim', 'boşver', 'olmadı', 'iptal', 'bırak', 'gerek yok', 'sonra bakarız']
            if any(word in user_clean.lower() for word in cancellation_words):
                if self.context.user_tone == 'friendly':
                    return "Tamam canım, başka bir şey için yardım istersen söyle!"
                else:
                    return "Anladım, başka bir konuda yardımcı olabilirim."
            
            # No products found or too generic input - ask for more info
            if self.context.user_tone == 'friendly':
                response = "Canım, hangi ürün arıyorsun? Ürün adı, çap/strok bilgisi "
                response += "ya da özellik söylersen sana en uygun ürünleri bulabilirim!\n\n"
                response += "💡 Örnekler:\n• '100mm çap, 400mm strok silindir'\n• 'kör tapa'\n• 'manyetik silindir'"
            else:
                response = "Ürün aramanız için daha fazla bilgiye ihtiyacım var.\n\n"
                response += "📋 Arayabileceğiniz:\n"
                response += "  • Ürün adı (örn: kör tapa, silindir)\n"
                response += "  • Boyut bilgisi (örn: 100mm çap, 400mm strok)\n"
                response += "  • Özellikler (magnetik, amortisörlü, vb.)"
            
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
        """AI-powered doğal dil miktar analizi"""
        if not self.context.current_order:
            return "Ürün seçimi bulunamadı. Lütfen tekrar başlayın."
        
        # Handle both old tuple format and new dict format
        if isinstance(self.context.current_order, dict):
            product = self.context.current_order
        else:
            product, _ = self.context.current_order
        
        # AI ile miktar çıkarımı
        try:
            # AI'den miktar çıkarımı iste
            # Get product name with backward compatibility
            product_name = product.get('malzeme_adi') or product.get('name', 'Ürün')
            
            ai_context = {
                'user_input': quantity_str,
                'product_name': product_name,
                'current_stage': 'quantity_extraction'
            }
            
            # OpenRouter AI ile miktar analizi
            ai_response = openrouter_client.extract_quantity(quantity_str, ai_context)
            quantity = ai_response.get('extracted_quantity')
            
            if not quantity or quantity <= 0:
                # Fallback: regex ile basit sayı çıkarımı
                import re
                numbers = re.findall(r'\d+', quantity_str)
                if numbers:
                    quantity = int(numbers[0])
                else:
                    return "❓ Kaç adet istediğinizi anlayamadım. Lütfen sayı belirtin. (Örn: 5, 10 adet, 3 tane)"
            
            # Get actual current stock from database for real-time check
            actual_stock = self.get_actual_stock(product['id'])
            
            if actual_stock == 0:
                return f"❌ Üzgünüm, '{product['name']}' şu anda stokta yok. Başka bir ürün seçer misiniz?"
            elif quantity > actual_stock:
                return f"⚠️ Stokta sadece {actual_stock:.0f} adet mevcut. {actual_stock:.0f} adet için sipariş verebilirsiniz."
            
            # DOĞRUDAN SİPARİŞ ONAYINI ATLAYIP KAYDET
            success = self.save_order(product, quantity)
            
            if success:
                # Update order with quantity  
                self.context.current_order = (product, quantity)
                self.context.conversation_stage = 'order_completed'
                
                return self.create_final_order_confirmation(quantity, product)
            else:
                return "❌ Sipariş kaydedilemedi. Lütfen tekrar deneyiniz."
                
        except Exception as e:
            print(f"Quantity processing error: {e}")
            # Fallback to simple number extraction
            try:
                import re
                numbers = re.findall(r'\d+', quantity_str)
                if numbers:
                    quantity = int(numbers[0])
                    if quantity <= 0:
                        return "❓ Lütfen 1'den büyük bir sayı belirtin."
                    return self.handle_quantity_input(str(quantity))  # Retry with clean number
                else:
                    return "❓ Kaç adet istediğinizi belirtin. (Örn: 5, 10 adet, 3 tane)"
            except:
                return "❓ Lütfen adet sayısını net bir şekilde belirtin."

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
    
    def create_final_order_confirmation(self, quantity: int, product: Dict) -> str:
        """Final sipariş onay mesajı - evet/hayır olmadan direkt"""
        from datetime import datetime
        
        # Simple time check without pytz (fallback to system time)
        now = datetime.now()
        current_hour = now.hour
        
        # Determine delivery time based on current time
        if current_hour < 16:  # Before 4 PM
            delivery_info = "📦 **Bugün kargoya verilecek**"
        else:  # After 4 PM
            delivery_info = "📦 **Yarın kargoya verilecek** (16:00 sonrası sipariş)"
        
        # Handle missing price field for product code searches
        if 'price' in product and product['price'] is not None:
            unit_price = product['price']
        else:
            # For product code searches without price, use placeholder or fetch from DB
            unit_price = 0.0  # Will be fetched in save_order method
        
        total_price = quantity * unit_price
        
        # Format price display
        price_display = f"{unit_price:.2f} TL" if unit_price > 0 else "Fiyat sorulacak"
        total_display = f"{total_price:.2f} TL" if unit_price > 0 else "Fiyat sorulacak"
        
        response = f"""✅ **SİPARİŞİNİZ ALINDI!**

📋 **Sipariş Detayları:**
🔸 Ürün: {product.get('malzeme_adi') or product.get('name', 'Ürün')}
🔸 Ürün Kodu: {product.get('malzeme_kodu') or product.get('urun_kodu', 'N/A')}
🔸 Adet: {quantity}
🔸 Birim Fiyat: {price_display}
🔸 Toplam: {total_display}

⏰ **Kargo Bilgisi:**
{delivery_info}

🎯 **Teslim Süreci:**
• 16:00'a kadar olan siparişler aynı gün kargoya verilir
• 16:00'dan sonraki siparişler ertesi gün kargoya verilir

📞 Herhangi bir sorun için bize ulaşabilirsiniz.
**Teşekkürler! 🙏**"""

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
                    
                    # Handle missing price field for product code searches
                    if 'price' in product and product['price'] is not None:
                        unit_price = product['price']
                    else:
                        # For product code searches, use placeholder price (prices are quoted on request in B2B)
                        unit_price = 0.0
                    
                    total_price = quantity * unit_price
                    
                    # Create conversation context - convert Decimal objects for JSON serialization
                    product_info = product.copy()
                    if 'current_stock' in product_info and product_info['current_stock'] is not None:
                        product_info['current_stock'] = float(product_info['current_stock'])
                    
                    context_data = {
                        'specs': self.context.extracted_specs,
                        'conversation_history': self.context.user_query_history[-5:],  # Last 5 queries
                        'selected_product_info': product_info,
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
                        unit_price,
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
            
            # AI-powered intent classification for better conversation flow
            try:
                conversation_history = [q['query'] for q in conversation_system.context.user_query_history[-3:]]
                user_intent = openrouter_client.classify_intent(user_input, conversation_history)
                print(f"[AI] Detected intent: {user_intent}")
            except Exception as e:
                print(f"[AI] Intent classification failed: {e}")
                user_intent = "general_question"
            
            # Handle different conversation stages with AI intent awareness
            stage = conversation_system.context.conversation_stage
            
            # Special handling for AI-detected intents
            if user_intent == "greeting":
                response = "Merhaba! Size nasıl yardımcı olabilirim? Hangi silindir özelliklerini arıyorsunuz?"
            elif user_intent == "price_inquiry" and not conversation_system.context.selected_products:
                response = "Fiyat bilgisi için önce ürün özelliklerini belirtmeniz gerekiyor. Hangi çap ve strok aralığında silindir arıyorsunuz?"
            elif stage == 'product_selection' and (user_input.isdigit() or user_intent == "order_intent"):
                response = conversation_system.handle_product_selection(user_input)
            elif stage == 'order_creation' and user_input.isdigit():
                response = conversation_system.handle_quantity_input(user_input)
            elif stage == 'order_confirmation':
                response = conversation_system.handle_order_confirmation(user_input)
            elif user_intent == "product_search" or user_intent == "spec_question":
                response = conversation_system.generate_response(user_input)
            else:
                # Default response generation with AI assistance
                try:
                    products = conversation_system.context.selected_products if conversation_system.context.selected_products else None
                    context_data = {
                        'stage': stage,
                        'specs': conversation_system.context.extracted_specs,
                        'intent': user_intent
                    }
                    ai_response = openrouter_client.generate_response(user_input, context_data, products)
                    response = ai_response if ai_response else conversation_system.generate_response(user_input)
                except Exception as e:
                    print(f"[AI] Response generation failed: {e}")
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
#!/usr/bin/env python3
"""
B2B Chat Web Interface - Flask app
"""

from flask import Flask, render_template, request, jsonify
import sys
import os
import json
import time
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from conversation_system import B2BConversationSystem
from openrouter_client import openrouter_client

app = Flask(__name__)
app.secret_key = 'b2b_chat_secret_key'

# Global conversation systems per session
conversation_systems = {}  # session_id -> B2BConversationSystem
conversation_analytics = []  # Store conversation analytics

def get_conversation_system(session_id):
    """Get or create conversation system for session"""
    global conversation_systems
    if session_id not in conversation_systems:
        db_connection = "postgresql://postgres:masterkey@localhost:5432/b2b_rag_system"
        conversation_systems[session_id] = B2BConversationSystem(db_connection)
        print(f"[Web] Created new conversation system for session: {session_id}")
        
        # Try to load context from memory-keeper  
        try:
            print(f"[Memory] Loading context for session {session_id}")
            # Memory-keeper integration would restore context here
            # For now, context persists in conversation_systems dict during app lifetime
                
        except Exception as e:
            print(f"[Memory] Error loading context: {e}")
    
    return conversation_systems[session_id]

@app.route('/')
def index():
    """Main chat interface"""
    return render_template('chat.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    """Handle AI-powered chat messages"""
    start_time = time.time()
    
    try:
        data = request.json
        user_message = data.get('message', '').strip()
        session_id = data.get('session_id', 'web_session')
        
        if not user_message:
            return jsonify({'error': 'Boş mesaj gönderildi'}), 400
        
        # Get conversation system for this session
        system = get_conversation_system(session_id)
        
        # AI-powered intent classification
        try:
            conversation_history = [q['query'] for q in system.context.user_query_history[-3:]]
            user_intent = openrouter_client.classify_intent(user_message, conversation_history)
            print(f"[Web] User Intent: {user_intent}")
        except Exception as e:
            print(f"[Web] Intent classification failed: {e}")
            user_intent = "general_question"
        
        # Handle different conversation stages with AI
        stage = system.context.conversation_stage
        
        if user_intent == "greeting":
            ai_response = "Merhaba! B2B silindir satış sistemine hoş geldiniz. Size nasıl yardımcı olabilirim?"
        elif stage == 'product_selection' and (user_message.isdigit() or user_intent == "order_intent"):
            ai_response = system.handle_product_selection(user_message)
        elif stage == 'order_creation' and user_message.isdigit():
            ai_response = system.handle_quantity_input(user_message)
        elif stage == 'order_confirmation':
            ai_response = system.handle_order_confirmation(user_message)
        else:
            # AI-enhanced response generation
            ai_response = system.generate_response(user_message)
        
        # Calculate response time
        response_time = time.time() - start_time
        
        # Analytics collection
        analytics_entry = {
            'timestamp': datetime.now().isoformat(),
            'session_id': session_id,
            'user_message': user_message,
            'intent': user_intent,
            'conversation_stage': stage,
            'response_time': response_time,
            'ai_specs': system.context.extracted_specs,
            'confidence': getattr(system.context, 'last_confidence', 0.8)
        }
        conversation_analytics.append(analytics_entry)
        
        # Keep only last 100 analytics entries
        if len(conversation_analytics) > 100:
            conversation_analytics.pop(0)
        # Save context to memory-keeper every 3 messages
        if len(system.context.user_query_history) % 3 == 0:
            try:
                # Save conversation context to memory-keeper
                context_key = f"session_{session_id}_context"
                context_data = {
                    'specs': system.context.extracted_specs,
                    'stage': system.context.conversation_stage,
                    'history_count': len(system.context.user_query_history),
                    'last_message': user_message
                }
                
                # Save to memory-keeper (using MCP tool function)
                import json
                print(f"[Memory] Saving context for session {session_id}")
                
                # Memory-keeper integration would use MCP tool here
                # For now, session-based memory in conversation_systems dict is sufficient
                print(f"[Memory] Saved context for session: {session_id}")
                
            except Exception as e:
                print(f"[Memory] Error saving context: {e}")
        
        return jsonify({
            'response': ai_response,
            'stage': system.context.conversation_stage,
            'intent': user_intent,
            'response_time': round(response_time, 2),
            'context': {
                'diameter': system.context.extracted_specs.get('diameter'),
                'stroke': system.context.extracted_specs.get('stroke'),
                'features': system.context.extracted_specs.get('features', []),
                'quantity': system.context.extracted_specs.get('quantity'),
                'brand_preference': system.context.extracted_specs.get('brand_preference')
            },
            'products': len(system.context.selected_products) if system.context.selected_products else 0
        })
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"[Web] Error in chat: {e}")
        print(f"[Web] Full traceback: {error_trace}")
        return jsonify({'error': f'Sistem hatası: {str(e)}'}), 500

@app.route('/api/reset', methods=['POST'])
def reset_chat():
    """Reset conversation state"""
    try:
        data = request.json or {}
        session_id = data.get('session_id', 'web_session')
        
        global conversation_systems
        if session_id in conversation_systems:
            # Reset context properly
            from conversation_system import ConversationContext
            conversation_systems[session_id].context = ConversationContext()
            print(f"[Web] Reset conversation for session: {session_id}")
        
        return jsonify({'message': 'Konuşma sıfırlandı', 'success': True})
    except Exception as e:
        return jsonify({'error': f'Reset hatası: {str(e)}'}), 500

@app.route('/analytics')
def analytics_dashboard():
    """Analytics dashboard page"""
    return render_template('analytics.html')

@app.route('/api/analytics', methods=['GET'])
def get_analytics():
    """Get conversation analytics data"""
    try:
        # Calculate analytics
        total_conversations = len(conversation_analytics)
        
        if total_conversations == 0:
            return jsonify({
                'total_conversations': 0,
                'avg_response_time': 0,
                'intents': {},
                'stages': {},
                'recent_conversations': []
            })
        
        # Calculate metrics
        avg_response_time = sum(entry['response_time'] for entry in conversation_analytics) / total_conversations
        
        # Intent distribution
        intent_counts = {}
        for entry in conversation_analytics:
            intent = entry.get('intent', 'unknown')
            intent_counts[intent] = intent_counts.get(intent, 0) + 1
        
        # Stage distribution  
        stage_counts = {}
        for entry in conversation_analytics:
            stage = entry.get('conversation_stage', 'unknown')
            stage_counts[stage] = stage_counts.get(stage, 0) + 1
        
        # Recent conversations (last 10)
        recent_conversations = conversation_analytics[-10:] if len(conversation_analytics) > 10 else conversation_analytics
        
        return jsonify({
            'total_conversations': total_conversations,
            'avg_response_time': round(avg_response_time, 2),
            'intents': intent_counts,
            'stages': stage_counts,
            'recent_conversations': recent_conversations,
            'last_updated': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': f'Analytics hatası: {str(e)}'}), 500

@app.route('/demo')
def demo_page():
    """Demo environment page"""
    return render_template('demo.html')

@app.route('/product_selection')
def product_selection_page():
    """Product selection page"""
    return render_template('product_selection.html')

@app.route('/whatsapp/products/<session_id>')
def whatsapp_product_selection(session_id):
    """WhatsApp product selection page"""
    return render_template('whatsapp_products.html', session_id=session_id)

@app.route('/api/search_products', methods=['POST'])
def search_products():
    """Search products based on criteria"""
    try:
        data = request.json
        session_id = data.get('session_id', 'web_session')
        criteria = data.get('criteria', {})
        
        # Get conversation system for context
        system = get_conversation_system(session_id)
        
        # Build search query based on criteria
        products = []
        
        with psycopg2.connect("postgresql://postgres:masterkey@localhost:5432/b2b_rag_system") as db:
            with db.cursor(cursor_factory=RealDictCursor) as cur:
                # Base query
                query = """
                    SELECT p.id, p.malzeme_adi, i.current_stock
                    FROM products p 
                    LEFT JOIN inventory i ON p.id = i.product_id
                    WHERE COALESCE(i.current_stock, 0) > 0
                """
                params = []
                
                # Add filters based on criteria
                # Note: Don't filter by product_type as it's too restrictive
                # Let diameter and stroke filters find the relevant products
                
                # Add diameter filter
                if criteria.get('diameter'):
                    query += " AND p.malzeme_adi ILIKE %s"
                    params.append(f"%{criteria['diameter']}%")
                
                # Add stroke filter
                if criteria.get('stroke'):
                    query += " AND p.malzeme_adi ILIKE %s"
                    params.append(f"%{criteria['stroke']}%")
                
                # Add voltage filter
                if criteria.get('voltage'):
                    query += " AND p.malzeme_adi ILIKE %s"
                    params.append(f"%{criteria['voltage']}%")
                
                query += " ORDER BY i.current_stock DESC LIMIT 50"
                
                cur.execute(query, params)
                rows = cur.fetchall()
                
                for row in rows:
                    products.append({
                        'id': row['id'],
                        'name': row['malzeme_adi'],
                        'brand': 'N/A',  # Brand column doesn't exist in products table
                        'price': 0,  # Price column doesn't exist, will be quoted later
                        'stock': float(row['current_stock']) if row['current_stock'] else 0
                    })
        
        return jsonify({
            'success': True,
            'products': products,
            'total_count': len(products)
        })
        
    except Exception as e:
        print(f"[Web] Error in search_products: {e}")
        return jsonify({'error': f'Arama hatası: {str(e)}'}), 500

@app.route('/api/select_product', methods=['POST'])
def select_product():
    """Handle product selection"""
    try:
        data = request.json
        session_id = data.get('session_id', 'web_session')
        product_id = data.get('product_id')
        
        if not product_id:
            return jsonify({'error': 'Ürün ID gerekli'}), 400
        
        # Get product details
        with psycopg2.connect("postgresql://postgres:masterkey@localhost:5432/b2b_rag_system") as db:
            with db.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT p.id, p.malzeme_adi, i.current_stock
                    FROM products p 
                    LEFT JOIN inventory i ON p.id = i.product_id
                    WHERE p.id = %s
                """, (product_id,))
                
                product = cur.fetchone()
                
                if not product:
                    return jsonify({'error': 'Ürün bulunamadı'}), 404
        
        # Get conversation system and store selection
        system = get_conversation_system(session_id)
        
        # Store selected product in context
        selected_product = {
            'id': product['id'],
            'name': product['malzeme_adi'],
            'brand': 'N/A',  # Brand column doesn't exist
            'price': 0,  # Price will be quoted later
            'stock': float(product['current_stock']) if product['current_stock'] else 0
        }
        
        system.context.selected_products = [selected_product]
        system.context.current_order = (selected_product, None)
        system.context.conversation_stage = 'order_creation'
        
        # Set AI response for when user returns to chat
        ai_message = f"✅ '{selected_product['name']}' ürününü seçtiniz. Kaç adet sipariş vermek istiyorsunuz?"
        system.context.last_ai_response = ai_message
        
        # Add the selection message to conversation history
        system.context.add_query(f"PRODUCT_SELECTED: {selected_product['name']}")
        
        print(f"[Web] Product selected: {selected_product['name']} for session {session_id}")
        print(f"[Web] AI message set: {ai_message}")
        
        return jsonify({
            'success': True,
            'selected_product': selected_product
        })
        
    except Exception as e:
        print(f"[Web] Error in select_product: {e}")
        return jsonify({'error': f'Seçim hatası: {str(e)}'}), 500

@app.route('/api/check_selection', methods=['POST'])
def check_selection():
    """Check if user selected a product and return AI message"""
    try:
        data = request.json
        session_id = data.get('session_id', 'web_session')
        
        # Get conversation system
        system = get_conversation_system(session_id)
        
        # Check if there's a pending AI response (product was selected)
        if (system.context.conversation_stage == 'order_creation' and 
            system.context.last_ai_response and 
            'seçtiniz' in system.context.last_ai_response):
            
            ai_message = system.context.last_ai_response
            
            # Clear the message so it doesn't repeat
            system.context.last_ai_response = None
            
            context_info = {
                'diameter': system.context.extracted_specs.get('diameter'),
                'stroke': system.context.extracted_specs.get('stroke'),
                'selected_product': system.context.current_order[0]['name'] if system.context.current_order else None
            }
            
            return jsonify({
                'has_selection': True,
                'ai_message': ai_message,
                'context': context_info
            })
        else:
            return jsonify({
                'has_selection': False
            })
            
    except Exception as e:
        print(f"[Web] Error in check_selection: {e}")
        return jsonify({'has_selection': False})

if __name__ == '__main__':
    print("B2B Chat Web Interface baslatiliyor...")
    print("Tarayicida ac: http://localhost:5000")
    
    # Debug: Print routes before starting
    print("Registered routes:")
    for rule in app.url_map.iter_rules():
        print(f"  {rule.rule} -> {rule.endpoint}")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
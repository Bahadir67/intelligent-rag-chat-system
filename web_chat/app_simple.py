#!/usr/bin/env python3
"""
B2B Chat Web Interface - Simplified without psycopg2 dependency
Uses mock data for demo
"""

from flask import Flask, render_template, request, jsonify
import json
import time
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'b2b_chat_secret_key'

# Mock conversation context
conversation_context = {
    'stage': 'discovery',
    'user_preferences': {
        'diameter': None,
        'stroke': None,
        'features': [],
        'quantity': None
    },
    'conversation_history': [],
    'found_products': []
}

# Mock product database
MOCK_PRODUCTS = [
    {
        'id': 1,
        'name': 'IS 100* 400 ISO MANYETİK YAST.SİL.MAG',
        'brand': 'FESTO',
        'diameter': 100,
        'stroke': 400,
        'features': ['magnetic'],
        'price': 280.0,
        'stock': 3
    },
    {
        'id': 2,
        'name': 'ANS 100* 400 PN.SİLİNDİR MAG',
        'brand': 'SMC',
        'diameter': 100,
        'stroke': 400,
        'features': ['magnetic'],
        'price': 250.0,
        'stock': 2
    },
    {
        'id': 3,
        'name': 'FESTO DNC-100*350-PPV-A',
        'brand': 'FESTO',
        'diameter': 100,
        'stroke': 350,
        'features': [],
        'price': 220.0,
        'stock': 5
    },
    {
        'id': 4,
        'name': 'SMC CDQ2B100-200DMZ-M9BW',
        'brand': 'SMC',
        'diameter': 100,
        'stroke': 200,
        'features': ['magnetic'],
        'price': 180.0,
        'stock': 8
    }
]

def parse_user_input(text):
    """Parse user input for dimensions and features"""
    import re
    
    text_upper = text.upper()
    parsed = {
        'diameter': None,
        'stroke': None,
        'features': [],
        'quantity': None,
        'greeting': False,
        'casual': False
    }
    
    # Greeting detection
    greetings = ['MERHABA', 'SELAM', 'HI', 'HELLO', 'NABER', 'NASIL']
    if any(word in text_upper for word in greetings):
        parsed['greeting'] = True
    
    # Casual conversation
    casual_words = ['NABER', 'NASIL', 'İYİ', 'TEŞEKKÜR', 'SAĞ OL']
    if any(word in text_upper for word in casual_words):
        parsed['casual'] = True
    
    # Diameter detection
    diameter_patterns = [
        r'(\d+)\s*(?:CAP|CAPLI|ÇAP|ÇAPLI)',
        r'(\d+)\s*(?:LUK|LIK|LÜK)',
        r'Ø(\d+)',
        r'(\d+)\s*MM\s*(?:CAP|CAPLI|ÇAP|ÇAPLI)'
    ]
    
    for pattern in diameter_patterns:
        matches = re.findall(pattern, text_upper)
        if matches:
            parsed['diameter'] = int(matches[0])
            break
    
    # Stroke detection
    stroke_patterns = [
        r'(\d+)\s*(?:STROK|STROKLU)',
        r'(\d+)\s*MM\s*(?:STROK|STROKLU)'
    ]
    for pattern in stroke_patterns:
        matches = re.findall(pattern, text_upper)
        if matches:
            parsed['stroke'] = int(matches[0])
            break
    
    # Feature detection
    if any(word in text_upper for word in ['MAGNETİK', 'MAGNETLI', 'MAGNET']):
        parsed['features'].append('magnetic')
    
    # Quantity detection
    quantity_patterns = [r'(\d+)\s*(?:ADET|TANE|PARÇA)']
    for pattern in quantity_patterns:
        matches = re.findall(pattern, text_upper)
        if matches:
            parsed['quantity'] = int(matches[0])
            break
    
    return parsed

def search_products(diameter=None, stroke=None, features=None):
    """Search products based on criteria"""
    results = []
    
    for product in MOCK_PRODUCTS:
        match = True
        
        if diameter and product['diameter'] != diameter:
            match = False
        
        if stroke and product['stroke'] != stroke:
            match = False
        
        if features:
            for feature in features:
                if feature not in product.get('features', []):
                    match = False
        
        if match and product['stock'] > 0:
            results.append(product)
    
    return sorted(results, key=lambda x: x['stock'], reverse=True)

def get_stroke_options(diameter):
    """Get available stroke options for diameter"""
    strokes = {}
    for product in MOCK_PRODUCTS:
        if product['diameter'] == diameter and product['stock'] > 0:
            stroke = product['stroke']
            if stroke not in strokes:
                strokes[stroke] = {'total_stock': 0, 'products': []}
            strokes[stroke]['total_stock'] += product['stock']
            strokes[stroke]['products'].append(product)
    
    return strokes

def generate_response(user_input):
    """Generate AI response based on input"""
    global conversation_context
    
    parsed = parse_user_input(user_input)
    
    # Update context
    if parsed['diameter']:
        conversation_context['user_preferences']['diameter'] = parsed['diameter']
    if parsed['stroke']:
        conversation_context['user_preferences']['stroke'] = parsed['stroke']
    if parsed['features']:
        conversation_context['user_preferences']['features'].extend(parsed['features'])
    if parsed['quantity']:
        conversation_context['user_preferences']['quantity'] = parsed['quantity']
    
    # Get current preferences
    diameter = conversation_context['user_preferences']['diameter']
    stroke = conversation_context['user_preferences']['stroke']
    features = conversation_context['user_preferences']['features']
    quantity = conversation_context['user_preferences']['quantity']
    
    # Handle greeting/casual conversation
    if parsed['greeting'] or parsed['casual']:
        if parsed['greeting']:
            return "Merhaba! Ben B2B silindir uzmanınızım. Size nasıl yardımcı olabilirim? 😊"
        elif 'NABER' in user_input.upper():
            return "İyiyim, teşekkürler! Silindir konusunda size nasıl yardımcı olabilirim?"
    
    # Handle cylinder search intent
    if any(word in user_input.upper() for word in ['SİLİNDİR', 'SILINDIR']):
        if not diameter:
            return "Harika! Silindir arıyorsunuz. Hangi çap lazım?"
    
    # Generate response based on current state
    if diameter and stroke:
        # Complete specs - show products
        products = search_products(diameter, stroke, features)
        
        if products:
            best_product = products[0]
            conversation_context['found_products'] = products
            conversation_context['stage'] = 'ordering'
            
            response = f"{diameter}mm x {stroke}mm silindir var! "
            response += f"{best_product['name']}, {best_product['stock']} adet stokta. "
            response += f"Fiyat {best_product['price']:.0f} TL. Kaç adet lazım?"
            
            return response
        else:
            return f"Maalesef {diameter}mm x {stroke}mm silindir şu an stokta yok. Alternatif önerebilirim?"
    
    elif diameter and not stroke:
        # Need stroke
        stroke_options = get_stroke_options(diameter)
        
        if stroke_options:
            total_stock = sum(opt['total_stock'] for opt in stroke_options.values())
            conversation_context['stage'] = 'specification'
            
            return f"{diameter}mm çaplı silindirden {total_stock} adet var. Strok bilgisini verirsen bakayım."
        else:
            return f"Maalesef {diameter}mm çaplı silindir stokta yok. Başka bir çap deneyelim mi?"
    
    elif quantity and conversation_context['stage'] == 'ordering':
        # Handle quantity for ordering
        if conversation_context['found_products']:
            best_product = conversation_context['found_products'][0]
            total_price = quantity * best_product['price']
            
            if quantity > best_product['stock']:
                return f"Stokta sadece {best_product['stock']} adet var. Daha az adet belirtir misiniz?"
            
            conversation_context['stage'] = 'confirmation'
            return f"Tamam! {quantity} adet sipariş, toplam {total_price:.0f} TL. Onaylıyor musun?"
    
    elif user_input.upper() in ['EVET', 'ONAYLA', 'TAMAM', 'OK'] and conversation_context['stage'] == 'confirmation':
        # Confirm order
        conversation_context['stage'] = 'completed'
        order_id = int(time.time()) % 10000  # Simple order ID
        return f"✅ Sipariş başarıyla kaydedildi! Sipariş No: {order_id}. Başka bir şey lazım mı?"
    
    elif not diameter:
        # Initial state
        return "Hangi çap silindir arıyorsunuz?"
    
    # Default response
    return "Size nasıl yardımcı olabilirim? Silindir çapını belirtirseniz arama yapabilirim."

@app.route('/')
def index():
    """Main chat interface"""
    return render_template('chat.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    """Handle chat messages"""
    try:
        data = request.json
        user_message = data.get('message', '').strip()
        
        if not user_message:
            return jsonify({'error': 'Boş mesaj'}), 400
        
        # Generate response
        ai_response = generate_response(user_message)
        
        # Add to history
        conversation_context['conversation_history'].append({
            'user': user_message,
            'ai': ai_response,
            'timestamp': datetime.now().isoformat()
        })
        
        return jsonify({
            'response': ai_response,
            'stage': conversation_context['stage'],
            'context': conversation_context['user_preferences']
        })
        
    except Exception as e:
        return jsonify({'error': f'Hata: {str(e)}'}), 500

@app.route('/api/reset', methods=['POST'])
def reset_chat():
    """Reset conversation"""
    global conversation_context
    conversation_context = {
        'stage': 'discovery',
        'user_preferences': {
            'diameter': None,
            'stroke': None,
            'features': [],
            'quantity': None
        },
        'conversation_history': [],
        'found_products': []
    }
    return jsonify({'message': 'Konuşma sıfırlandı'})

if __name__ == '__main__':
    print("🚀 B2B Chat Web Interface (Simplified) başlatılıyor...")
    print("📱 Tarayıcıda aç: http://localhost:5000")
    print("💡 Mock data kullanılıyor - gerçek veritabanı gerekmez!")
    app.run(debug=True, host='0.0.0.0', port=5000)
#!/usr/bin/env python3
"""
WhatsApp Bot - Twilio WhatsApp API Integration
"""

import os
import sys
import json
from flask import Flask, request, jsonify
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse

# Add parent directory to path for imports
sys.path.append(os.path.dirname(__file__))
from conversation_system import B2BConversationSystem

app = Flask(__name__)

# Twilio Configuration - Load from environment variables
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_WHATSAPP_NUMBER = os.getenv('TWILIO_WHATSAPP_NUMBER', 'whatsapp:+14155238886')

# Initialize Twilio client with region optimization
try:
    # Try Ireland region first (better for Turkey)
    twilio_client = Client(
        TWILIO_ACCOUNT_SID, 
        TWILIO_AUTH_TOKEN,
        region='dublin',
        edge='dublin'
    )
    print("[Twilio] Connected to Dublin region")
except:
    # Fallback to default (US)
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    print("[Twilio] Connected to US region")

# Global conversation systems per phone number
conversation_systems = {}  # phone_number -> B2BConversationSystem
db_connection = "postgresql://postgres:masterkey@localhost:5432/b2b_rag_system"

def get_conversation_system(phone_number):
    """Get or create conversation system for phone number"""
    global conversation_systems
    if phone_number not in conversation_systems:
        conversation_systems[phone_number] = B2BConversationSystem(db_connection)
        print(f"[WhatsApp] Created new conversation system for: {phone_number}")
    return conversation_systems[phone_number]

def send_whatsapp_message(to_number, message):
    """Send WhatsApp message via Twilio"""
    try:
        print(f"[WhatsApp] Sending to {to_number}: {message}")
        
        response = twilio_client.messages.create(
            from_=TWILIO_WHATSAPP_NUMBER,
            body=message,
            to=f'whatsapp:{to_number}'
        )
        print(f"[WhatsApp] SUCCESS! Message SID: {response.sid}")
        return True
    except Exception as e:
        print(f"[WhatsApp] ERROR sending message: {e}")
        return False

@app.route('/whatsapp/webhook', methods=['POST'])
def whatsapp_webhook():
    """Handle incoming WhatsApp messages"""
    try:
        print(f"[WhatsApp] RAW REQUEST: {request.form}")
        print(f"[WhatsApp] HEADERS: {dict(request.headers)}")
        
        # Get message data
        from_number = request.form.get('From', '').replace('whatsapp:', '')
        message_body = request.form.get('Body', '').strip()
        
        print(f"[WhatsApp] Received from {from_number}: {message_body}")
        
        if not message_body:
            print("[WhatsApp] Empty message, ignoring")
            return '', 200
        
        # Get conversation system for this phone number
        system = get_conversation_system(from_number)
        
        # Generate AI response
        ai_response = system.generate_response(message_body)
        
        # Check if products were found and add link
        if (system.context.conversation_stage == 'product_selection' and 
            system.context.selected_products):
            
            # Create product selection link
            base_url = "https://benz-net-excellence-breeding.trycloudflare.com"  # Actual tunnel URL
            product_link = f"{base_url}/whatsapp/products/{from_number.replace('+', '')}"
            
            ai_response += f"\n\n🛒 Ürünleri [buradan]({product_link}) inceleyebilirsiniz."
        
        # Send response back
        send_whatsapp_message(from_number, ai_response)
        
        return '', 200
        
    except Exception as e:
        print(f"[WhatsApp] Webhook error: {e}")
        return '', 500

@app.route('/whatsapp/products/<phone_number>')
def whatsapp_product_page(phone_number):
    """WhatsApp product selection page"""
    # Add + back to phone number
    full_phone = '+' + phone_number
    
    # Get conversation system
    system = get_conversation_system(full_phone)
    
    if not system.context.selected_products:
        return "Ürün bulunamadı. Lütfen WhatsApp'ta yeniden arama yapın."
    
    # Render mobile-friendly product page
    return render_template('whatsapp_products.html', 
                         products=system.context.selected_products,
                         phone_number=phone_number,
                         specs=system.context.extracted_specs)

@app.route('/whatsapp/select/<phone_number>/<int:product_id>')
def whatsapp_product_select(phone_number, product_id):
    """Handle product selection from WhatsApp page"""
    try:
        # Add + back to phone number
        full_phone = '+' + phone_number
        
        # Get conversation system
        system = get_conversation_system(full_phone)
        
        # Find selected product
        selected_product = None
        for product in system.context.selected_products:
            if product['id'] == product_id:
                selected_product = product
                break
        
        if not selected_product:
            return "Ürün bulunamadı!"
        
        # Store selection in context
        system.context.current_order = (selected_product, None)
        system.context.conversation_stage = 'order_creation'
        
        # Send WhatsApp message
        message = f"✅ '{selected_product['name']}' ürününü seçtiniz. Kaç adet sipariş vermek istiyorsunuz?"
        send_whatsapp_message(full_phone, message)
        
        return f"""
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>Seçim Tamamlandı</title>
            <style>
                body {{ font-family: Arial; text-align: center; padding: 50px; background: #e5ddd5; }}
                .success {{ background: white; padding: 30px; border-radius: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .icon {{ font-size: 50px; margin-bottom: 20px; }}
            </style>
        </head>
        <body>
            <div class="success">
                <div class="icon">✅</div>
                <h2>Seçiminiz Kaydedildi!</h2>
                <p><strong>{selected_product['name']}</strong></p>
                <p>WhatsApp'a dönüp adet belirtin.</p>
                <br>
                <p style="color: #666; font-size: 14px;">Bu sayfayı kapatabilirsiniz.</p>
            </div>
        </body>
        </html>
        """
        
    except Exception as e:
        print(f"[WhatsApp] Selection error: {e}")
        return "Hata oluştu!"

if __name__ == '__main__':
    print("🤖 WhatsApp Bot Starting...")
    print("Twilio webhook URL: http://localhost:5001/whatsapp/webhook")
    print("Product pages: http://localhost:5001/whatsapp/products/[phone]")
    
    app.run(debug=True, host='0.0.0.0', port=5001)
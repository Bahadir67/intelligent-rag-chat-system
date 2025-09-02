#!/usr/bin/env python3
"""
WhatsApp Bot - whatsapp-web.js ile (Ücretsiz)
QR kod ile bağlan, normal hesabınla çalış
"""

import sys
import subprocess
import time
from flask import Flask, request, jsonify
import requests
import json

sys.path.append('.')
from conversation_system import B2BConversationSystem

app = Flask(__name__)

# Global conversation systems per phone number
conversation_systems = {}
db_connection = "postgresql://postgres:masterkey@localhost:5432/b2b_rag_system"

def get_conversation_system(phone_number):
    """Get or create conversation system for phone number"""
    global conversation_systems
    if phone_number not in conversation_systems:
        conversation_systems[phone_number] = B2BConversationSystem(db_connection)
        print(f"[WhatsApp] Created conversation system for: {phone_number}")
    return conversation_systems[phone_number]

def send_whatsapp_message(phone_number, message):
    """Send WhatsApp message via web.js API"""
    try:
        # Local whatsapp-web.js API endpoint
        url = "http://localhost:3000/send-message"
        data = {
            "chatId": f"{phone_number}@c.us",
            "message": message
        }
        
        response = requests.post(url, json=data, timeout=5)
        if response.status_code == 200:
            print(f"[WhatsApp] Message sent to {phone_number}")
            return True
        else:
            print(f"[WhatsApp] Failed to send: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"[WhatsApp] Error: {e}")
        return False

@app.route('/whatsapp/webhook', methods=['POST'])
def whatsapp_webhook():
    """Handle incoming WhatsApp messages from web.js"""
    try:
        data = request.json
        
        phone_number = data.get('from', '').replace('@c.us', '')
        message_body = data.get('body', '').strip()
        
        print(f"[WhatsApp] Received from {phone_number}: {message_body}")
        
        if not message_body:
            return '', 200
        
        # Get conversation system
        system = get_conversation_system(phone_number)
        
        # Generate AI response
        ai_response = system.generate_response(message_body)
        
        # Check if products were found and add link
        if (system.context.conversation_stage == 'product_selection' and 
            system.context.selected_products):
            
            base_url = "https://benz-net-excellence-breeding.trycloudflare.com"
            product_link = f"{base_url}/whatsapp/products/{phone_number}"
            
            ai_response += f"\n\n🛒 Ürünleri buradan inceleyebilirsiniz: {product_link}"
        
        # Send response back
        send_whatsapp_message(phone_number, ai_response)
        
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"[WhatsApp] Webhook error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/whatsapp/products/<phone_number>')
def whatsapp_product_page(phone_number):
    """WhatsApp product selection page"""
    system = get_conversation_system(phone_number)
    
    if not system.context.selected_products:
        return "Ürün bulunamadı. Lütfen WhatsApp'ta yeniden arama yapın."
    
    return render_template('whatsapp_products.html', 
                         products=system.context.selected_products,
                         phone_number=phone_number,
                         specs=system.context.extracted_specs)

@app.route('/whatsapp/select/<phone_number>/<int:product_id>')
def whatsapp_product_select(phone_number, product_id):
    """Handle product selection"""
    try:
        system = get_conversation_system(phone_number)
        
        selected_product = None
        for product in system.context.selected_products:
            if product['id'] == product_id:
                selected_product = product
                break
        
        if not selected_product:
            return "Ürün bulunamadı!"
        
        # Store selection
        system.context.current_order = (selected_product, None)
        system.context.conversation_stage = 'order_creation'
        
        # Send WhatsApp message
        message = f"✅ '{selected_product['name']}' seçtiniz. Kaç adet istiyorsunuz?"
        send_whatsapp_message(phone_number, message)
        
        return "✅ Seçiminiz kaydedildi! WhatsApp'a dönün."
        
    except Exception as e:
        return f"Hata: {e}"

def start_whatsapp_webjs():
    """Start WhatsApp Web.js server"""
    print("Starting WhatsApp Web.js server...")
    print("QR kodu tarayacaksınız...")
    
    # Bu Node.js script'i çalıştırır
    # npm install whatsapp-web.js gerekli
    pass

if __name__ == '__main__':
    print("🚀 WhatsApp Web.js Bot Starting...")
    print("1. Node.js ve npm kurulu olmalı")
    print("2. QR kod ile WhatsApp'a bağlanacak")
    print("3. Normal hesabınızla çalışacak")
    print("\nTwilio'ya veda! 😊")
    
    app.run(debug=True, host='0.0.0.0', port=5001)
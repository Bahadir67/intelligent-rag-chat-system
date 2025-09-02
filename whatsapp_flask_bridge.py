#!/usr/bin/env python3
"""
WhatsApp Flask Bridge - Node.js WhatsApp Web.js ile Python conversation system arasında köprü
"""

import sys
import os
import json
import requests
from flask import Flask, request, jsonify, render_template

# Add parent directory to path for imports
sys.path.append(os.path.dirname(__file__))
from conversation_system import B2BConversationSystem

app = Flask(__name__, template_folder='web_chat/templates')

# Configure Flask for UTF-8
app.config['JSON_AS_ASCII'] = False
app.config['JSON_SORT_KEYS'] = False

# Global conversation systems per phone number
conversation_systems = {}
db_connection = "postgresql://postgres:masterkey@localhost:5432/b2b_rag_system"

def get_conversation_system(phone_number):
    """Get or create conversation system for phone number"""
    global conversation_systems
    # Clean phone number
    clean_phone = phone_number.replace('@c.us', '').replace('whatsapp:', '')
    
    if clean_phone not in conversation_systems:
        conversation_systems[clean_phone] = B2BConversationSystem(db_connection, clean_phone)
        print(f"[Bridge] Created conversation system for: {clean_phone}")
    return conversation_systems[clean_phone]

def send_whatsapp_message(phone_number, message):
    """Send message via Node.js WhatsApp Web.js API"""
    try:
        # Node.js API endpoint
        url = "http://localhost:3000/send-message"
        data = {
            "to": phone_number,
            "message": message
        }
        
        response = requests.post(url, json=data, timeout=5)
        if response.status_code == 200:
            print(f"[Bridge] Message sent to {phone_number}")
            return True
        else:
            print(f"[Bridge] Failed to send: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"[Bridge] Send error: {e}")
        return False

@app.route('/whatsapp/process', methods=['POST'])
def process_whatsapp_message():
    """Process WhatsApp message from Node.js"""
    import traceback
    try:
        print("[Bridge] Received request")
        
        # Handle UTF-8 encoding issues
        try:
            data = request.json
            print(f"[Bridge] Successfully parsed JSON: {data}")
        except Exception as decode_error:
            print(f"[Bridge] JSON decode error: {decode_error}")
            print(f"[Bridge] Error type: {type(decode_error)}")
            traceback.print_exc()
            # Fallback for encoding issues
            raw_data = request.get_data()
            print(f"[Bridge] Raw data length: {len(raw_data)}")
            try:
                # Try different encodings
                data_str = raw_data.decode('utf-8')
                print("[Bridge] Successfully decoded as UTF-8")
            except UnicodeDecodeError:
                try:
                    data_str = raw_data.decode('iso-8859-1')
                    print("[Bridge] Successfully decoded as ISO-8859-1")
                except UnicodeDecodeError:
                    data_str = raw_data.decode('cp1254')  # Turkish encoding
                    print("[Bridge] Successfully decoded as CP1254")
            
            import json
            data = json.loads(data_str)
            print(f"[Bridge] Parsed JSON from raw data: {data}")
        
        from_number = data.get('from', '')
        message_body = data.get('body', '').strip()
        
        # Ensure UTF-8 encoding for Turkish characters
        if isinstance(message_body, str):
            # Normalize Turkish characters
            message_body = message_body.encode('utf-8').decode('utf-8')
        
        print(f"[Bridge] Processing: {from_number} -> {message_body}")
        
        if not message_body:
            return jsonify({'reply': None})
        
        # Get conversation system
        print("[Bridge] Getting conversation system...")
        system = get_conversation_system(from_number)
        print("[Bridge] Got conversation system successfully")
        
        # Handle conversation stages like in main conversation loop
        stage = system.context.conversation_stage
        print(f"[Bridge] Current stage: {stage}")
        
        # More flexible quantity detection for order_creation stage
        is_quantity_input = (
            stage == 'order_creation' and 
            (message_body.isdigit() or 
             any(word in message_body.lower() for word in ['adet', 'tane', 'parça', 'piece']))
        )
        
        if is_quantity_input:
            # Quantity input
            print(f"[Bridge] About to handle quantity input: {message_body}")
            print(f"[Bridge] Current order before: {system.context.current_order}")
            try:
                ai_response = system.handle_quantity_input(message_body)
                print(f"[Bridge] Handled quantity input successfully: {message_body}")
                print(f"[Bridge] Response: {ai_response[:100]}...")
            except Exception as e:
                print(f"[Bridge] ERROR in handle_quantity_input: {e}")
                import traceback
                traceback.print_exc()
                ai_response = "❌ Sipariş kaydedilemedi. Lütfen tekrar deneyiniz."
        elif stage == 'order_confirmation':
            # Order confirmation
            ai_response = system.handle_order_confirmation(message_body)
            print(f"[Bridge] Handled order confirmation: {message_body}")
        else:
            # Generate AI response
            ai_response = system.generate_response(message_body)
        
        # Check if products were found and add link  
        print(f"[Bridge] After AI response - Stage: {system.context.conversation_stage}, Products: {len(system.context.selected_products) if system.context.selected_products else 0}")
        
        if (system.context.conversation_stage == 'product_selection' and 
            system.context.selected_products):
            
            # Cloudflare tunnel URL - GÜNCEL
            base_url = "https://fired-sq-remedies-cheapest.trycloudflare.com"
            clean_phone = from_number.replace('@c.us', '').replace('+', '')
            product_link = f"{base_url}/whatsapp/products/{clean_phone}"
            
            ai_response += f"\n\n🛒 Ürünleri *buradan* inceleyebilirsiniz:\n{product_link}"
        
        # Ensure response is properly UTF-8 encoded
        response_data = {'reply': ai_response}
        response = jsonify(response_data)
        response.charset = 'utf-8'
        return response
        
    except Exception as e:
        print(f"[Bridge] Process error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'reply': 'Özür dilerim, bir hata oluştu. Tekrar deneyin.'}), 500

@app.route('/whatsapp/products/<phone_number>')
def whatsapp_product_page(phone_number):
    """WhatsApp product selection page"""
    try:
        system = get_conversation_system(phone_number)
        
        if not system.context.selected_products:
            return """
            <html><body style='text-align:center; padding:50px; font-family:Arial;'>
                <h2>😔 Ürün Bulunamadı</h2>
                <p>Lütfen WhatsApp'ta yeniden arama yapın.</p>
            </body></html>
            """
        
        return render_template('whatsapp_products.html', 
                             products=system.context.selected_products,
                             phone_number=phone_number,
                             specs=system.context.extracted_specs)
    except Exception as e:
        return f"<html><body><h2>Hata:</h2><p>{e}</p></body></html>"

@app.route('/whatsapp/select/<phone_number>/<int:product_id>')
def whatsapp_product_select(phone_number, product_id):
    """Handle product selection"""
    try:
        system = get_conversation_system(phone_number)
        
        # Find selected product
        selected_product = None
        for product in system.context.selected_products:
            if product['id'] == product_id:
                selected_product = product
                break
        
        if not selected_product:
            return """
            <html><body style='text-align:center; padding:50px; font-family:Arial;'>
                <h2>❌ Ürün Bulunamadı</h2>
                <p>Bu sayfayı kapatabilirsiniz.</p>
            </body></html>
            """
        
        # Check stock before processing order
        stock = selected_product.get('stock', 0)
        
        # Send WhatsApp message with detailed product info
        whatsapp_phone = f"{phone_number}@c.us" if '@c.us' not in phone_number else phone_number
        
        # Format price display
        price_text = f"{selected_product['price']:.2f} TL" if selected_product.get('price', 0) > 0 else "Fiyat sorulacak"
        
        if stock <= 0:
            # Zero or negative stock - don't go to order creation
            system.context.conversation_stage = 'general'
            message = f"""✅ ÜRÜN SEÇİLDİ
        
📦 {selected_product['name']}
🏷️ Ürün Kodu: {selected_product.get('urun_kodu', 'Kod yok')}
⚠️ Stok: {stock:.0f} adet (Stokta yok)
💰 Fiyat: {price_text}

📝 Bu ürün şu an stokta bulunmamaktadır. Tedarik süresi ve fiyat bilgisi için müşteri temsilcimizle iletişime geçebilirsiniz."""
        else:
            # Product has stock - proceed with order creation
            system.context.current_order = (selected_product, None)
            system.context.conversation_stage = 'order_creation'
            message = f"""✅ ÜRÜN SEÇİLDİ
        
📦 {selected_product['name']}
🏷️ Ürün Kodu: {selected_product.get('urun_kodu', 'Kod yok')}
📊 Stok: {stock:.0f} adet
💰 Fiyat: {price_text}

❓ Kaç adet istiyorsunuz?"""
        
        # Send via Node.js API
        send_success = send_whatsapp_message(whatsapp_phone, message)
        
        # Check if this is an AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # For AJAX requests, return simple success response
            return jsonify({'success': True, 'message': f"'{selected_product['name']}' selected"})
        else:
            # For regular requests, return the old page-based response
            return """
            <html><body style='background:#25d366;color:white;display:flex;flex-direction:column;align-items:center;justify-content:center;height:100vh;font-family:Arial;margin:0;'>
                <h2 style='margin-bottom:20px;'>✅ Seçim Kaydedildi!</h2>
                <p>WhatsApp'ta mesajınızı bekleyin</p>
                <p style='font-size:14px;margin-top:20px;'>Bu sayfa otomatik kapanacak...</p>
            </body>
            <script>
                setTimeout(() => {
                    try {
                        if (window.history.length > 1) {
                            window.history.back();
                        } else {
                            window.location.href = "whatsapp://";
                        }
                    } catch(e) {
                        console.warn('Navigation failed:', e);
                    }
                }, 1000);
            </script>
            </html>
            """
        
    except Exception as e:
        return f"""
        <html><body style='text-align:center; padding:50px; font-family:Arial;'>
            <h2>❌ Hata</h2>
            <p>{e}</p>
        </body></html>
        """

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'OK',
        'bridge': 'active',
        'conversations': len(conversation_systems),
        'timestamp': 'now'
    })

if __name__ == '__main__':
    print("🌉 WhatsApp Flask Bridge Starting...")
    print("🔗 Node.js WhatsApp Web.js: http://localhost:3000")
    print("🐍 Python Bridge: http://localhost:5002")
    print("📱 QR kod Node.js'de gösterilecek")
    
    app.run(debug=True, host='0.0.0.0', port=5002)
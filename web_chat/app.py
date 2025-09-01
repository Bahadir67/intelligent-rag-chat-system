#!/usr/bin/env python3
"""
B2B Chat Web Interface - Flask app
"""

from flask import Flask, render_template, request, jsonify
import sys
import os
sys.path.append('..')
from intelligent_conversation import IntelligentB2BSystem

app = Flask(__name__)
app.secret_key = 'b2b_chat_secret_key'

# Global chat system instance
chat_system = None

def init_chat_system():
    """Initialize chat system once"""
    global chat_system
    if chat_system is None:
        db_connection = "postgresql://postgres:masterkey@localhost:5432/b2b_rag_system"
        chat_system = IntelligentB2BSystem(db_connection)
    return chat_system

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
        
        # Get or initialize chat system
        system = init_chat_system()
        
        # Generate response
        ai_response = system.generate_intelligent_response(user_message)
        
        # Add to conversation history
        system.context.add_exchange(user_message, ai_response)
        
        # Save to memory periodically
        if len(system.context.conversation_history) % 3 == 0:
            system.save_user_memory()
        
        return jsonify({
            'response': ai_response,
            'stage': system.context.conversation_stage,
            'context': {
                'diameter': system.context.user_preferences.get('diameter'),
                'stroke': system.context.user_preferences.get('stroke'),
                'features': system.context.user_preferences.get('features', [])
            }
        })
        
    except Exception as e:
        return jsonify({'error': f'Hata: {str(e)}'}), 500

@app.route('/api/reset', methods=['POST'])
def reset_chat():
    """Reset conversation"""
    global chat_system
    if chat_system:
        chat_system.save_user_memory()
        chat_system = None
    return jsonify({'message': 'Konuşma sıfırlandı'})

if __name__ == '__main__':
    print("🚀 B2B Chat Web Interface başlatılıyor...")
    print("📱 Tarayıcıda aç: http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
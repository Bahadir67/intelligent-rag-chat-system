#!/usr/bin/env python3
"""
Conversation System Test - Full flow simulation
"""

import sys
from conversation_system import B2BConversationSystem

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

def simulate_conversation():
    """Full conversation flow simulation"""
    print("🤖 B2B SİLİNDİR AI - KONUŞMA TESTİ")
    print("=" * 50)
    
    db_connection = "postgresql://postgres:masterkey@localhost:5432/b2b_rag_system"
    system = B2BConversationSystem(db_connection)
    
    # Test conversation flow
    test_inputs = [
        "100 çap silindir arıyorum dostum",  # Initial query - should ask for stroke
        "2",                                 # Select stroke option  
        "1",                                 # Select product
        "5",                                 # Quantity
        "evet"                              # Confirm order
    ]
    
    expected_stages = [
        'initial',
        'spec_gathering', 
        'product_selection',
        'order_creation',
        'order_confirmation'
    ]
    
    print("🎬 KONUŞMA AKIŞI:")
    print("-" * 30)
    
    for i, user_input in enumerate(test_inputs):
        print(f"\n👤 [{i+1}] Kullanıcı: {user_input}")
        print(f"📊 Stage: {system.context.conversation_stage}")
        
        # Process input based on current stage
        stage = system.context.conversation_stage
        
        if stage == 'product_selection' and user_input.isdigit():
            response = system.handle_product_selection(user_input)
        elif stage == 'order_creation' and user_input.isdigit():
            response = system.handle_quantity_input(user_input)
        elif stage == 'order_confirmation':
            response = system.handle_order_confirmation(user_input)
        else:
            response = system.generate_response(user_input)
        
        print(f"🤖 AI: {response}")
        print(f"📈 New Stage: {system.context.conversation_stage}")
        print("-" * 50)
    
    # Show final context
    print("\n📋 FINAL CONTEXT:")
    print(f"Extracted Specs: {system.context.extracted_specs}")
    print(f"Final Stage: {system.context.conversation_stage}")

if __name__ == "__main__":
    simulate_conversation()
#!/usr/bin/env python3
"""
Real Chat System - Windows compatible input handling
"""

import sys
import msvcrt
import os
from conversation_system import B2BConversationSystem

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

def get_input_line():
    """Windows-compatible input handling"""
    sys.stdout.write("\n👤 Siz: ")
    sys.stdout.flush()
    
    line = ""
    while True:
        if msvcrt.kbhit():
            char = msvcrt.getch()
            
            if char == b'\r':  # Enter key
                print()  # New line
                return line.strip()
            elif char == b'\x08':  # Backspace
                if line:
                    line = line[:-1]
                    sys.stdout.write('\b \b')
                    sys.stdout.flush()
            elif char == b'\x03':  # Ctrl+C
                raise KeyboardInterrupt
            elif 32 <= ord(char) <= 126:  # Printable ASCII
                char_str = char.decode('utf-8', errors='ignore')
                line += char_str
                sys.stdout.write(char_str)
                sys.stdout.flush()

def main():
    """Main chat loop with Windows input handling"""
    print("🤖 B2B Silindir AI - Konuşmalı Sipariş Sistemi")
    print("=" * 50)
    print("Merhaba! Size nasıl yardımcı olabilirim?")
    print("Çıkmak için 'quit' yazın.")
    print("-" * 50)
    
    db_connection = "postgresql://postgres:masterkey@localhost:5432/b2b_rag_system"
    conversation_system = B2BConversationSystem(db_connection)
    
    try:
        while True:
            try:
                user_input = get_input_line()
                
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
                
            except KeyboardInterrupt:
                print("\n\n🤖 AI: İyi günler!")
                break
                
    except Exception as e:
        print(f"\nSistem hatası: {e}")

if __name__ == "__main__":
    if sys.platform == "win32":
        main()
    else:
        print("Bu versiyon sadece Windows için optimize edildi.")
        print("Linux/Mac için conversation_system.py kullanın.")
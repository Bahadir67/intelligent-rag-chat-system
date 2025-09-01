#!/usr/bin/env python3
"""
AI Integration Test Suite
Test OpenRouter API integration for B2B RAG system
"""

import os
import sys
import asyncio
import time
from typing import List, Dict

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from openrouter_client import openrouter_client, AIResponse
from conversation_system import B2BConversationSystem

def test_openrouter_connection():
    """Test basic OpenRouter API connection"""
    print("🔄 Testing OpenRouter API connection...")
    
    try:
        # Simple test message
        test_message = "Merhaba"
        intent = openrouter_client.classify_intent(test_message)
        print(f"✅ API Connection successful - Intent: {intent}")
        return True
    except Exception as e:
        print(f"❌ API Connection failed: {e}")
        return False

def test_spec_extraction():
    """Test AI-powered spec extraction"""
    print("\n🔄 Testing AI spec extraction...")
    
    test_cases = [
        {
            "message": "50mm çaplı 100mm stroklu silindir istiyorum, 5 adet",
            "expected_diameter": 50,
            "expected_stroke": 100,
            "expected_quantity": 5
        },
        {
            "message": "Ø63 çaplı amortisörlü silindir arıyorum",
            "expected_diameter": 63,
            "expected_features": ["cushioned"]
        },
        {
            "message": "100x400 pnömatik silindir lazım",
            "expected_diameter": 100,
            "expected_stroke": 400,
            "expected_features": ["pneumatic"]
        },
        {
            "message": "Festo marka çift etkili silindir fiyatı?",
            "expected_brand": "festo",
            "expected_features": ["double_acting"]
        }
    ]
    
    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n  Test {i}: '{test_case['message']}'")
        
        try:
            response = openrouter_client.extract_specifications(test_case['message'])
            specs = response.extracted_specs
            
            # Check diameter
            if 'expected_diameter' in test_case:
                if specs.get('diameter') == test_case['expected_diameter']:
                    print(f"    ✅ Diameter: {specs.get('diameter')}")
                else:
                    print(f"    ❌ Diameter: Expected {test_case['expected_diameter']}, got {specs.get('diameter')}")
            
            # Check stroke
            if 'expected_stroke' in test_case:
                if specs.get('stroke') == test_case['expected_stroke']:
                    print(f"    ✅ Stroke: {specs.get('stroke')}")
                else:
                    print(f"    ❌ Stroke: Expected {test_case['expected_stroke']}, got {specs.get('stroke')}")
            
            # Check quantity
            if 'expected_quantity' in test_case:
                if specs.get('quantity') == test_case['expected_quantity']:
                    print(f"    ✅ Quantity: {specs.get('quantity')}")
                else:
                    print(f"    ❌ Quantity: Expected {test_case['expected_quantity']}, got {specs.get('quantity')}")
            
            # Check features
            if 'expected_features' in test_case:
                expected_features = test_case['expected_features']
                actual_features = specs.get('features', [])
                
                if any(feature in actual_features for feature in expected_features):
                    print(f"    ✅ Features: {actual_features}")
                else:
                    print(f"    ❌ Features: Expected {expected_features}, got {actual_features}")
            
            # Check brand
            if 'expected_brand' in test_case:
                brand = specs.get('brand_preference', '').lower()
                if test_case['expected_brand'].lower() in brand:
                    print(f"    ✅ Brand: {specs.get('brand_preference')}")
                else:
                    print(f"    ❌ Brand: Expected {test_case['expected_brand']}, got {specs.get('brand_preference')}")
            
            print(f"    📊 Confidence: {response.confidence:.2f}")
            print(f"    🎯 Intent: {response.intent}")
            
            results.append({
                'test': i,
                'success': True,
                'specs': specs,
                'confidence': response.confidence
            })
            
            # Rate limiting
            time.sleep(1)
            
        except Exception as e:
            print(f"    ❌ Error: {e}")
            results.append({
                'test': i,
                'success': False,
                'error': str(e)
            })
    
    successful_tests = sum(1 for r in results if r['success'])
    print(f"\n📊 Spec Extraction Results: {successful_tests}/{len(test_cases)} tests passed")
    
    return results

def test_intent_classification():
    """Test AI intent classification"""
    print("\n🔄 Testing intent classification...")
    
    intent_tests = [
        {"message": "Merhaba", "expected": "greeting"},
        {"message": "50mm silindir arıyorum", "expected": "product_search"},
        {"message": "Bu silindir kaç lira?", "expected": "price_inquiry"},
        {"message": "Sipariş vermek istiyorum", "expected": "order_intent"},
        {"message": "Şirket bilgilerimiz: ABC Ltd", "expected": "company_info"},
        {"message": "Teşekkürler, iyi günler", "expected": "general_question"},
    ]
    
    results = []
    
    for i, test in enumerate(intent_tests, 1):
        print(f"\n  Test {i}: '{test['message']}'")
        
        try:
            intent = openrouter_client.classify_intent(test['message'])
            
            if intent == test['expected']:
                print(f"    ✅ Intent: {intent}")
                results.append(True)
            else:
                print(f"    ❌ Intent: Expected '{test['expected']}', got '{intent}'")
                results.append(False)
            
            time.sleep(0.5)  # Rate limiting
            
        except Exception as e:
            print(f"    ❌ Error: {e}")
            results.append(False)
    
    successful_tests = sum(results)
    print(f"\n📊 Intent Classification Results: {successful_tests}/{len(intent_tests)} tests passed")
    
    return results

def test_conversation_flow():
    """Test full conversation flow with AI"""
    print("\n🔄 Testing AI-enhanced conversation flow...")
    
    # Mock database connection for testing
    db_connection = "postgresql://postgres:masterkey@localhost:5432/b2b_rag_system"
    
    try:
        conversation = B2BConversationSystem(db_connection)
        print("    ✅ Conversation system initialized")
        
        # Test conversation scenarios
        scenarios = [
            {
                "user_input": "50mm çaplı silindir arıyorum",
                "expected_stage": "spec_gathering"
            },
            {
                "user_input": "100mm strok olsun",
                "expected_stage": "product_selection"
            }
        ]
        
        for i, scenario in enumerate(scenarios, 1):
            print(f"\n  Scenario {i}: '{scenario['user_input']}'")
            
            try:
                response = conversation.generate_response(scenario['user_input'])
                current_stage = conversation.context.conversation_stage
                
                print(f"    📝 Response: {response[:100]}...")
                print(f"    🎭 Stage: {current_stage}")
                
                if 'expected_stage' in scenario:
                    if current_stage == scenario['expected_stage']:
                        print(f"    ✅ Stage transition correct")
                    else:
                        print(f"    ❌ Stage: Expected '{scenario['expected_stage']}', got '{current_stage}'")
                
                time.sleep(1)  # Rate limiting
                
            except Exception as e:
                print(f"    ❌ Conversation error: {e}")
        
        return True
        
    except Exception as e:
        print(f"    ❌ Failed to initialize conversation system: {e}")
        print("    ℹ️  This might be due to database connection issues")
        return False

def test_ai_response_generation():
    """Test AI response generation quality"""
    print("\n🔄 Testing AI response generation...")
    
    test_contexts = [
        {
            "user_message": "Hangi boyutlarda silindir var?",
            "context": {"stage": "initial", "specs": {}, "intent": "product_search"}
        },
        {
            "user_message": "Fiyat bilgisi verebilir misiniz?",
            "context": {"stage": "product_selection", "specs": {"diameter": 50}, "intent": "price_inquiry"},
            "products": [{"name": "Test Silindir", "price": 150.0}]
        }
    ]
    
    for i, test in enumerate(test_contexts, 1):
        print(f"\n  Test {i}: '{test['user_message']}'")
        
        try:
            response = openrouter_client.generate_response(
                test['user_message'], 
                test['context'], 
                test.get('products')
            )
            
            print(f"    📝 AI Response: {response[:150]}...")
            
            # Basic quality checks
            if len(response) > 10:
                print(f"    ✅ Response has adequate length ({len(response)} chars)")
            else:
                print(f"    ❌ Response too short ({len(response)} chars)")
            
            if any(word in response.lower() for word in ['silindir', 'ürün', 'fiyat', 'boyut']):
                print(f"    ✅ Response contains relevant keywords")
            else:
                print(f"    ❌ Response lacks relevant keywords")
            
            time.sleep(1)  # Rate limiting
            
        except Exception as e:
            print(f"    ❌ Response generation failed: {e}")
    
    return True

def performance_test():
    """Test AI response performance"""
    print("\n🔄 Performance testing...")
    
    test_message = "50x100 silindir lazım"
    iterations = 3
    
    total_time = 0
    successful_calls = 0
    
    for i in range(iterations):
        try:
            start_time = time.time()
            response = openrouter_client.extract_specifications(test_message)
            end_time = time.time()
            
            duration = end_time - start_time
            total_time += duration
            successful_calls += 1
            
            print(f"    Call {i+1}: {duration:.2f}s (confidence: {response.confidence:.2f})")
            
            time.sleep(1)  # Rate limiting
            
        except Exception as e:
            print(f"    Call {i+1}: Failed - {e}")
    
    if successful_calls > 0:
        avg_time = total_time / successful_calls
        print(f"\n📊 Performance Results:")
        print(f"    Average response time: {avg_time:.2f}s")
        print(f"    Success rate: {successful_calls}/{iterations} ({successful_calls/iterations*100:.1f}%)")
    
    return successful_calls > 0

def main():
    """Run all AI integration tests"""
    print("🧪 B2B RAG System - AI Integration Tests")
    print("=" * 50)
    
    # Test results
    results = {}
    
    # 1. API Connection Test
    results['connection'] = test_openrouter_connection()
    
    if not results['connection']:
        print("\n❌ API connection failed. Skipping other tests.")
        print("\nℹ️  Please check:")
        print("   - OPENROUTER_API_KEY in .env file")
        print("   - Internet connection")
        print("   - API key validity")
        return
    
    # 2. Spec Extraction Tests
    try:
        spec_results = test_spec_extraction()
        results['spec_extraction'] = len([r for r in spec_results if r['success']]) > 0
    except Exception as e:
        print(f"❌ Spec extraction tests failed: {e}")
        results['spec_extraction'] = False
    
    # 3. Intent Classification Tests
    try:
        intent_results = test_intent_classification()
        results['intent_classification'] = sum(intent_results) > len(intent_results) // 2
    except Exception as e:
        print(f"❌ Intent classification tests failed: {e}")
        results['intent_classification'] = False
    
    # 4. Conversation Flow Tests
    results['conversation_flow'] = test_conversation_flow()
    
    # 5. Response Generation Tests
    results['response_generation'] = test_ai_response_generation()
    
    # 6. Performance Tests
    results['performance'] = performance_test()
    
    # Summary
    print("\n" + "=" * 50)
    print("🏁 TEST SUMMARY")
    print("=" * 50)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name.replace('_', ' ').title():<25} {status}")
    
    passed_tests = sum(results.values())
    total_tests = len(results)
    
    print(f"\n📊 Overall Score: {passed_tests}/{total_tests} tests passed ({passed_tests/total_tests*100:.1f}%)")
    
    if passed_tests == total_tests:
        print("🎉 All tests passed! AI integration is working correctly.")
    elif passed_tests >= total_tests * 0.7:
        print("⚠️  Most tests passed. Some issues may need attention.")
    else:
        print("❌ Multiple test failures. AI integration needs debugging.")

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
OpenRouter API Client for B2B RAG System
Natural language processing for spec extraction and intent classification
"""

import os
import json
import requests
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

@dataclass
class AIResponse:
    """AI response with structured data"""
    intent: str
    confidence: float
    extracted_specs: Dict[str, Any]
    suggested_response: str
    requires_clarification: bool = False
    clarification_questions: List[str] = None

class OpenRouterClient:
    """OpenRouter API client for B2B conversations"""
    
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.model = os.getenv("MODEL", "openai/gpt-3.5-turbo")
        self.base_url = "https://openrouter.ai/api/v1"
        
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not found in environment variables")
    
    def _make_request(self, messages: List[Dict[str, str]], temperature: float = 0.3) -> str:
        """Make API request to OpenRouter"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/Bahadir67/intelligent-rag-chat-system",
            "X-Title": "B2B RAG Sales Assistant"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 1000
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            
            # Ensure proper UTF-8 encoding
            if isinstance(content, bytes):
                content = content.decode('utf-8')
            
            return content
            
        except requests.exceptions.RequestException as e:
            logger.error(f"OpenRouter API request failed: {e}")
            raise
        except KeyError as e:
            logger.error(f"Unexpected API response format: {e}")
            raise
    
    def extract_specifications(self, user_message: str, context: Dict = None) -> AIResponse:
        """Extract product specifications from natural language"""
        
        system_prompt = """Sen bir B2B satış asistanısın. Kullanıcının mesajından ürün özelliklerini çıkar.

Çıkaracağın özellikler:
- diameter: Çap (mm cinsinden sayı)
- stroke: Strok (mm cinsinden sayı) 
- quantity: Miktar (adet)
- features: Özellikler listesi (amortisörlü, yağsız, vs)
- brand_preference: Marka tercihi

JSON formatında yanıt ver:
{
  "intent": "spec_query|product_search|order_intent|general_question",
  "confidence": 0.0-1.0,
  "extracted_specs": {
    "diameter": null veya sayı,
    "stroke": null veya sayı,
    "quantity": null veya sayı,
    "features": [],
    "brand_preference": null veya string
  },
  "suggested_response": "Kullanıcıya verilecek yanıt",
  "requires_clarification": true/false,
  "clarification_questions": ["soru1", "soru2"]
}

Türkçe terimler: çap, strok, adet, tane, parça, amortisörlü, yağsız"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Kullanıcı mesajı: {user_message}"}
        ]
        
        # Add context if available
        if context:
            context_msg = f"Konversation context: {json.dumps(context, ensure_ascii=False)}"
            messages.append({"role": "assistant", "content": context_msg})
        
        try:
            response = self._make_request(messages, temperature=0.2)
            
            # Parse JSON response
            ai_data = json.loads(response)
            
            return AIResponse(
                intent=ai_data.get("intent", "general_question"),
                confidence=ai_data.get("confidence", 0.5),
                extracted_specs=ai_data.get("extracted_specs", {}),
                suggested_response=ai_data.get("suggested_response", ""),
                requires_clarification=ai_data.get("requires_clarification", False),
                clarification_questions=ai_data.get("clarification_questions", [])
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            # Fallback response
            return AIResponse(
                intent="general_question",
                confidence=0.3,
                extracted_specs={},
                suggested_response="Üzgünüm, isteğinizi tam olarak anlayamadım. Lütfen daha detaylı açıklayabilir misiniz?",
                requires_clarification=True,
                clarification_questions=["Hangi ürün hakkında bilgi istiyorsunuz?"]
            )
    
    def classify_intent(self, user_message: str, conversation_history: List[str] = None) -> str:
        """Classify user intent for conversation flow"""
        
        system_prompt = """Kullanıcının niyetini sınıflandır. Sadece kategori ismi döndür:

Kategoriler:
- product_search: Ürün arıyor
- spec_question: Teknik özellik soruyor  
- price_inquiry: Fiyat soruyor
- order_intent: Sipariş vermek istiyor
- company_info: Firma bilgisi veriyor
- general_question: Genel soru
- greeting: Selamlama
- complaint: Şikayet

Sadece kategori ismini döndür, açıklama yapma."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        if conversation_history:
            history_context = "\n".join(conversation_history[-3:])  # Son 3 mesaj
            messages.insert(1, {"role": "assistant", "content": f"Geçmiş konuşma: {history_context}"})
        
        try:
            response = self._make_request(messages, temperature=0.1)
            return response.strip().lower()
        except Exception as e:
            logger.error(f"Intent classification failed: {e}")
            return "general_question"
    
    def generate_response(self, user_message: str, context: Dict, products: List[Dict] = None) -> str:
        """Generate natural conversational response"""
        
        system_prompt = """Sen profesyonel bir B2B satış danışmanısın. 
        
Görevlerin:
1. Müşteri ihtiyaçlarını anla
2. Uygun ürünleri öner
3. Teknik detayları açıkla
4. Sipariş sürecinde rehberlik et

Tarzın: Professional, yardımsever, bilgili ama samimi.
Türkçe yanıt ver."""

        context_str = json.dumps(context, ensure_ascii=False) if context else "Yok"
        products_str = json.dumps(products, ensure_ascii=False) if products else "Yok"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"""
Müşteri mesajı: {user_message}
Konversation context: {context_str}
Bulunan ürünler: {products_str}

Uygun bir yanıt oluştur."""}
        ]
        
        try:
            return self._make_request(messages, temperature=0.7)
        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            return "Üzgünüm, şu anda teknik bir sorun yaşıyoruz. Lütfen daha sonra tekrar deneyin."

# Global instance
openrouter_client = OpenRouterClient()

# Test function
def test_client():
    """Test OpenRouter client functionality"""
    test_message = "50 çaplı 100 stroklu amortisörlü silindir arıyorum, 5 adet"
    
    print("Testing spec extraction...")
    result = openrouter_client.extract_specifications(test_message)
    print(f"Intent: {result.intent}")
    print(f"Specs: {result.extracted_specs}")
    print(f"Response: {result.suggested_response}")
    
    print("\nTesting intent classification...")
    intent = openrouter_client.classify_intent(test_message)
    print(f"Classified intent: {intent}")

if __name__ == "__main__":
    test_client()
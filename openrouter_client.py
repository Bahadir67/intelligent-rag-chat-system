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
    sub_intent: str = None
    action: str = None

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
            elif isinstance(content, str):
                # Fix any encoding issues in string
                try:
                    content = content.encode('latin1').decode('utf-8')
                except (UnicodeEncodeError, UnicodeDecodeError):
                    # If encoding fix fails, keep original
                    pass
            
            return content
            
        except requests.exceptions.RequestException as e:
            logger.error(f"OpenRouter API request failed: {e}")
            raise
        except KeyError as e:
            logger.error(f"Unexpected API response format: {e}")
            raise
    
    def extract_specifications(self, user_message: str, context: Dict = None, conversation_history: List[str] = None, previous_ai_response: str = None) -> AIResponse:
        """Extract product specifications from natural language"""
        
        system_prompt = """Sen bir B2B pnömatik ürün satış asistanısın. Kullanıcının mesajını analiz ederek hangi tür ürün aradığını ve ne yapılması gerektiğini belirle.

ANA ÜRÜN TİPLERİ:
1. ANA VALF (main_valve): 5/2, 3/2, 4/2, 5/3 vb. - Bağlantı boyutu parametresi gerekli
2. ANA SİLİNDİR (main_cylinder): Çap ve strok parametreleri gerekli  
3. VALF AKSESUARI (valve_accessory): Bobin, oransal valf, basınç regülatörü vb. - Direkt aranabilir
4. SİLİNDİR AKSESUARI (cylinder_accessory): Tamir takımı, bağlantı parçaları vb. - Direkt aranabilir

CLASSIFICATION LOGIC:
- Eğer "5/2 valf", "3/2 valf", "4/2 valf", "5/3 valf" gibi valf tipi belirtilmişse → main_valve
- Eğer çap/strok bilgisi varsa → main_cylinder  
- Eğer "bobin", "coil", "tamir", "repair", "bağlantı" gibi aksesuar kelimeler varsa → aksesuar kategorisi
- Belirsizse → unknown

JSON formatında yanıt ver:
{
  "intent": "spec_query|product_search|order_intent|general_question|product_code_search|incomplete_spec",
  "sub_intent": "main_valve|main_cylinder|valve_accessory|cylinder_accessory|unknown",
  "confidence": 0.0-1.0,
  "extracted_specs": {
    "diameter": null veya sayı,
    "stroke": null veya sayı,
    "quantity": null veya sayı,
    "features": [],
    "brand_preference": null veya string,
    "product_code": null veya string,
    "connection_size": null veya string,
    "special_properties": [],
    "corrected_query": "eğer yazım hatası varsa düzeltilmiş hali, yoksa null"
  },
  "suggested_response": "Kullanıcıya verilecek yanıt",
  "requires_clarification": true/false,
  "clarification_questions": ["soru1", "soru2"],
  "action": "search_direct|request_params|clarify_intent"
}

ACTION LOGIC:
- main_valve: action="request_params" (bağlantı boyutu sor)
- main_cylinder: action="request_params" (çap/strok eksikse sor) 
- valve_accessory/cylinder_accessory: action="search_direct" (direkt ara)
- unknown: action="clarify_intent"

ÖRNEKLER:
"5/2 valf arıyorum" → sub_intent: "main_valve", action: "request_params"
"24 VDC valf bobini" → sub_intent: "valve_accessory", action: "search_direct"
"100 çap silindir" → sub_intent: "main_cylinder", action: "request_params" 
"silindir tamir takımı" → sub_intent: "cylinder_accessory", action: "search_direct"

YAZIM HATASI DÜZELTME ÖNCELIĞI:
- "nerler var" → "neler var" düzelt
- "sartlandirici" → "şartlandırıcı" düzelt  
- "hidrilik" → "hidrolik" düzelt
- ÖNCE yazım hatalarını düzelt, SONRA işlemi yap

KRITIK SENARYOLAR:

VALF SCENARIOS:
- "5/2 valf arıyorum" → features: ["5/2"], requires_clarification: true, clarification_questions: ["Bağlantı boyutu: 1/4, 1/8, 1/2 - hangisi?"]
- "3/2 valf" → features: ["3/2"], intent: "incomplete_spec", requires_clarification: true, clarification_questions: ["Bağlantı boyutu: 1/4, 1/8, 1/2 - hangisi?"]
- "5/3 valf" → features: ["5/3"], intent: "incomplete_spec", requires_clarification: true, clarification_questions: ["Bağlantı boyutu: 1/4, 1/8, 1/2 - hangisi?"]
- "4/2 valf" → features: ["4/2"], intent: "incomplete_spec", requires_clarification: true, clarification_questions: ["Bağlantı boyutu: 1/4, 1/8, 1/2 - hangisi?"]

SILINDIR SCENARIOS:
- "100 lük silindir" → diameter: 100, intent: "incomplete_spec", clarification_questions: ["Strok uzunluğu kaç mm?"]
- "100 çap silindir" → diameter: 100, intent: "incomplete_spec"
- "100 mm çap silindir" → diameter: 100, intent: "incomplete_spec" 
- "200 strok" → stroke: 200, intent: "incomplete_spec", clarification_questions: ["Çap kaç mm?"]
- "200mm strok" → stroke: 200, intent: "incomplete_spec"
- "strok 200" → stroke: 200, intent: "incomplete_spec"
- "100 stroklu silindir" → stroke: 100, intent: "incomplete_spec", clarification_questions: ["Çap kaç mm?"]

SILINDIR SPEC KURALLARI:
- Sayı + "strok" (tüm ekleriyle: strok, stroklu, stroka, strokun, strokta) → stroke değeri
- Sayı + "çap" (tüm ekleriyle: çap, çaplı, çapa, çapın, çapta) → diameter değeri
- Sayı + "lük/lı/lu" + "silindir" → diameter değeri

URUN KODU SCENARIOS:
- "17P1040 arıyorum" → product_code: "17P1040", intent: "product_code_search"
- "stoklara bi baksana 17P1040 var mı" → product_code: "17P1040", intent: "product_code_search"
- Ürün kodu format: Harfler+rakamlar (17P1040, A123B, XY5678 vb.)

OZEL OZELLIK SCENARIOS:
- "manyetik özelliği olan silindiler" → special_properties: ["manyetik"], intent: "product_search"
- "amortisörlü silindir" → special_properties: ["amortisör"], intent: "product_search"
- "çift etkili silindir" → special_properties: ["çift etkili"], intent: "product_search"

BAGLANTI BOYUTU SCENARIOS:
- "1/4 bağlantı" → connection_size: "1/4"
- "1/8 NPT" → connection_size: "1/8"
- "1/2 inç" → connection_size: "1/2"

TEMEL KURALLAR:
- Tam spec (çap+strok) → intent: "spec_query"
- Eksik spec → intent: "incomplete_spec" + clarification_questions
- Ürün kodu → intent: "product_code_search" + product_code
- Özel özellik → intent: "product_search" + special_properties
- Marka isimleri: ANS, ANSY, IS, KHS, NHS, PISCO vs.
- VALF KURALI: Valf tipi belirtilmişse (5/2, 3/2, 5/3, 4/2 vb.) → HER ZAMAN bağlantı boyutu sor
- YAZIM HATASI DÜZELTME: Yazım hatalarını otomatik düzelt (örn: "nerler" → "neler", "sartlandirici" → "şartlandırıcı")

DOGRU ORNEKLER:
- "100mm çap, 200mm strok" → diameter: 100, stroke: 200, intent: "spec_query"
- "ANS 50" → brand_preference: "ANS", diameter: 50, intent: "incomplete_spec"
- "valf 5/2 var mı?" → features: ["5/2"], intent: "incomplete_spec", clarification_questions: ["Bağlantı boyutu?"]
- "Merhaba 5/2 valf arıyorum" → features: ["5/2"], intent: "incomplete_spec", clarification_questions: ["Bağlantı boyutu: 1/4, 1/8, 1/2?"]
- "17P1040 arıyorum" → product_code: "17P1040", intent: "product_code_search"
- "manyetik silindir" → special_properties: ["manyetik"], intent: "product_search"  
- "100 çap silindir" → diameter: 100, intent: "incomplete_spec", clarification_questions: ["Strok uzunluğu?"]
- "şartlandırıcılara nerler var" → corrected_query: "şartlandırıcılara neler var", intent: "product_search" (şartlandırıcı ürün listesi)"""

        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        # Add conversation history if available
        if conversation_history:
            for i, prev_msg in enumerate(conversation_history[-3:]):  # Last 3 messages
                messages.append({"role": "user", "content": f"Önceki mesaj {i+1}: {prev_msg}"})
        
        # Add current context if available
        if context:
            context_msg = f"Mevcut context: {json.dumps(context, ensure_ascii=False)}"
            messages.append({"role": "assistant", "content": context_msg})
        
        # Add previous AI response for context awareness
        if previous_ai_response:
            messages.append({"role": "assistant", "content": f"Son AI cevabım: {previous_ai_response}"})
            
        # Add current user message
        messages.append({"role": "user", "content": f"Yeni mesaj: {user_message}"})
        
        try:
            response = self._make_request(messages, temperature=0.2)
            
            # Parse JSON response
            ai_data = json.loads(response)
            
            # Ensure all new fields are handled
            extracted_specs = ai_data.get("extracted_specs", {})
            if "product_code" not in extracted_specs:
                extracted_specs["product_code"] = None
            if "connection_size" not in extracted_specs:
                extracted_specs["connection_size"] = None  
            if "special_properties" not in extracted_specs:
                extracted_specs["special_properties"] = []
            if "corrected_query" not in extracted_specs:
                extracted_specs["corrected_query"] = None
            
            return AIResponse(
                intent=ai_data.get("intent", "general_question"),
                confidence=ai_data.get("confidence", 0.5),
                extracted_specs=extracted_specs,
                suggested_response=ai_data.get("suggested_response", ""),
                requires_clarification=ai_data.get("requires_clarification", False),
                clarification_questions=ai_data.get("clarification_questions", []),
                sub_intent=ai_data.get("sub_intent", "unknown"),
                action=ai_data.get("action", "clarify_intent")
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
                clarification_questions=["Hangi ürün hakkında bilgi istiyorsunuz?"],
                sub_intent="unknown",
                action="clarify_intent"
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
    
    def extract_quantity(self, quantity_text: str, context: Dict = None) -> Dict:
        """Doğal dil ile miktar çıkarımı"""
        
        system_prompt = """Kullanıcının verdiği metinden kaç adet ürün istediğini çıkar.

Örnekler:
- "5 tane" → 5
- "10 adet istiyorum" → 10  
- "bundan 3 adet" → 3
- "7 parça lazım" → 7
- "15" → 15
- "on beş tane" → 15
- "iki adet sipariş" → 2

JSON formatında sadece sayıyı döndür:
{"extracted_quantity": sayı}

Eğer sayı bulamazsan:
{"extracted_quantity": null}"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Metin: '{quantity_text}'"}
        ]
        
        if context and context.get('product_name'):
            messages.append({
                "role": "assistant", 
                "content": f"Ürün: {context['product_name']}"
            })
        
        try:
            response = self._make_request(messages, temperature=0.1)
            
            # JSON parse et
            import json
            result = json.loads(response.strip())
            return result
            
        except Exception as e:
            logger.error(f"Quantity extraction failed: {e}")
            # Fallback: basit regex
            import re
            numbers = re.findall(r'\d+', quantity_text)
            if numbers:
                return {"extracted_quantity": int(numbers[0])}
            else:
                return {"extracted_quantity": None}
    
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
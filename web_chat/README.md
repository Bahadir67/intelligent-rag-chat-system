# 🤖 B2B Silindir AI Chat - Web Interface

Akıcı, doğal konuşma ile silindir arama ve sipariş sistemi.

## 🚀 Hızlı Başlangıç

```bash
# Gerekli paketleri yükle
pip install -r requirements.txt

# Web uygulamasını başlat
python app.py
```

**Tarayıcıda aç:** http://localhost:5000

## 💬 Örnek Konuşmalar

```
👤 Sen: Merhaba naber?
🤖 AI: Merhaba! İyiyim, teşekkürler. Size nasıl yardımcı olabilirim?

👤 Sen: Silindir bakıyorum
🤖 AI: Harika! Hangi çap arıyorsunuz?

👤 Sen: 100 çap lazım
🤖 AI: 100mm çaplı silindirden 95 adet var. Strok bilgisini verirsen bakayım.

👤 Sen: 400 mm strok ve magnetli
🤖 AI: 100mm x 400mm magnetik silindir var! IS 100*400 MANYETİK, 1 adet stokta. Fiyat 280 TL. Kaç adet lazım?

👤 Sen: 2 adet istiyorum
🤖 AI: Tamam! 2 adet sipariş, toplam 560 TL. Onaylıyor musun?

👤 Sen: Evet
🤖 AI: ✅ Sipariş kaydedildi! Sipariş No: 123. Başka bir şey lazım mı?
```

## ⚡ Özellikler

- **Doğal Konuşma**: "Merhaba naber" gibi günlük konuşma
- **Akıllı Arama**: Semantic search + SQL hybrid
- **Progressive Inquiry**: Eksik bilgileri akıllıca sorar
- **Gerçek Zamanlı**: Typing indicator, smooth animations
- **Memory**: Konuşma geçmişini hatırlar
- **Sipariş Sistemi**: Tam sipariş akışı
- **Responsive**: Mobil uyumlu

## 🛠️ Teknik Detaylar

- **Backend**: Flask + PostgreSQL + ChromaDB
- **Frontend**: Vanilla JS + Modern CSS
- **AI**: Natural language processing
- **Memory**: Persistent conversation context

## 📱 Kullanım

1. Web uygulamasını başlat
2. Tarayıcıda `localhost:5000` aç
3. Doğal dille konuş:
   - "Merhaba"
   - "Silindir arıyorum"
   - "100 çap 400 strok magnetli"
   - "3 adet istiyorum"
   - "Onayla"

## 🔧 Konfigürasyon

`app.py` içinde database bağlantısını düzenle:
```python
db_connection = "postgresql://postgres:PASSWORD@localhost:5432/DB_NAME"
```
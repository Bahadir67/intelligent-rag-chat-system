# B2B RAG Sales Assistant System

B2B satış süreçleri için geliştirilmiş akıllı RAG sistemi. Ürün keşfi, derinlemesine müşteri sorguları ve otomatik sipariş oluşturma ile desteklenmiş AI satış danışmanı.

## Özellikler

### ✅ Tamamlanan Özellikler
- **B2B Product Discovery**: Akıllı ürün keşif ve öneri sistemi
- **Multi-turn Conversation**: Bağlamsal konuşma yönetimi
- **Customer Profiling**: Müşteri segmentasyonu ve analiz
- **Order Management**: Otomatik sipariş oluşturma ve onay süreci
- **PostgreSQL Integration**: Güvenli veri yönetimi ve raporlama
- **Web Interface**: Flask tabanlı kullanıcı dostu arayüz
- **CLI Tools**: Sistem yönetimi ve test araçları

### 🔄 Devam Eden Özellikler
- **OpenRouter AI Integration**: Regex mantığından doğal dil işlemeye geçiş
- **Advanced Analytics**: Satış performansı ve trend analizi

## Teknik Altyapı

### Veritabanı
- **PostgreSQL**: Ana veri deposu (müşteriler, ürünler, siparişler)
- **ChromaDB**: Vektör tabanlı ürün arama (opsiyonel)
- **Memory-keeper MCP**: Conversation context yönetimi

### API Entegrasyonları
- **OpenRouter API**: GPT-3.5-turbo / Claude-3.5-sonnet
- **psycopg2**: PostgreSQL bağlantı yönetimi
- **Flask**: Web API sunucusu

### Dosya Yapısı

#### Ana Sistem Dosyaları
- `rag_system.py` - B2B RAG çekirdek sistemi
- `conversation_system.py` - Konuşma durumu yönetimi  
- `intelligent_conversation.py` - AI destekli satış danışmanlığı
- `progressive_inquiry_system.py` - Aşamalı müşteri profilleme
- `chat_system.py` - Unified conversation interface

#### CLI Arayüzleri
- `interactive_cli.py` - Etkileşimli CLI
- `direct_cli.py` - Direkt CLI
- `simple_cli.py` - Basit CLI

#### Web Arayüzü
- `web_chat/app.py` - Ana Flask uygulaması
- `web_chat/templates/chat.html` - Web arayüz şablonu

#### Test Dosyaları
- `test_conversation.py` - Konuşma testleri
- `performance_benchmark.py` - Performans testleri
- `complex_search_tests.py` - Karmaşık arama testleri

#### Veritabanı
- `db_schema.sql` - PostgreSQL B2B şeması
- `add_orders_table.sql` - Sipariş yönetimi tablları
- `conversation_orders.sql` - Conversation-Order mapping

#### Veri Dosyaları
- CSV dosyaları: B2B müşteri ve ürün verileri
- `RAG_SYSTEM_REPORT.md` - Sistem analiz raporu

## Kurulum ve Çalıştırma

### Gereksinimler
```bash
pip install flask psycopg2 chromadb requests openai python-dotenv
```

### PostgreSQL Kurulumu
```sql
-- Veritabanı oluştur
CREATE DATABASE b2b_rag_system;

-- Şemayı yükle
psql -d b2b_rag_system -f db_schema.sql
```

### Web Arayüzü
```bash
cd web_chat
python app.py
```

### CLI Arayüzü
```bash
python interactive_cli.py
```

## Sistem Mimarisi

### B2B Satış Süreci
1. **Müşteri Profilleme** → Firma bilgileri ve ihtiyaç analizi
2. **Ürün Keşfi** → PostgreSQL + RAG tabanlı ürün önerisi 
3. **Derinlemesine Sorgular** → AI destekli ihtiyaç belirleme
4. **Sipariş Oluşturma** → Otomatik fiyatlandırma ve onay
5. **Takip Sistemi** → Süreç yönetimi ve raporlama

### Gelişim Aşamaları
1. ✅ PostgreSQL B2B şeması ve veri modeli
2. ✅ Multi-turn conversation engine
3. ✅ Customer profiling ve segmentasyon
4. ✅ Product discovery RAG sistemi
5. ✅ Order workflow automation
6. ✅ Memory-keeper context yönetimi
7. 🔄 OpenRouter AI integration (regex → doğal dil)

## B2B Kullanım Senaryoları

### Satış Süreçleri
- **Lead Qualification**: AI destekli potansiyel müşteri değerlendirmesi
- **Product Recommendation**: Müşteri ihtiyaçlarına göre akıllı ürün önerisi
- **Quote Generation**: Otomatik fiyat teklifi ve sipariş oluşturma
- **Sales Analytics**: Satış performansı ve trend analizi

### Müşteri Deneyimi  
- **24/7 Sales Support**: Kesintisiz satış danışmanlığı hizmeti
- **Technical Consultation**: Ürün spesifikasyonu ve teknik destek
- **Order Tracking**: Sipariş durumu takibi ve güncellemeler
- **Account Management**: Müşteri hesap yönetimi ve geçmiş analizi
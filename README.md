# Intelligent Conversation RAG System

RAG (Retrieval-Augmented Generation) tabanlı akıllı soru-cevap sistemi. Multi-turn conversation engine, context memory sistemi ve OpenRouter API entegrasyonu ile güçlendirilmiş gelişmiş konuşma sistemi.

## Özellikler

### ✅ Tamamlanan Özellikler
- **Multi-turn Conversation Engine**: Sürekli konuşma takibi
- **Context Memory Sistemi**: Memory-keeper MCP entegrasyonu
- **RAG Tabanlı Arama**: ChromaDB ile vektör arama
- **Sipariş Workflow'u**: Otomatik sipariş oluşturma ve kayıt
- **Web Arayüzü**: Flask tabanlı web chat arayüzü
- **CLI Arayüzü**: Komut satırı etkileşimi

### 🔄 Devam Eden Özellikler
- **OpenRouter API Entegrasyonu**: Regex yerine gerçek AI kullanımı

## Teknik Altyapı

### Veritabanı
- **SQLite**: Ana veritabanı yönetimi
- **ChromaDB**: Vektör tabanlı arama ve embedding
- **Memory-keeper MCP**: Context takibi ve oturum yönetimi

### API Entegrasyonları
- **OpenRouter API**: Claude-3.5-sonnet modeli
- **Embedding API**: all-MiniLM-L6-v2 modeli

### Dosya Yapısı

#### Ana Sistem Dosyaları
- `chat_system.py` - Ana chat sistemi
- `conversation_system.py` - Konuşma yönetimi
- `intelligent_conversation.py` - AI destekli konuşma
- `rag_system.py` - RAG tabanlı arama sistemi
- `progressive_inquiry_system.py` - Aşamalı sorgulama

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
- `db_schema.sql` - Ana veritabanı şeması
- `add_orders_table.sql` - Sipariş tablosu eklentisi
- `conversation_orders.sql` - Konuşma-sipariş ilişkisi

#### Veri Dosyaları
- CSV dosyaları: Bakım verisi importu
- `RAG_SYSTEM_REPORT.md` - Sistem raporu

## Kurulum ve Çalıştırma

### Gereksinimler
```bash
pip install flask sqlite3 chromadb requests openai numpy pandas
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

## Gelişim Süreci

Proje 6 ana aşamada tamamlanmıştır:
1. ✅ Konuşma ortamı kurulumu - context takibi ile
2. ✅ Multi-turn conversation engine
3. ✅ Context memory sistemi
4. ✅ Sipariş oluşturma workflow'u entegrasyonu
5. ✅ Sipariş onay ve kayıt sistemi
6. ✅ Memory-keeper MCP entegrasyonu
7. 🔄 OpenRouter API entegrasyonu (devam ediyor)

## Kullanım Alanları

- Müşteri hizmetleri chat botları
- Teknik destek sistemleri
- Bilgi bankası sorgulama
- Akıllı asistan uygulamaları
- Dokümantasyon arama sistemleri
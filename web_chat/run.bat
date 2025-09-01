@echo off
echo 🚀 B2B Chat Web Interface başlatılıyor...
echo.
echo 📦 Gerekli paketler kontrol ediliyor...
pip install -r requirements.txt

echo.
echo 🌐 Web sunucusu başlatılıyor...
echo 📱 Tarayıcıda aç: http://localhost:5000
echo.

python app.py

pause
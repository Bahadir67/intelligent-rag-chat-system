@echo off
echo 🚀 B2B Chat Web Interface (Basit Versiyon) başlatılıyor...
echo.
echo 📦 Sadece Flask yükleniyor...
pip install Flask==2.3.3

echo.
echo 🌐 Web sunucusu başlatılıyor...
echo 📱 Tarayıcıda aç: http://localhost:5000
echo 💡 Mock data kullanılıyor - veritabanı gerekmez!
echo.

python app_simple.py

pause
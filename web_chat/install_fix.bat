@echo off
echo 🔧 Windows psycopg2 sorunu düzeltiliyor...
echo.

echo 1. Visual Studio Build Tools kontrol ediliyor...
pip install --upgrade pip setuptools wheel

echo.
echo 2. psycopg2 alternatif kurulum...
pip install psycopg2-binary --no-cache-dir
if errorlevel 1 (
    echo psycopg2-binary başarısız, alternatif deniyor...
    pip install psycopg2
)

echo.
echo 3. Diğer paketler kuruluyor...
pip install Flask==2.3.3
pip install chromadb==0.4.15

echo.
echo ✅ Kurulum tamamlandı!
pause
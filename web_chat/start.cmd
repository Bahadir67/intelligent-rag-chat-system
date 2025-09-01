@echo off
cd /d "%~dp0"
echo 🚀 B2B Chat başlatılıyor...
echo.
py app_simple.py
if errorlevel 1 (
    echo Python bulunamadı, alternatif deniyor...
    python3 app_simple.py
    if errorlevel 1 (
        echo python komutu deniyor...
        python app_simple.py
    )
)
pause
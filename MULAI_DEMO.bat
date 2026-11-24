@echo off
cd /d "%~dp0"
title SAB - layar demo

echo.
echo  [1/3] Menyalakan server demo (FastAPI, port 8899) ...
start "" /min cmd /c "python app.py"
timeout /t 5 /nobreak >nul

echo  [2/3] Memeriksa mesin sebelum layar dibagikan ...
python pra_siaran.py

echo.
echo  [3/3] Membuka layar demo di browser ...
start "" "http://127.0.0.1:8899/siaran"

echo.
echo  Tekan F11 untuk layar penuh, lalu bagikan JENDELA INI saja.
echo  Urutan klik:  1 kirim  -  2 coba sendiri  -  3 daftar  -  4 mesin  -  5 apa yang belum  -  6 enam poin
echo.
echo  Jendela ini boleh ditutup setelah presentasi terbuka.
timeout /t 12 /nobreak >nul

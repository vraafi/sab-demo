@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

rem ---------------------------------------------------------------------------
rem  Menyalakan demo di alamat publik, dengan pengaman.
rem
rem  Yang berubah dibanding MULAI_DEMO.bat:
rem    * port 8901, bukan 8899  -> demo lokal Anda tetap jalan seperti biasa
rem    * SAB_TANPA_KIRIM=1      -> pesan dibaca & dibalas, tetapi tidak dikirim
rem    * SAB_TOKEN              -> tanpa tautan bertoken, tidak ada yang terbuka
rem    * cloudflared            -> alamat https yang bisa dibuka Tico
rem
rem  Tautan trycloudflare hidup selama jendela Cloudflare ini terbuka.
rem  Kalau ditutup, alamatnya mati dan tidak bisa dipakai lagi.
rem ---------------------------------------------------------------------------

if not exist "tmp" mkdir "tmp"

set "SAB_TOKEN="
if exist "tmp\token_publik.txt" set /p SAB_TOKEN=<"tmp\token_publik.txt"
if not defined SAB_TOKEN (
  for /f %%i in ('python -c "import secrets;print(secrets.token_urlsafe(18))"') do set "SAB_TOKEN=%%i"
  >"tmp\token_publik.txt" echo !SAB_TOKEN!
)

set SAB_TANPA_KIRIM=1

echo.
echo   Token demo : !SAB_TOKEN!
echo.
echo   [1/2] menyalakan mesin di 127.0.0.1:8901 ...
start "SAB publik 8901" cmd /k python -m uvicorn app:app --host 127.0.0.1 --port 8901 --log-level warning

timeout /t 7 /nobreak >nul

echo   [2/2] membuka terowongan Cloudflare ...
start "Cloudflare tunnel" cmd /k "C:\Users\user\cloudflared.exe" tunnel --url http://127.0.0.1:8901 --no-autoupdate

echo.
echo   ------------------------------------------------------------------
echo    Di jendela "Cloudflare tunnel", cari baris:
echo        https://xxxx-xxxx-xxxx.trycloudflare.com
echo.
echo    Tautan yang dibagikan ke Tico adalah alamat itu ditambah:
echo        /pintu?k=!SAB_TOKEN!
echo.
echo    Contoh lengkap:
echo        https://xxxx-xxxx-xxxx.trycloudflare.com/pintu?k=!SAB_TOKEN!
echo   ------------------------------------------------------------------
echo.
pause

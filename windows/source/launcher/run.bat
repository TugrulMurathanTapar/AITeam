@echo off
setlocal EnableExtensions
chcp 65001 >nul 2>&1

for %%I in ("%~dp0..") do set "PROJECT_ROOT=%%~fI"
set "SETUP_SCRIPT=%PROJECT_ROOT%\install_win.ps1"

if not exist "%SETUP_SCRIPT%" (
    echo [HATA] Kurulum betigi bulunamadi: "%SETUP_SCRIPT%"
    pause
    exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SETUP_SCRIPT%" -ProjectRoot "%PROJECT_ROOT%" -RunApplication
if errorlevel 1 (
    echo.
    echo [HATA] Kurulum veya uygulama baslatma basarisiz oldu.
    pause
    exit /b 1
)

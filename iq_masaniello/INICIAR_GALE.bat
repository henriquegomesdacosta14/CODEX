@echo off
title IQBOT Gale + Claude Vision Analitico
cd /d "%~dp0"

echo.
echo  =========================================
echo   IQBOT Gale + Claude Vision Analitico
echo  =========================================
echo.

:: Mata processos anteriores
taskkill /f /im python.exe >nul 2>&1
timeout /t 2 /nobreak >nul

:: Instala dependencias (so na primeira vez ou se faltar)
echo  Verificando dependencias...
pip install websockets nest_asyncio matplotlib pillow anthropic --quiet --no-warn-script-location >nul 2>&1
pip install "git+https://github.com/iqoptionapi/iqoptionapi.git" --quiet --no-warn-script-location >nul 2>&1
echo  Dependencias OK!
echo.

:: Inicia o Watchdog (que gerencia o bot_gale)
start "IQBOT-Watchdog-Gale" cmd /k "python watchdog_gale.py"

:: Aguarda bot subir
timeout /t 6 /nobreak >nul

:: Inicia servidor HTTP para o dashboard
start "IQBOT-HTTP" cmd /k "python -m http.server 3000"

:: Aguarda servidor
timeout /t 3 /nobreak >nul

:: Abre dashboard Gale no navegador
start http://localhost:3000/dashboard_gale.html

echo.
echo  IQBOT Gale + Claude Vision iniciado!
echo.
echo  Dashboard: http://localhost:3000/dashboard_gale.html
echo  WebSocket:  ws://localhost:8765
echo.
echo  Watchdog ativo - bot reinicia automaticamente se travar
echo  Nao feche as janelas do CMD
echo.
pause

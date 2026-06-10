@echo off
title IQBOT Claude M1
cd /d "%~dp0"

echo.
echo  =========================================
echo   IQBOT Claude M1 + EMA + Fractal
echo  =========================================
echo.

taskkill /f /im python.exe >nul 2>&1
timeout /t 2 /nobreak >nul

echo  Verificando dependencias...
pip install websockets nest_asyncio matplotlib pillow --quiet --no-warn-script-location >nul 2>&1
pip install "git+https://github.com/iqoptionapi/iqoptionapi.git" --quiet --no-warn-script-location >nul 2>&1
echo  Dependencias OK!
echo.

start "IQBOT-Claude" cmd /k "python iqbot-claude-m1.py"
timeout /t 6 /nobreak >nul

start "IQBOT-HTTP" cmd /k "python -m http.server 3000"
timeout /t 3 /nobreak >nul

start http://localhost:3000/iqbot-active-dashboard.html

echo.
echo  IQBOT Claude M1 iniciado!
echo  Dashboard PC:     http://localhost:3000/iqbot-active-dashboard.html
echo  Dashboard Mobile: http://localhost:3000/iqbot-active-dashboard-mobile.html
echo  WebSocket:        ws://localhost:8775
echo.
echo  Nao feche as janelas do CMD
echo.
pause

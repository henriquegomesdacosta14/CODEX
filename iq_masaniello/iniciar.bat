@echo off
title Masaniello Bot
cd /d "%~dp0"

echo.
echo  ============================================
echo   MASANIELLO BOT - Iniciando...
echo  ============================================
echo.

:: Verifica Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERRO] Python nao encontrado!
    echo  Baixe em: https://www.python.org/downloads/
    echo  Marque "Add Python to PATH" durante a instalacao
    pause
    exit /b 1
)

:: Instala dependencias se necessario
echo  [1/3] Verificando dependencias...
pip install iqoptionapi pandas numpy flask flask-cors anthropic --quiet --disable-pip-version-check
echo  OK

:: Inicia o bot em janela separada
echo  [2/3] Iniciando bot...
start "Masaniello BOT" cmd /k "cd /d "%~dp0" && python bot_confluencia.py"

:: Aguarda 2 segundos
timeout /t 2 /nobreak >nul

:: Inicia o servidor do painel
echo  [3/3] Iniciando painel web...
start "Masaniello PAINEL" cmd /k "cd /d "%~dp0" && python servidor_masaniello.py"

:: Aguarda o servidor subir
echo.
echo  Aguardando servidor iniciar...
timeout /t 3 /nobreak >nul

:: Abre o painel no navegador
echo  Abrindo painel...
start http://localhost:3000

echo.
echo  ============================================
echo   Bot rodando!
echo   Painel: http://localhost:3000
echo
echo   Para parar: feche as janelas "Masaniello BOT"
echo               e "Masaniello PAINEL"
echo  ============================================
echo.
pause

@echo off
echo Deteniendo backend...
taskkill /F /IM python.exe 2>nul
timeout /t 2 /nobreak >nul
echo Iniciando backend...
cd backend
start python main.py
echo Backend reiniciado

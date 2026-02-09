# Docker Quick Start Script (Optimizado)
# Uso: .\docker-start-optimized.bat

@echo off
echo 🚀 Iniciando Auditor GEO (Optimizado)...

REM Verificar si Docker está corriendo
docker info >nul 2>&1
if errorlevel 1 (
    echo ❌ Error: Docker no está corriendo
    pause
    exit /b 1
)

echo 📦 Construyendo imágenes con cache...
docker-compose build --parallel

echo 🗃️ Iniciando servicios...
docker-compose up -d

echo ⏳ Esperando que los servicios estén listos...
timeout /t 10 /nobreak >nul

echo 🔍 Verificando estado...
docker-compose ps

echo ✅ Servicios iniciados!
echo 🌐 Frontend: http://localhost:3000
echo 🔧 Backend: http://localhost:8000
echo 📚 Docs API: http://localhost:8000/docs

echo.
echo 💡 Comandos útiles:
echo   - Ver logs: docker-compose logs -f
echo   - Detener: docker-compose down
echo   - Reiniciar: docker-compose restart
echo.
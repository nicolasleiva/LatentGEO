# Docker Clean Build Script (Ultra Limpio)
# Uso: .\docker-clean-build.bat

@echo off
echo 🧹 Limpieza ultra profunda de Docker...

REM Detener todos los contenedores relacionados
docker-compose down -v --remove-orphans 2>nul

REM Remover imágenes específicas del proyecto
docker images | findstr "auditor_geo" | for /f "tokens=3" %%i in ('docker images ^| findstr "auditor_geo"') do docker rmi %%i 2>nul

REM Limpiar build cache
docker builder prune -f

REM Limpiar sistema Docker
docker system prune -f

echo 📦 Construyendo desde cero (sin cache)...
docker-compose build --no-cache --parallel --progress=plain

echo 🗃️ Iniciando servicios...
docker-compose up -d

echo ⏳ Esperando servicios...
timeout /t 20 /nobreak >nul

echo ✅ Build ultra limpio completado!
echo 🌐 Frontend: http://localhost:3000
echo 🔧 Backend: http://localhost:8000
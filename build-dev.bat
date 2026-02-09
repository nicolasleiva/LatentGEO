@echo off
REM Script para builds rápidos con Docker BuildKit (Windows)
REM Uso: build-dev.bat [servicio]

echo 🚀 Auditor GEO - Development Build Script
echo.

REM Activar BuildKit para builds paralelos y cache export
set DOCKER_BUILDKIT=1
set COMPOSE_DOCKER_CLI_BUILD=1
set BUILDKIT_PROGRESS=plain

REM Build específico o todos
if "%~1"=="" (
    echo 📦 Construyendo todos los servicios...
    docker compose -f docker-compose.dev.yml build --parallel
    echo.
    echo 🎉 Todos los servicios construidos exitosamente!
    echo.
    echo Para iniciar los servicios:
    echo   docker compose -f docker-compose.dev.yml up
) else (
    echo 📦 Construyendo servicio: %1
    docker compose -f docker-compose.dev.yml build %1
    echo.
    echo 🎉 Servicio %1 construido exitosamente!
)

pause

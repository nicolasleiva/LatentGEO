@echo off
REM Script mejorado para iniciar Docker
echo ========================================
echo   GEO Audit Platform - Docker Start
echo ========================================
echo.

REM Verificar Docker
where docker >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Docker no esta instalado o no esta en PATH
    pause
    exit /b 1
)

REM Verificar .env
if not exist ".env" (
    echo [ADVERTENCIA] Archivo .env no encontrado
    echo Creando desde .env.example...
    if exist ".env.example" (
        copy .env.example .env
    ) else (
        echo GEMINI_API_KEY= > .env
        echo GOOGLE_API_KEY= >> .env
        echo CSE_ID= >> .env
    )
    echo.
    echo Por favor edita .env con tus API keys antes de continuar
    pause
)

echo [1] Deteniendo contenedores anteriores...
docker compose down

echo.
echo [2] Construyendo imagenes...
docker compose build

echo.
echo [3] Iniciando servicios...
docker compose up -d

echo.
echo [4] Esperando que los servicios esten listos...
timeout /t 10 /nobreak >nul

echo.
echo ========================================
echo   Servicios iniciados:
echo   - Frontend: http://localhost:3000
echo   - Backend:  http://localhost:8000
echo   - API Docs: http://localhost:8000/docs
echo ========================================
echo.
echo Para ver logs: docker compose logs -f
echo Para detener:  docker compose down
echo.
pause

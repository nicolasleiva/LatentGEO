@echo off
REM Script de inicio rápido para Windows
REM GEO Audit Platform

echo.
echo ========================================
echo   GEO Audit Platform - Quick Start
echo ========================================
echo.

REM Verificar si Docker está disponible
where docker >nul 2>nul
if %errorlevel% equ 0 (
    echo [1] Docker encontrado - Iniciando con Docker Compose...
    echo.
    cd /d "%~dp0"
    docker-compose up --build
) else (
    echo [2] Docker no encontrado - Iniciando modo local Python...
    echo.
    
    REM Crear venv si no existe
    if not exist "backend\venv" (
        echo Creando virtual environment...
        cd backend
        python -m venv venv
        call venv\Scripts\activate.bat
        echo Instalando dependencias...
        pip install -r requirements.txt
    ) else (
        cd backend
        call venv\Scripts\activate.bat
    )
    
    REM Verificar .env
    if not exist ".env" (
        echo.
        echo [ADVERTENCIA] Archivo .env no encontrado
        echo Creando desde .env.example...
        copy .env.example .env
        echo Por favor edita .env con tus API keys
        pause
    )
    
    echo.
    echo Iniciando servidor FastAPI...
    python main.py
)

echo.
echo Presiona cualquier tecla para salir...
pause >nul

#!/bin/bash
# Script de inicio rápido para Linux/Mac
# GEO Audit Platform

echo ""
echo "========================================"
echo "  GEO Audit Platform - Quick Start"
echo "========================================"
echo ""

# Verificar si Docker está disponible
if command -v docker &> /dev/null; then
    echo "[1] Docker encontrado - Iniciando con Docker Compose..."
    echo ""
    cd "$(dirname "$0")"
    docker-compose up --build
else
    echo "[2] Docker no encontrado - Iniciando modo local Python..."
    echo ""
    
    # Crear venv si no existe
    if [ ! -d "backend/venv" ]; then
        echo "Creando virtual environment..."
        cd backend
        python3 -m venv venv
        source venv/bin/activate
        echo "Instalando dependencias..."
        pip install -r requirements.txt
    else
        cd backend
        source venv/bin/activate
    fi
    
    # Verificar .env
    if [ ! -f ".env" ]; then
        echo ""
        echo "[ADVERTENCIA] Archivo .env no encontrado"
        echo "Creando desde .env.example..."
        cp .env.example .env
        echo "Por favor edita .env con tus API keys"
        read -p "Presiona Enter para continuar..."
    fi
    
    echo ""
    echo "Iniciando servidor FastAPI..."
    python main.py
fi

echo ""
read -p "Presiona Enter para salir..."

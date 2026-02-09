#!/bin/bash

# Docker Quick Start Script (Optimizado) - Linux/Mac
# Uso: ./docker-start-optimized.sh

echo "🚀 Iniciando Auditor GEO (Optimizado)..."

# Verificar si Docker está corriendo
if ! docker info >/dev/null 2>&1; then
    echo "❌ Error: Docker no está corriendo"
    exit 1
fi

echo "📦 Construyendo imágenes con cache y parallel builds..."
docker-compose build --parallel

echo "🗃️ Iniciando servicios..."
docker-compose up -d

echo "⏳ Esperando que los servicios estén listos..."
sleep 10

echo "🔍 Verificando estado..."
docker-compose ps

echo "✅ Servicios iniciados!"
echo "🌐 Frontend: http://localhost:3000"
echo "🔧 Backend: http://localhost:8000"
echo "📚 Docs API: http://localhost:8000/docs"

echo ""
echo "💡 Comandos útiles:"
echo "  - Ver logs: docker-compose logs -f"
echo "  - Detener: docker-compose down"
echo "  - Reiniciar: docker-compose restart"
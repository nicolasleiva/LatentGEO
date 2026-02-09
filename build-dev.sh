#!/bin/bash
# Script para builds rápidos con Docker BuildKit
# Uso: ./build-dev.sh [servicio]

set -e

# Colores para output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Auditor GEO - Development Build Script${NC}"
echo ""

# Activar BuildKit para builds paralelos y cache export
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1
export BUILDKIT_PROGRESS=plain

# Función para mostrar tiempo
show_time() {
    echo -e "${GREEN}✅ Completado en $(($1 / 60)) minutos y $(($1 % 60)) segundos${NC}"
}

# Build específico o todos
if [ -z "$1" ]; then
    echo -e "${YELLOW}📦 Construyendo todos los servicios...${NC}"
    START_TIME=$SECONDS
    
    docker compose -f docker-compose.dev.yml build --parallel
    
    show_time $((SECONDS - START_TIME))
    echo ""
    echo -e "${GREEN}🎉 Todos los servicios construidos exitosamente!${NC}"
    echo ""
    echo "Para iniciar los servicios:"
    echo -e "${BLUE}  docker compose -f docker-compose.dev.yml up${NC}"
else
    echo -e "${YELLOW}📦 Construyendo servicio: $1${NC}"
    START_TIME=$SECONDS
    
    docker compose -f docker-compose.dev.yml build "$1"
    
    show_time $((SECONDS - START_TIME))
    echo ""
    echo -e "${GREEN}🎉 Servicio $1 construido exitosamente!${NC}"
fi

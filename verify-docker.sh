#!/bin/bash
# Script de verificación para Docker Frontend
# Ejecutar con: bash verify-docker.sh

echo "=========================================="
echo "Verificación de Configuración Docker"
echo "=========================================="
echo ""

# Colores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Verificar Docker
echo -e "${YELLOW}1. Verificando Docker...${NC}"
if command -v docker &> /dev/null; then
    echo -e "${GREEN}✓ Docker está instalado${NC}"
    docker --version
else
    echo -e "${RED}✗ Docker no está instalado${NC}"
    exit 1
fi

echo ""

# Verificar archivos necesarios
echo -e "${YELLOW}2. Verificando archivos de configuración...${NC}"
files=(
    "Dockerfile.frontend"
    "docker-compose.yml"
    "docker-compose.dev.yml"
    "frontend/next.config.mjs"
    "frontend/package.json"
)

all_present=true
for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✓ $file${NC}"
    else
        echo -e "${RED}✗ $file (falta)${NC}"
        all_present=false
    fi
done

if [ "$all_present" = false ]; then
    echo -e "${RED}Faltan archivos necesarios${NC}"
    exit 1
fi

echo ""

# Verificar output standalone en next.config.mjs
echo -e "${YELLOW}3. Verificando configuración Next.js...${NC}"
if grep -q "output: 'standalone'" frontend/next.config.mjs; then
    echo -e "${GREEN}✓ Next.js configurado con 'output: standalone'${NC}"
else
    echo -e "${RED}✗ Falta 'output: standalone' en next.config.mjs${NC}"
fi

echo ""

# Verificar que docker-compose.yml no tenga volúmenes conflictivos
echo -e "${YELLOW}4. Verificando docker-compose.yml (producción)...${NC}"
if grep -A 20 "frontend:" docker-compose.yml | grep -q "./frontend:/app"; then
    echo -e "${RED}✗ docker-compose.yml tiene volumen conflictivo (./frontend:/app)${NC}"
    echo -e "${RED}   Esto sobrescribirá el build en producción${NC}"
else
    echo -e "${GREEN}✓ docker-compose.yml correcto para producción${NC}"
    echo -e "${GREEN}  No hay volúmenes de código que interfieran${NC}"
fi

echo ""

# Verificar docker-compose.dev.yml
echo -e "${YELLOW}5. Verificando docker-compose.dev.yml (desarrollo)...${NC}"
if grep -q "pnpm run dev" docker-compose.dev.yml; then
    echo -e "${GREEN}✓ Modo desarrollo configurado correctamente${NC}"
    echo -e "${GREEN}  Usa 'pnpm run dev' para hot reload${NC}"
else
    echo -e "${RED}✗ Modo desarrollo no configurado correctamente${NC}"
fi

echo ""

# Resumen
echo "=========================================="
echo -e "${GREEN}Verificación completada${NC}"
echo "=========================================="
echo ""
echo "Para levantar los servicios:"
echo ""
echo "  PRODUCCIÓN (usar imagen construida):"
echo "    docker compose up --build"
echo ""
echo "  DESARROLLO (con hot reload):"
echo "    docker compose -f docker-compose.dev.yml up"
echo ""
echo "=========================================="

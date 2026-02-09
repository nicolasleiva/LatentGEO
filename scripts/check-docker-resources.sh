#!/bin/bash
# =============================================================================
# Script de diagnóstico de recursos Docker
# Verifica configuración de memoria y recursos
# =============================================================================

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

echo "================================================================"
echo "  DIAGNÓSTICO DE RECURSOS DOCKER"
echo "================================================================"
echo ""

# Verificar Docker está corriendo
if ! docker info &> /dev/null; then
    log_error "Docker no está corriendo"
    exit 1
fi

log_success "Docker está activo"

# Verificar versión de Docker
DOCKER_VERSION=$(docker version --format '{{.Server.Version}}' 2>/dev/null || echo "unknown")
log_info "Versión de Docker: $DOCKER_VERSION"

# Verificar Docker Desktop (Windows/Mac) o Docker Engine (Linux)
if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]] || [[ "$OSTYPE" == "win32" ]]; then
    # Windows
    log_info "Sistema: Windows"
    
    # Intentar obtener información de recursos de Docker Desktop
    if docker info 2>/dev/null | grep -q "Total Memory"; then
        TOTAL_MEM=$(docker info 2>/dev/null | grep "Total Memory" | awk '{print $3}')
        log_info "Memoria total asignada a Docker: $TOTAL_MEM"
        
        # Convertir a GB para comparar
        MEM_GB=$(echo $TOTAL_MEM | sed 's/GiB//;s/MiB/\/1024/' | bc -l 2>/dev/null || echo "0")
        
        if (( $(echo "$MEM_GB < 3" | bc -l 2>/dev/null || echo "0") )); then
            log_warning "⚠️  Memoria asignada a Docker es menor a 3GB"
            log_warning "   Recomendado: 4GB o más para evitar errores ENOMEM"
            log_info "   Solución: Docker Desktop → Settings → Resources → Memory"
        else
            log_success "✓ Memoria asignada es suficiente (≥3GB)"
        fi
    else
        log_warning "No se pudo determinar memoria asignada a Docker"
    fi
    
elif [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    log_info "Sistema: macOS"
    
    if command -v docker-machine &> /dev/null; then
        TOTAL_MEM=$(docker-machine inspect default 2>/dev/null | grep Memory | head -1 | awk '{print $2}' | tr -d ',')
        if [ -n "$TOTAL_MEM" ]; then
            MEM_GB=$((TOTAL_MEM / 1024))
            log_info "Memoria asignada a Docker: ${MEM_GB}GB"
            
            if [ $MEM_GB -lt 3 ]; then
                log_warning "⚠️  Memoria asignada a Docker es menor a 3GB"
                log_info "   Solución: Docker Desktop → Settings → Resources → Memory"
            fi
        fi
    fi
    
else
    # Linux
    log_info "Sistema: Linux"
    
    # Linux no tiene límites por defecto en Docker
    TOTAL_RAM=$(free -h | grep Mem | awk '{print $2}')
    log_info "Memoria RAM total del sistema: $TOTAL_RAM"
    
    # Verificar uso actual
    USED_RAM=$(free | grep Mem | awk '{printf "%.0f", $3/$2 * 100}')
    log_info "Uso actual de RAM: ${USED_RAM}%"
    
    if [ $USED_RAM -gt 80 ]; then
        log_warning "⚠️  Uso de RAM está alto (>80%)"
    fi
fi

# Verificar uso de disco de Docker
echo ""
log_info "Uso de disco de Docker:"
docker system df

# Verificar si hay contenedores usando mucha memoria
echo ""
log_info "Contenedores activos y uso de recursos:"
if docker ps -q &> /dev/null; then
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" 2>/dev/null || log_info "No hay contenedores corriendo"
else
    log_info "No hay contenedores activos"
fi

# Verificar imágenes
echo ""
log_info "Imágenes Docker:"
 docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}" | head -10

# Recomendaciones
echo ""
echo "================================================================"
echo "  RECOMENDACIONES"
echo "================================================================"

MIN_MEMORY_GB=4

case $OSTYPE in
    msys*|cygwin*|win32*)
        echo ""
        log_info "Para Windows:"
        echo "  1. Abrir Docker Desktop"
        echo "  2. Settings (⚙️) → Resources → Advanced"
        echo "  3. Configurar:"
        echo "     - Memory: ${MIN_MEMORY_GB}GB o más"
        echo "     - Swap: 2GB"
        echo "     - CPUs: 2"
        echo "  4. Apply & Restart"
        ;;
    darwin*)
        echo ""
        log_info "Para macOS:"
        echo "  1. Abrir Docker Desktop"
        echo "  2. Settings → Resources"
        echo "  3. Memory: ${MIN_MEMORY_GB}GB o más"
        echo "  4. Apply & Restart"
        ;;
    linux*)
        echo ""
        log_info "Para Linux:"
        echo "  - Docker no tiene límites de memoria por defecto"
        echo "  - Verificar RAM disponible: free -h"
        echo "  - Si hay poca RAM, cerrar otras aplicaciones"
        ;;
esac

echo ""
log_info "Para ejecutar con límites de memoria:"
echo "  docker run --memory=2g --cpus=1.0 -p 3000:3000 <imagen>"

echo ""
log_info "Ver documentación completa: MEMORY_ERROR_SOLUTION.md"

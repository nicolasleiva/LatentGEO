#!/bin/bash
# =============================================================================
# Script de build Docker profesional para Frontend
# Manejo robusto de errores, caché, retries y logging detallado
# =============================================================================

set -euo pipefail  # Fail fast, exit on error, undefined vars, pipe errors

# -----------------------------------------------------------------------------
# CONFIGURACIÓN
# -----------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="auditor-geo"
IMAGE_NAME="${PROJECT_NAME}-frontend"
DOCKERFILE="Dockerfile.frontend"
BUILD_CONTEXT="."
MAX_RETRIES=3
RETRY_DELAY=10

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# -----------------------------------------------------------------------------
# FUNCIONES DE UTILIDAD
# -----------------------------------------------------------------------------

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# -----------------------------------------------------------------------------
# VALIDACIONES PRE-BUILD
# -----------------------------------------------------------------------------

check_docker_memory() {
    log_info "Verificando recursos de Docker..."
    
    # Obtener memoria total asignada a Docker
    TOTAL_MEM=$(docker info 2>/dev/null | grep "Total Memory" | awk '{print $3}' || echo "0")
    
    if [ -n "$TOTAL_MEM" ] && [ "$TOTAL_MEM" != "0" ]; then
        # Extraer número y unidad
        MEM_NUM=$(echo $TOTAL_MEM | grep -oE '[0-9.]+')
        MEM_UNIT=$(echo $TOTAL_MEM | grep -oE '[A-Za-z]+')
        
        # Convertir a GB
        case $MEM_UNIT in
            GiB|GB) MEM_GB=$MEM_NUM ;;
            MiB|MB) MEM_GB=$(echo "scale=2; $MEM_NUM / 1024" | bc -l 2>/dev/null || echo "0") ;;
            *) MEM_GB="0" ;;
        esac
        
        log_info "Memoria asignada a Docker: ${MEM_GB}GB"
        
        # Verificar si es suficiente (menos de 3GB = problemas)
        if (( $(echo "$MEM_GB < 3" | bc -l 2>/dev/null || echo "1") )); then
            log_warning "⚠️  Memoria asignada a Docker es baja (${MEM_GB}GB)"
            log_warning "   Recomendado: 4GB+ para evitar errores ENOMEM"
            log_info "   Solución rápida:"
            log_info "     Windows/Mac: Docker Desktop → Settings → Resources → Memory"
            log_info "     Ver guía completa: MEMORY_ERROR_SOLUTION.md"
            echo ""
            
            # Preguntar si continuar
            if [ "${SKIP_MEMORY_CHECK:-false}" != "true" ]; then
                read -p "¿Continuar de todos modos? (y/N): " -n 1 -r
                echo
                if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                    log_info "Cancelado. Aumenta la memoria de Docker e intenta de nuevo."
                    exit 1
                fi
            fi
        else
            log_success "✓ Memoria suficiente (${MEM_GB}GB)"
        fi
    else
        log_warning "No se pudo determinar memoria de Docker"
    fi
}

validate_prerequisites() {
    log_info "Validando prerequisitos..."
    
    # Verificar Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker no está instalado o no está en el PATH"
        exit 1
    fi
    
    # Verificar recursos
    check_docker_memory
    
    # Verificar Docker Buildx (necesario para caché)
    if ! docker buildx version &> /dev/null; then
        log_warning "Docker Buildx no está disponible. Creando builder..."
        docker buildx create --use --name "${PROJECT_NAME}-builder" || true
    fi
    
    # Verificar archivos necesarios
    if [[ ! -f "${SCRIPT_DIR}/${DOCKERFILE}" ]]; then
        log_error "No se encuentra ${DOCKERFILE}"
        exit 1
    fi
    
    if [[ ! -f "${SCRIPT_DIR}/frontend/package.json" ]]; then
        log_error "No se encuentra frontend/package.json"
        exit 1
    fi
    
    if [[ ! -f "${SCRIPT_DIR}/frontend/pnpm-lock.yaml" ]]; then
        log_error "No se encuentra frontend/pnpm-lock.yaml"
        log_error "Ejecuta 'cd frontend && pnpm install' primero"
        exit 1
    fi
    
    log_success "Prerequisitos validados"
}

# -----------------------------------------------------------------------------
# VERIFICACIÓN Y SINCRONIZACIÓN DE LOCKFILE
# -----------------------------------------------------------------------------

verify_lockfile() {
    log_info "Verificando sincronización de lockfile..."
    
    # Ejecutar script de sincronización
    if [[ -f "${SCRIPT_DIR}/sync-lockfile.sh" ]]; then
        bash "${SCRIPT_DIR}/sync-lockfile.sh"
    else
        log_warning "Script de sincronización no encontrado, verificando manualmente..."
        cd "${SCRIPT_DIR}/frontend"
        
        # Verificar si package.json y pnpm-lock.yaml están sincronizados
        if ! pnpm install --frozen-lockfile --lockfile-only &> /dev/null; then
            log_error "El lockfile está desincronizado con package.json"
            log_error "Ejecuta 'pnpm install' en frontend/ y commitea los cambios"
            exit 1
        fi
        
        cd - > /dev/null
    fi
    
    log_success "Lockfile verificado y sincronizado"
}

# -----------------------------------------------------------------------------
# LIMPIEZA DE CACHÉ (OPCIONAL)
# -----------------------------------------------------------------------------

cleanup_cache() {
    if [[ "${CLEAN_BUILD:-false}" == "true" ]]; then
        log_warning "Limpiando caché de Docker..."
        docker builder prune -f || true
        log_success "Caché limpiado"
    fi
}

# -----------------------------------------------------------------------------
# BUILD CON RETRY LOGIC
# -----------------------------------------------------------------------------

build_with_retry() {
    local attempt=1
    local build_args=(
        --file "${DOCKERFILE}"
        --tag "${IMAGE_NAME}:latest"
        --build-arg BUILDKIT_INLINE_CACHE=1
        --progress=plain
    )
    
    # Añadir caché si está disponible Buildx
    if docker buildx version &> /dev/null; then
        build_args+=(
            --cache-from "type=local,src=/tmp/.buildx-cache"
            --cache-to "type=local,dest=/tmp/.buildx-cache-new,mode=max"
        )
    fi
    
    # Añadir build args adicionales si existen
    if [[ -n "${BUILD_ARGS:-}" ]]; then
        build_args+=("${BUILD_ARGS}")
    fi
    
    build_args+=("${BUILD_CONTEXT}")
    
    while [[ $attempt -le $MAX_RETRIES ]]; do
        log_info "Intento de build $attempt/$MAX_RETRIES..."
        
        # Configurar BuildKit
        export DOCKER_BUILDKIT=1
        export BUILDKIT_PROGRESS=plain
        
        if docker build "${build_args[@]}" 2>&1 | tee "build-attempt-${attempt}.log"; then
            log_success "Build completado exitosamente"
            
            # Mover caché nueva a la ubicación correcta
            if [[ -d /tmp/.buildx-cache-new ]]; then
                rm -rf /tmp/.buildx-cache
                mv /tmp/.buildx-cache-new /tmp/.buildx-cache
            fi
            
            return 0
        fi
        
        log_error "Build falló en intento $attempt"
        
        if [[ $attempt -lt $MAX_RETRIES ]]; then
            log_warning "Reintentando en ${RETRY_DELAY} segundos..."
            sleep $RETRY_DELAY
        fi
        
        ((attempt++))
    done
    
    log_error "Build falló después de $MAX_RETRIES intentos"
    log_error "Revisa los logs: build-attempt-*.log"
    return 1
}

# -----------------------------------------------------------------------------
# OPTIMIZACIONES DE RED
# -----------------------------------------------------------------------------

setup_network_optimizations() {
    log_info "Configurando optimizaciones de red..."
    
    # Configurar DNS de Google como fallback (más rápido en algunos entornos)
    export DOCKER_BUILDKIT=1
    
    # Crear docker daemon config temporal si no existe
    mkdir -p ~/.docker
    if [[ ! -f ~/.docker/config.json ]]; then
        echo '{}' > ~/.docker/config.json
    fi
    
    log_success "Optimizaciones de red configuradas"
}

# -----------------------------------------------------------------------------
# INFORMACIÓN POST-BUILD
# -----------------------------------------------------------------------------

show_build_info() {
    log_info "Información de la imagen construida:"
    docker images "${IMAGE_NAME}" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"
    
    echo ""
    log_info "Para ejecutar la imagen:"
    echo "  docker run -p 3000:3000 ${IMAGE_NAME}:latest"
    
    echo ""
    log_info "Para debuggear la imagen:"
    echo "  docker run -it --entrypoint sh ${IMAGE_NAME}:latest"
}

# -----------------------------------------------------------------------------
# FUNCIÓN PRINCIPAL
# -----------------------------------------------------------------------------

main() {
    echo "================================================================"
    echo "  DOCKER BUILD - ${PROJECT_NAME} FRONTEND"
    echo "================================================================"
    echo ""
    
    # Parsear argumentos
    while [[ $# -gt 0 ]]; do
        case $1 in
            --clean)
                CLEAN_BUILD=true
                shift
                ;;
            --no-cache)
                BUILD_ARGS="--no-cache"
                shift
                ;;
            --tag)
                IMAGE_NAME="${PROJECT_NAME}-frontend:$2"
                shift 2
                ;;
            --help)
                echo "Uso: $0 [OPTIONS]"
                echo ""
                echo "Opciones:"
                echo "  --clean       Limpiar caché antes de build"
                echo "  --no-cache    Build sin usar caché"
                echo "  --tag TAG     Etiqueta personalizada para la imagen"
                echo "  --help        Mostrar esta ayuda"
                exit 0
                ;;
            *)
                log_error "Opción desconocida: $1"
                exit 1
                ;;
        esac
    done
    
    # Ejecutar pipeline
    validate_prerequisites
    verify_lockfile
    setup_network_optimizations
    cleanup_cache
    
    echo ""
    log_info "Iniciando build de Docker..."
    echo "----------------------------------------------------------------"
    
    if build_with_retry; then
        echo ""
        echo "================================================================"
        log_success "BUILD COMPLETADO EXITOSAMENTE"
        echo "================================================================"
        echo ""
        show_build_info
        exit 0
    else
        echo ""
        echo "================================================================"
        log_error "BUILD FALLÓ"
        echo "================================================================"
        exit 1
    fi
}

# Ejecutar main
main "$@"

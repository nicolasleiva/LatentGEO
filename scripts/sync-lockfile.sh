#!/bin/bash
# =============================================================================
# Script de sincronización de lockfile para Docker
# Asegura que pnpm-lock.yaml sea compatible antes del build
# =============================================================================

set -euo pipefail

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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/../frontend"

cd "$FRONTEND_DIR"

log_info "Verificando sincronización del lockfile..."

# Verificar si packageManager está definido
if ! grep -q '"packageManager"' package.json; then
    log_warning "No se encontró 'packageManager' en package.json"
    log_info "Detectando versión de pnpm..."
    PNPM_VERSION=$(pnpm --version)
    log_info "Versión detectada: pnpm@$PNPM_VERSION"
    
    # Agregar packageManager al package.json
    log_info "Agregando packageManager al package.json..."
    node -e "
        const fs = require('fs');
        const pkg = JSON.parse(fs.readFileSync('package.json', 'utf8'));
        pkg.packageManager = 'pnpm@$PNPM_VERSION';
        fs.writeFileSync('package.json', JSON.stringify(pkg, null, 2) + '\n');
    "
    log_success "packageManager agregado: pnpm@$PNPM_VERSION"
fi

# Verificar si el lockfile existe
if [ ! -f pnpm-lock.yaml ]; then
    log_warning "No existe pnpm-lock.yaml"
    log_info "Generando lockfile..."
    pnpm install --lockfile-only
    log_success "Lockfile generado"
else
    # Verificar si está sincronizado
    log_info "Verificando si lockfile está sincronizado..."
    if pnpm install --frozen-lockfile --lockfile-only > /dev/null 2>&1; then
        log_success "Lockfile está sincronizado"
    else
        log_warning "Lockfile desincronizado"
        log_info "Actualizando lockfile..."
        pnpm install --lockfile-only
        log_success "Lockfile actualizado"
        
        echo ""
        log_warning "IMPORTANTE: Se modificó pnpm-lock.yaml"
        log_warning "Por favor commitea los cambios:"
        echo "  git add pnpm-lock.yaml"
        echo "  git commit -m 'chore: sync pnpm-lock.yaml'"
    fi
fi

log_success "Verificación completada. Listo para Docker build."

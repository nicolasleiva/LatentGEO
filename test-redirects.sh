#!/bin/bash
# =============================================================================
# Test Suite para Auditor GEO - Verificación de Redirecciones
# =============================================================================

set -e

echo "=========================================="
echo "🔍 TEST SUITE - Auditor GEO"
echo "=========================================="
echo ""

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Variables
FRONTEND_URL="http://localhost:3000"
BACKEND_URL="http://localhost:8000"
MAX_RETRIES=30
RETRY_DELAY=2

# Función para imprimir errores
error_exit() {
    echo -e "${RED}❌ ERROR: $1${NC}" >&2
    exit 1
}

# Función para imprimir éxito
success() {
    echo -e "${GREEN}✅ $1${NC}"
}

# Función para imprimir advertencias
warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Función para verificar si un servicio está corriendo
check_service() {
    local url=$1
    local name=$2
    local retries=0
    
    echo "Esperando a que $name esté disponible en $url..."
    
    while [ $retries -lt $MAX_RETRIES ]; do
        if curl -s -o /dev/null -w "%{http_code}" "$url" | grep -q "200\|301\|302"; then
            success "$name está respondiendo correctamente"
            return 0
        fi
        
        retries=$((retries + 1))
        echo "  Intento $retries/$MAX_RETRIES..."
        sleep $RETRY_DELAY
    done
    
    error_exit "$name no está respondiendo después de $MAX_RETRIES intentos"
}

# =============================================================================
# TEST 1: Verificar configuración de archivos
# =============================================================================
echo "📋 TEST 1: Verificación de configuración de archivos"
echo "----------------------------------------------------"

# Verificar que .env existe en la raíz
if [ -f ".env" ]; then
    success "Archivo .env encontrado en la raíz"
else
    error_exit "Archivo .env NO encontrado en la raíz del proyecto"
fi

# Verificar que middleware.ts excluye /auth/*
if grep -q 'auth/' "frontend/middleware.ts"; then
    success "middleware.ts contiene exclusión para rutas /auth/*"
else
    warning "middleware.ts podría no excluir correctamente las rutas /auth/*"
fi

# Verificar next.config.mjs
if [ -f "frontend/next.config.mjs" ]; then
    success "next.config.mjs existe"
else
    error_exit "next.config.mjs NO encontrado"
fi

echo ""

# =============================================================================
# TEST 2: Verificar build de Docker
# =============================================================================
echo "📋 TEST 2: Verificación de build de Docker"
echo "----------------------------------------------------"

echo "Reconstruyendo contenedores..."
docker-compose down 2>/dev/null || true

# Build con output visible
docker-compose build --no-cache frontend 2>&1 | tee /tmp/docker-build.log || error_exit "Falló el build de Docker"

# Verificar que el build fue exitoso
if grep -q "successfully built\|exporting layers" /tmp/docker-build.log || grep -q "naming to docker.io" /tmp/docker-build.log; then
    success "Build de Docker completado exitosamente"
else
    error_exit "Build de Docker falló o no se completó correctamente"
fi

echo ""

# =============================================================================
# TEST 3: Levantar servicios y verificar redirecciones
# =============================================================================
echo "📋 TEST 3: Verificación de redirecciones"
echo "----------------------------------------------------"

echo "Iniciando servicios..."
docker-compose up -d

# Esperar a que los servicios estén listos
check_service "$FRONTEND_URL" "Frontend"

echo ""
echo "Verificando redirecciones..."

# Test 3.1: Redirección de / a /en
echo -n "  - Redirección / → /en: "
REDIRECT=$(curl -s -o /dev/null -w "%{redirect_url}" "$FRONTEND_URL/")
if echo "$REDIRECT" | grep -q "/en"; then
    success "OK (redirige a $REDIRECT)"
else
    error_exit "Falló la redirección de / a /en (obtenido: $REDIRECT)"
fi

# Test 3.2: Acceso directo a /en no debe redirigir
echo -n "  - Acceso a /en: "
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$FRONTEND_URL/en")
if [ "$HTTP_CODE" = "200" ]; then
    success "OK (HTTP $HTTP_CODE)"
else
    error_exit "Falló el acceso a /en (HTTP $HTTP_CODE)"
fi

# Test 3.3: Rutas /auth/* no deben tener redirección de locale
echo -n "  - Ruta /auth/login no redirige a /en/auth: "
REDIRECT=$(curl -s -o /dev/null -w "%{redirect_url}" "$FRONTEND_URL/auth/login" || echo "")
if [ -z "$REDIRECT" ] || echo "$REDIRECT" | grep -qv "/en/auth"; then
    success "OK (sin redirección forzada a /en)"
else
    error_exit "Falló: /auth/login redirige incorrectamente a $REDIRECT"
fi

# Test 3.4: Verificar que no hay loop de redirección
echo -n "  - Sin loops de redirección: "
MAX_REDIRECTS=5
CURRENT_URL="$FRONTEND_URL/"
REDIRECT_COUNT=0
LOOP_DETECTED=false

while [ $REDIRECT_COUNT -lt $MAX_REDIRECTS ]; do
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code},%{redirect_url}" "$CURRENT_URL")
    HTTP_CODE=$(echo "$RESPONSE" | cut -d',' -f1)
    NEXT_URL=$(echo "$RESPONSE" | cut -d',' -f2)
    
    if [ "$HTTP_CODE" = "200" ]; then
        break
    elif [ -z "$NEXT_URL" ] || [ "$NEXT_URL" = "$CURRENT_URL" ]; then
        break
    fi
    
    CURRENT_URL="$NEXT_URL"
    REDIRECT_COUNT=$((REDIRECT_COUNT + 1))
done

if [ $REDIRECT_COUNT -ge $MAX_REDIRECTS ]; then
    error_exit "Detectado posible loop de redirección (>5 redirecciones)"
else
    success "OK (máx $REDIRECT_COUNT redirecciones)"
fi

echo ""

# =============================================================================
# TEST 4: Verificar Auth0 Configuration
# =============================================================================
echo "📋 TEST 4: Verificación de configuración Auth0"
echo "----------------------------------------------------"

# Verificar que las variables están cargadas en el contenedor
echo -n "  - Variables Auth0 en contenedor: "
AUTH0_CHECK=$(docker exec auditor_frontend env | grep -c "AUTH0_" || echo "0")
if [ "$AUTH0_CHECK" -ge 4 ]; then
    success "OK ($AUTH0_CHECK variables Auth0 encontradas)"
else
    warning "Solo $AUTH0_CHECK variables Auth0 encontradas en el contenedor"
fi

# Verificar que APP_BASE_URL está configurado
echo -n "  - APP_BASE_URL configurado: "
if docker exec auditor_frontend env | grep -q "APP_BASE_URL=http://localhost:3000"; then
    success "OK"
else
    warning "APP_BASE_URL podría no estar configurado correctamente"
fi

echo ""

# =============================================================================
# Resumen
# =============================================================================
echo "=========================================="
echo "📊 RESUMEN DE TESTS"
echo "=========================================="
success "Todos los tests completados exitosamente!"
echo ""
echo "✨ La aplicación está funcionando correctamente:"
echo "   - Frontend: $FRONTEND_URL"
echo "   - Backend: $BACKEND_URL"
echo ""
echo "📝 Para ver logs:"
echo "   docker-compose logs -f frontend"
echo ""

exit 0

#!/bin/bash

# Docker Setup Validation Script
# This script checks if your Docker setup is correct

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
PASSED=0
FAILED=0
WARNINGS=0

# Functions
print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

check_pass() {
    echo -e "${GREEN}✓ $1${NC}"
    ((PASSED++))
}

check_fail() {
    echo -e "${RED}✗ $1${NC}"
    ((FAILED++))
}

check_warn() {
    echo -e "${YELLOW}⚠ $1${NC}"
    ((WARNINGS++))
}

# Start validation
print_header "Docker Setup Validation"

# 1. Check Docker installation
echo "1. Checking Docker installation..."
if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version)
    check_pass "Docker installed: $DOCKER_VERSION"
else
    check_fail "Docker not installed"
fi

# 2. Check Docker Compose
echo -e "\n2. Checking Docker Compose..."
if command -v docker-compose &> /dev/null; then
    COMPOSE_VERSION=$(docker-compose --version)
    check_pass "Docker Compose installed: $COMPOSE_VERSION"
else
    check_fail "Docker Compose not installed"
fi

# 3. Check Docker daemon
echo -e "\n3. Checking Docker daemon..."
if docker info > /dev/null 2>&1; then
    check_pass "Docker daemon is running"
else
    check_fail "Docker daemon is not running"
fi

# 4. Check required files
echo -e "\n4. Checking required files..."
REQUIRED_FILES=(
    "Dockerfile.backend"
    "Dockerfile.frontend"
    "docker-compose.yml"
    "docker-compose.dev.yml"
    ".env.example"
    "backend/requirements.txt"
    "frontend/package.json"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        check_pass "Found: $file"
    else
        check_fail "Missing: $file"
    fi
done

# 5. Check .env file
echo -e "\n5. Checking environment configuration..."
if [ -f ".env" ]; then
    check_pass ".env file exists"
    
    # Check for API keys
    if grep -q "GEMINI_API_KEY" .env; then
        if grep -q "GEMINI_API_KEY=" .env && [ -z "$(grep 'GEMINI_API_KEY=' .env | cut -d'=' -f2)" ]; then
            check_warn "GEMINI_API_KEY is empty (optional for basic testing)"
        else
            check_pass "GEMINI_API_KEY is configured"
        fi
    fi
else
    check_warn ".env file not found (creating from .env.example)"
    if [ -f ".env.example" ]; then
        cp .env.example .env
        check_pass "Created .env from .env.example"
    else
        check_fail "Cannot create .env - .env.example not found"
    fi
fi

# 6. Check backend structure
echo -e "\n6. Checking backend structure..."
BACKEND_FILES=(
    "backend/app/main.py"
    "backend/app/core/config.py"
    "backend/app/core/database.py"
    "backend/app/api/routes/audits.py"
)

for file in "${BACKEND_FILES[@]}"; do
    if [ -f "$file" ]; then
        check_pass "Found: $file"
    else
        check_fail "Missing: $file"
    fi
done

# 7. Check frontend structure
echo -e "\n7. Checking frontend structure..."
FRONTEND_FILES=(
    "frontend/package.json"
    "frontend/next.config.mjs"
    "frontend/tsconfig.json"
    "frontend/app/page.tsx"
)

for file in "${FRONTEND_FILES[@]}"; do
    if [ -f "$file" ]; then
        check_pass "Found: $file"
    else
        check_fail "Missing: $file"
    fi
done

# 8. Check ports availability
echo -e "\n8. Checking port availability..."
PORTS=(3000 8000 5432 6379)

for port in "${PORTS[@]}"; do
    if ! nc -z localhost $port 2>/dev/null; then
        check_pass "Port $port is available"
    else
        check_warn "Port $port is already in use"
    fi
done

# 9. Check disk space
echo -e "\n9. Checking disk space..."
AVAILABLE_SPACE=$(df . | awk 'NR==2 {print $4}')
if [ "$AVAILABLE_SPACE" -gt 5242880 ]; then  # 5GB in KB
    check_pass "Sufficient disk space available ($(numfmt --to=iec $((AVAILABLE_SPACE * 1024))) free)"
else
    check_warn "Low disk space ($(numfmt --to=iec $((AVAILABLE_SPACE * 1024))) free)"
fi

# 10. Check documentation
echo -e "\n10. Checking documentation..."
DOCS=(
    "README_DOCKER.md"
    "DOCKER_QUICK_START.md"
    "DOCKER_SETUP.md"
    "DOCKER_TROUBLESHOOTING.md"
    "DOCKER_FIXES_SUMMARY.md"
)

for doc in "${DOCS[@]}"; do
    if [ -f "$doc" ]; then
        check_pass "Found: $doc"
    else
        check_fail "Missing: $doc"
    fi
done

# Summary
print_header "Validation Summary"

echo -e "${GREEN}Passed:${NC} $PASSED"
echo -e "${YELLOW}Warnings:${NC} $WARNINGS"
echo -e "${RED}Failed:${NC} $FAILED"

if [ $FAILED -eq 0 ]; then
    echo -e "\n${GREEN}✓ All checks passed! Your Docker setup is ready.${NC}"
    echo -e "\n${BLUE}Next steps:${NC}"
    echo "1. Edit .env with your API keys (optional)"
    echo "2. Run: docker-compose up -d"
    echo "3. Access: http://localhost:3000"
    exit 0
else
    echo -e "\n${RED}✗ Some checks failed. Please fix the issues above.${NC}"
    exit 1
fi

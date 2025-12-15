#!/bin/bash

# Production Ready Test Script
# Tests core functionality of Auditor GEO

echo "🧪 Testing Auditor GEO Production Readiness"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counters
PASSED=0
FAILED=0

# Function to test endpoint
test_endpoint() {
    local name=$1
    local url=$2
    local expected_code=${3:-200}
    
    echo -n "Testing $name... "
    
    response=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null)
    
    if [ "$response" = "$expected_code" ]; then
        echo -e "${GREEN}✓ PASS${NC} (HTTP $response)"
        ((PASSED++))
    else
        echo -e "${RED}✗ FAIL${NC} (HTTP $response, expected $expected_code)"
        ((FAILED++))
    fi
}

# Function to check if service is running
check_service() {
    local name=$1
    local port=$2
    
    echo -n "Checking $name on port $port... "
    
    if nc -z localhost $port 2>/dev/null; then
        echo -e "${GREEN}✓ Running${NC}"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}✗ Not running${NC}"
        ((FAILED++))
        return 1
    fi
}

echo "1. Checking Services"
echo "-------------------"
check_service "Backend" 8000
check_service "Frontend" 3000
check_service "Redis" 6379
check_service "Database" 5432
echo ""

echo "2. Testing Backend Endpoints"
echo "----------------------------"
test_endpoint "Health Check" "http://localhost:8000/health"
test_endpoint "API Docs" "http://localhost:8000/docs"
test_endpoint "HubSpot Auth URL" "http://localhost:8000/api/hubspot/auth-url"
test_endpoint "HubSpot Connections" "http://localhost:8000/api/hubspot/connections"
test_endpoint "Audits List" "http://localhost:8000/api/audits"
echo ""

echo "3. Testing Frontend Pages"
echo "------------------------"
test_endpoint "Home Page" "http://localhost:3000"
test_endpoint "Audits Page" "http://localhost:3000/audits"
test_endpoint "Settings Page" "http://localhost:3000/settings"
test_endpoint "Integrations Page" "http://localhost:3000/integrations"
echo ""

echo "4. Testing Environment Variables"
echo "-------------------------------"
if [ -f "backend/.env" ]; then
    echo -n "Backend .env exists... "
    echo -e "${GREEN}✓ PASS${NC}"
    ((PASSED++))
    
    # Check for required variables
    required_vars=("DATABASE_URL" "HUBSPOT_CLIENT_ID" "HUBSPOT_CLIENT_SECRET" "ENCRYPTION_KEY")
    for var in "${required_vars[@]}"; do
        if grep -q "^$var=" backend/.env; then
            echo -n "  $var set... "
            echo -e "${GREEN}✓${NC}"
        else
            echo -n "  $var missing... "
            echo -e "${RED}✗${NC}"
        fi
    done
else
    echo -e "${RED}✗ FAIL${NC} - backend/.env not found"
    ((FAILED++))
fi
echo ""

if [ -f "frontend/.env.local" ]; then
    echo -n "Frontend .env.local exists... "
    echo -e "${GREEN}✓ PASS${NC}"
    ((PASSED++))
else
    echo -e "${YELLOW}⚠ WARNING${NC} - frontend/.env.local not found"
fi
echo ""

echo "5. Summary"
echo "----------"
echo -e "Tests Passed: ${GREEN}$PASSED${NC}"
echo -e "Tests Failed: ${RED}$FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed! Ready for manual testing.${NC}"
    exit 0
else
    echo -e "${RED}✗ Some tests failed. Please check the output above.${NC}"
    exit 1
fi

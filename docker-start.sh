#!/bin/bash

# Docker startup script for GEO Audit Platform

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
print_header() {
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}$1${NC}"
    echo -e "${GREEN}========================================${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    print_error "Docker daemon is not running. Please start Docker Desktop."
    exit 1
fi

print_success "Docker daemon is running"

# Check if .env file exists
if [ ! -f .env ]; then
    print_info "Creating .env file from .env.example..."
    cp .env.example .env
    print_info "Please edit .env with your API keys before running again"
    exit 0
fi

# Parse arguments
MODE=${1:-prod}
ACTION=${2:-up}

case $MODE in
    dev)
        print_header "Starting Development Environment"
        COMPOSE_FILE="docker-compose.dev.yml"
        ;;
    prod)
        print_header "Starting Production Environment"
        COMPOSE_FILE="docker-compose.yml"
        ;;
    *)
        print_error "Invalid mode: $MODE. Use 'dev' or 'prod'"
        exit 1
        ;;
esac

case $ACTION in
    up)
        print_info "Building and starting services..."
        docker-compose -f $COMPOSE_FILE up -d
        print_success "Services started"
        
        print_info "Waiting for services to be healthy..."
        sleep 5
        
        docker-compose -f $COMPOSE_FILE ps
        
        print_header "Services Ready"
        echo -e "${GREEN}Frontend:${NC} http://localhost:3000"
        echo -e "${GREEN}Backend:${NC} http://localhost:8000"
        echo -e "${GREEN}API Docs:${NC} http://localhost:8000/docs"
        echo -e "${GREEN}Database:${NC} localhost:5432"
        echo -e "${GREEN}Redis:${NC} localhost:6379"
        ;;
    down)
        print_info "Stopping services..."
        docker-compose -f $COMPOSE_FILE down
        print_success "Services stopped"
        ;;
    restart)
        print_info "Restarting services..."
        docker-compose -f $COMPOSE_FILE restart
        print_success "Services restarted"
        ;;
    logs)
        print_info "Showing logs (Ctrl+C to exit)..."
        docker-compose -f $COMPOSE_FILE logs -f
        ;;
    build)
        print_info "Building services..."
        docker-compose -f $COMPOSE_FILE build --no-cache
        print_success "Services built"
        ;;
    clean)
        print_info "Cleaning up containers and volumes..."
        docker-compose -f $COMPOSE_FILE down -v
        print_success "Cleanup complete"
        ;;
    *)
        print_error "Invalid action: $ACTION"
        echo "Available actions: up, down, restart, logs, build, clean"
        exit 1
        ;;
esac

.PHONY: help up down restart logs build clean test dev prod

# Default target
help:
	@echo "GEO Audit Platform - Docker Commands"
	@echo "===================================="
	@echo ""
	@echo "Production Commands:"
	@echo "  make prod-up       - Start production environment"
	@echo "  make prod-down     - Stop production environment"
	@echo "  make prod-restart  - Restart production services"
	@echo "  make prod-logs     - View production logs"
	@echo "  make prod-build    - Build production images"
	@echo ""
	@echo "Development Commands:"
	@echo "  make dev-up        - Start development environment (with hot reload)"
	@echo "  make dev-down      - Stop development environment"
	@echo "  make dev-restart   - Restart development services"
	@echo "  make dev-logs      - View development logs"
	@echo "  make dev-build     - Build development images"
	@echo ""
	@echo "Utility Commands:"
	@echo "  make clean         - Remove all containers and volumes"
	@echo "  make ps            - Show running containers"
	@echo "  make shell-backend - Enter backend container shell"
	@echo "  make shell-frontend- Enter frontend container shell"
	@echo "  make shell-db      - Connect to PostgreSQL database"
	@echo "  make shell-redis   - Connect to Redis"
	@echo "  make test          - Run tests"
	@echo "  make lint          - Run linters"
	@echo ""

# Production targets
prod-up:
	docker-compose up -d
	@echo "✓ Production environment started"
	@echo "  Frontend: http://localhost:3000"
	@echo "  Backend: http://localhost:8000"
	@echo "  API Docs: http://localhost:8000/docs"

prod-down:
	docker-compose down
	@echo "✓ Production environment stopped"

prod-restart:
	docker-compose restart
	@echo "✓ Production services restarted"

prod-logs:
	docker-compose logs -f

prod-build:
	docker-compose build --no-cache
	@echo "✓ Production images built"

# Development targets
dev-up:
	docker-compose -f docker-compose.dev.yml up -d
	@echo "✓ Development environment started (with hot reload)"
	@echo "  Frontend: http://localhost:3000"
	@echo "  Backend: http://localhost:8000"
	@echo "  API Docs: http://localhost:8000/docs"

dev-down:
	docker-compose -f docker-compose.dev.yml down
	@echo "✓ Development environment stopped"

dev-restart:
	docker-compose -f docker-compose.dev.yml restart
	@echo "✓ Development services restarted"

dev-logs:
	docker-compose -f docker-compose.dev.yml logs -f

dev-build:
	docker-compose -f docker-compose.dev.yml build --no-cache
	@echo "✓ Development images built"

# Utility targets
ps:
	docker-compose ps

clean:
	docker-compose down -v
	@echo "✓ All containers and volumes removed"

shell-backend:
	docker-compose exec backend bash

shell-frontend:
	docker-compose exec frontend bash

shell-db:
	docker-compose exec postgres psql -U auditor -d auditor_db

shell-redis:
	docker-compose exec redis redis-cli

test:
	docker-compose exec backend pytest

lint:
	docker-compose exec backend flake8 app/
	docker-compose exec backend black --check app/

# Status checks
status:
	@echo "Service Status:"
	@docker-compose ps
	@echo ""
	@echo "Backend Health:"
	@curl -s http://localhost:8000/health || echo "Backend not responding"
	@echo ""
	@echo "Frontend Status:"
	@curl -s http://localhost:3000 > /dev/null && echo "Frontend is running" || echo "Frontend not responding"

# Database operations
db-backup:
	docker-compose exec postgres pg_dump -U auditor auditor_db > backup.sql
	@echo "✓ Database backed up to backup.sql"

db-restore:
	docker-compose exec -T postgres psql -U auditor auditor_db < backup.sql
	@echo "✓ Database restored from backup.sql"

# Logs
logs-backend:
	docker-compose logs -f backend

logs-frontend:
	docker-compose logs -f frontend

logs-db:
	docker-compose logs -f postgres

logs-redis:
	docker-compose logs -f redis

# Quick commands
up: prod-up
down: prod-down
restart: prod-restart
logs: prod-logs
build: prod-build

.PHONY: help up down restart logs build clean test dev prod

DOCKER_COMPOSE ?= docker compose
DB_SERVICE ?= db
DEV_DB_SERVICE ?= postgres

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
	@echo "  make dev-shell-db  - Connect to PostgreSQL (dev compose)"
	@echo "  make shell-redis   - Connect to Redis"
	@echo "  make test          - Run tests"
	@echo "  make lint          - Run linters"
	@echo ""

# Production targets
prod-up:
	$(DOCKER_COMPOSE) up -d
	@echo "✓ Production environment started"
	@echo "  Frontend: http://localhost:3000"
	@echo "  Backend: http://localhost:8000"
	@echo "  API Docs: http://localhost:8000/docs"

prod-down:
	$(DOCKER_COMPOSE) down
	@echo "✓ Production environment stopped"

prod-restart:
	$(DOCKER_COMPOSE) restart
	@echo "✓ Production services restarted"

prod-logs:
	$(DOCKER_COMPOSE) logs -f

prod-build:
	$(DOCKER_COMPOSE) build --no-cache
	@echo "✓ Production images built"

# Development targets
dev-up:
	$(DOCKER_COMPOSE) -f docker-compose.dev.yml up -d
	@echo "✓ Development environment started (with hot reload)"
	@echo "  Frontend: http://localhost:3000"
	@echo "  Backend: http://localhost:8000"
	@echo "  API Docs: http://localhost:8000/docs"

dev-down:
	$(DOCKER_COMPOSE) -f docker-compose.dev.yml down
	@echo "✓ Development environment stopped"

dev-restart:
	$(DOCKER_COMPOSE) -f docker-compose.dev.yml restart
	@echo "✓ Development services restarted"

dev-logs:
	$(DOCKER_COMPOSE) -f docker-compose.dev.yml logs -f

dev-build:
	$(DOCKER_COMPOSE) -f docker-compose.dev.yml build --no-cache
	@echo "✓ Development images built"

# Utility targets
ps:
	$(DOCKER_COMPOSE) ps

clean:
	$(DOCKER_COMPOSE) down -v
	@echo "✓ All containers and volumes removed"

shell-backend:
	$(DOCKER_COMPOSE) exec backend bash

shell-frontend:
	$(DOCKER_COMPOSE) exec frontend bash

shell-db:
	$(DOCKER_COMPOSE) exec $(DB_SERVICE) psql -U auditor -d auditor_db

dev-shell-db:
	$(DOCKER_COMPOSE) -f docker-compose.dev.yml exec $(DEV_DB_SERVICE) psql -U auditor -d auditor_db

shell-redis:
	$(DOCKER_COMPOSE) exec redis redis-cli

test:
	$(DOCKER_COMPOSE) exec backend pytest

lint:
	$(DOCKER_COMPOSE) exec backend flake8 app/
	$(DOCKER_COMPOSE) exec backend black --check app/

# Status checks
status:
	@echo "Service Status:"
	@$(DOCKER_COMPOSE) ps
	@echo ""
	@echo "Backend Health:"
	@curl -s http://localhost:8000/health || echo "Backend not responding"
	@echo ""
	@echo "Frontend Status:"
	@curl -s http://localhost:3000 > /dev/null && echo "Frontend is running" || echo "Frontend not responding"

# Database operations
db-backup:
	$(DOCKER_COMPOSE) exec $(DB_SERVICE) pg_dump -U auditor auditor_db > backup.sql
	@echo "✓ Database backed up to backup.sql"

db-restore:
	$(DOCKER_COMPOSE) exec -T $(DB_SERVICE) psql -U auditor auditor_db < backup.sql
	@echo "✓ Database restored from backup.sql"

# Logs
logs-backend:
	$(DOCKER_COMPOSE) logs -f backend

logs-frontend:
	$(DOCKER_COMPOSE) logs -f frontend

logs-db:
	$(DOCKER_COMPOSE) logs -f $(DB_SERVICE)

dev-logs-db:
	$(DOCKER_COMPOSE) -f docker-compose.dev.yml logs -f $(DEV_DB_SERVICE)

logs-redis:
	$(DOCKER_COMPOSE) logs -f redis

# Quick commands
up: prod-up
down: prod-down
restart: prod-restart
logs: prod-logs
build: prod-build

# Docker Setup Guide - GEO Audit Platform

## Prerequisites

- Docker Desktop installed and running
- Docker Compose v2.0+
- Git

## Quick Start

### 1. Clone and Setup Environment

```bash
# Clone the repository
git clone <repository-url>
cd auditor

# Copy environment variables
cp .env.example .env

# Edit .env with your API keys
# GEMINI_API_KEY=your_key_here
# OPENAI_API_KEY=your_key_here
# GOOGLE_API_KEY=your_key_here
# CSE_ID=your_cse_id_here
```

### 2. Production Build

```bash
# Build and start all services
docker-compose up -d

# Check service status
docker-compose ps

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend
```

### 3. Development Build

```bash
# Use development compose file with hot reload
docker-compose -f docker-compose.dev.yml up -d

# Check service status
docker-compose -f docker-compose.dev.yml ps

# View logs with follow
docker-compose -f docker-compose.dev.yml logs -f backend
```

## Services

### Backend (FastAPI)
- **URL**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **Port**: 8000

### Frontend (Next.js)
- **URL**: http://localhost:3000
- **Port**: 3000

### Database (PostgreSQL)
- **Host**: postgres (or localhost in dev)
- **Port**: 5432
- **User**: auditor
- **Password**: auditor_password
- **Database**: auditor_db

### Cache (Redis)
- **Host**: redis (or localhost in dev)
- **Port**: 6379

## Common Commands

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f frontend

# Last 100 lines
docker-compose logs --tail=100 backend
```

### Stop Services
```bash
# Stop all services
docker-compose down

# Stop and remove volumes (WARNING: deletes data)
docker-compose down -v
```

### Rebuild Services
```bash
# Rebuild backend
docker-compose build backend

# Rebuild frontend
docker-compose build frontend

# Rebuild all
docker-compose build --no-cache
```

### Execute Commands in Container
```bash
# Backend shell
docker-compose exec backend bash

# Frontend shell
docker-compose exec frontend bash

# Run Python command
docker-compose exec backend python -c "import app; print('OK')"
```

### Database Management
```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U auditor -d auditor_db

# Backup database
docker-compose exec postgres pg_dump -U auditor auditor_db > backup.sql

# Restore database
docker-compose exec -T postgres psql -U auditor auditor_db < backup.sql
```

## Troubleshooting

### Backend won't start
```bash
# Check logs
docker-compose logs backend

# Common issues:
# 1. Port 8000 already in use
#    Change port in docker-compose.yml: "8001:8000"
# 2. Database connection failed
#    Wait for postgres to be healthy: docker-compose ps
# 3. Missing environment variables
#    Check .env file exists and has required keys
```

### Frontend won't build
```bash
# Check logs
docker-compose logs frontend

# Common issues:
# 1. Node modules cache issue
#    docker-compose down -v && docker-compose build --no-cache frontend
# 2. Port 3000 already in use
#    Change port in docker-compose.yml: "3001:3000"
```

### Database connection issues
```bash
# Check if postgres is healthy
docker-compose ps

# Connect directly
docker-compose exec postgres psql -U auditor -d auditor_db

# Check connection from backend
docker-compose exec backend python -c "
from app.core.database import engine
print(engine.url)
"
```

### Redis connection issues
```bash
# Check if redis is running
docker-compose exec redis redis-cli ping

# Check redis info
docker-compose exec redis redis-cli info
```

## Performance Tips

### Development
- Use `docker-compose.dev.yml` for hot reload
- Mount volumes for code changes
- Keep containers running between sessions

### Production
- Use `docker-compose.yml` (optimized)
- Set `DEBUG=False`
- Use environment variables for secrets
- Enable restart policies
- Monitor logs and health checks

## Environment Variables

### Backend
- `DEBUG`: Enable debug mode (True/False)
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `CELERY_BROKER`: Celery broker URL
- `CELERY_BACKEND`: Celery result backend URL
- `GEMINI_API_KEY`: Google Gemini API key
- `OPENAI_API_KEY`: OpenAI API key
- `GOOGLE_API_KEY`: Google Custom Search API key
- `CSE_ID`: Custom Search Engine ID

### Frontend
- `NEXT_PUBLIC_API_URL`: Backend API URL

## Security Notes

1. **Never commit .env file** - Use .env.example as template
2. **Change default passwords** in docker-compose.yml for production
3. **Use secrets management** for sensitive data
4. **Enable HTTPS** in production
5. **Restrict network access** to required ports only
6. **Keep images updated** - Rebuild regularly

## Scaling

### Multiple Backend Instances
```yaml
backend:
  deploy:
    replicas: 3
```

### Load Balancing
Add nginx service for load balancing between backend instances.

### Database Replication
Configure PostgreSQL replication for high availability.

## Monitoring

### Health Checks
All services have health checks configured:
- Backend: `/health` endpoint
- Frontend: HTTP GET on port 3000
- PostgreSQL: `pg_isready` command
- Redis: `redis-cli ping` command

### Logs
```bash
# Real-time logs
docker-compose logs -f

# Specific service
docker-compose logs -f backend

# Last N lines
docker-compose logs --tail=50 backend
```

## Support

For issues or questions:
1. Check logs: `docker-compose logs -f`
2. Verify environment variables: `docker-compose config`
3. Test connectivity: `docker-compose exec backend curl http://postgres:5432`
4. Check Docker daemon: `docker ps`

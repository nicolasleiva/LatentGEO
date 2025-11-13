# GEO Audit Platform - Docker Deployment Guide

## Overview

This guide covers the complete Docker setup for the GEO Audit Platform, including both frontend (Next.js) and backend (FastAPI) services.

## What's Fixed

All Docker configuration issues have been resolved:

✓ **Backend Dockerfile** - Proper FastAPI/Uvicorn deployment  
✓ **Frontend Dockerfile** - Multi-stage Next.js build  
✓ **Docker Compose** - Correct service configuration  
✓ **Dependencies** - All required packages included  
✓ **Documentation** - Comprehensive guides and troubleshooting  

See [DOCKER_FIXES_SUMMARY.md](DOCKER_FIXES_SUMMARY.md) for detailed changes.

## Quick Start (30 seconds)

### Prerequisites
- Docker Desktop installed and running
- Git

### Setup

```bash
# 1. Clone repository
git clone <repository-url>
cd auditor

# 2. Copy environment file
cp .env.example .env

# 3. Edit .env with your API keys (optional for testing)
# GEMINI_API_KEY=your_key
# OPENAI_API_KEY=your_key
# GOOGLE_API_KEY=your_key
# CSE_ID=your_cse_id

# 4. Start services
docker-compose up -d

# 5. Access services
# Frontend: http://localhost:3000
# Backend: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

## Services

| Service | URL | Port | Purpose |
|---------|-----|------|---------|
| Frontend | http://localhost:3000 | 3000 | Next.js web application |
| Backend | http://localhost:8000 | 8000 | FastAPI REST API |
| API Docs | http://localhost:8000/docs | 8000 | Swagger UI documentation |
| Database | localhost | 5432 | PostgreSQL database |
| Cache | localhost | 6379 | Redis cache |

## Modes

### Production Mode (Default)

```bash
# Start production environment
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

**Features:**
- Optimized images
- No hot reload
- Production-ready configuration
- Health checks enabled

### Development Mode

```bash
# Start development environment with hot reload
docker-compose -f docker-compose.dev.yml up -d

# View logs
docker-compose -f docker-compose.dev.yml logs -f backend

# Stop services
docker-compose -f docker-compose.dev.yml down
```

**Features:**
- Hot reload for code changes
- Volume mounts for live editing
- Debug mode enabled
- Faster iteration

## Common Commands

### Using Docker Compose

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f backend

# Check status
docker-compose ps

# Rebuild images
docker-compose build --no-cache

# Enter container
docker-compose exec backend bash
```

### Using Make (Linux/Mac)

```bash
# Production
make prod-up          # Start
make prod-down        # Stop
make prod-logs        # View logs
make prod-build       # Rebuild

# Development
make dev-up           # Start with hot reload
make dev-logs         # View logs

# Utilities
make ps               # Show containers
make clean            # Remove all
make shell-backend    # Enter backend
make shell-db         # Connect to database
```

### Using Startup Scripts

**Linux/Mac:**
```bash
chmod +x docker-start.sh
./docker-start.sh prod up      # Start production
./docker-start.sh dev up       # Start development
./docker-start.sh prod logs    # View logs
```

**Windows:**
```batch
docker-start.bat prod up       # Start production
docker-start.bat dev up        # Start development
docker-start.bat prod logs     # View logs
```

## Environment Variables

### Required for API Features

Create `.env` file from `.env.example`:

```env
# API Keys (optional for basic testing)
GEMINI_API_KEY=your_gemini_key
OPENAI_API_KEY=your_openai_key
GOOGLE_API_KEY=your_google_key
CSE_ID=your_custom_search_engine_id

# Database (auto-configured)
DATABASE_URL=postgresql+psycopg2://auditor:auditor_password@postgres:5432/auditor_db

# Redis (auto-configured)
REDIS_URL=redis://redis:6379/0
```

## Troubleshooting

### Backend Issues

```bash
# Check logs
docker-compose logs backend

# Test connection
docker-compose exec backend curl http://localhost:8000/health

# Common fixes:
# 1. Port 8000 in use: Change in docker-compose.yml
# 2. Database not ready: Wait for postgres to be healthy
# 3. Import errors: Rebuild with docker-compose build --no-cache backend
```

### Frontend Issues

```bash
# Check logs
docker-compose logs frontend

# Test connection
docker-compose exec frontend curl http://localhost:3000

# Common fixes:
# 1. Port 3000 in use: Change in docker-compose.yml
# 2. Build failed: docker-compose build --no-cache frontend
# 3. Node modules issue: docker-compose down -v && docker-compose up -d
```

### Database Issues

```bash
# Check if postgres is healthy
docker-compose ps postgres

# Connect to database
docker-compose exec postgres psql -U auditor -d auditor_db

# Check logs
docker-compose logs postgres
```

### Redis Issues

```bash
# Check if redis is running
docker-compose exec redis redis-cli ping

# Check redis info
docker-compose exec redis redis-cli info
```

For detailed troubleshooting, see [DOCKER_TROUBLESHOOTING.md](DOCKER_TROUBLESHOOTING.md).

## Database Management

### Backup Database

```bash
docker-compose exec postgres pg_dump -U auditor auditor_db > backup.sql
```

### Restore Database

```bash
docker-compose exec -T postgres psql -U auditor auditor_db < backup.sql
```

### Connect to Database

```bash
docker-compose exec postgres psql -U auditor -d auditor_db
```

## Performance Optimization

### Development
- Use `docker-compose.dev.yml` for hot reload
- Mount volumes for code changes
- Keep containers running between sessions

### Production
- Use `docker-compose.yml` (optimized)
- Set `DEBUG=False`
- Use environment variables for secrets
- Enable restart policies
- Monitor health checks

## Scaling

### Multiple Backend Instances

```yaml
backend:
  deploy:
    replicas: 3
```

### Load Balancing

Add nginx service for load balancing between instances.

### Database Replication

Configure PostgreSQL replication for high availability.

## Monitoring

### Health Checks

All services have health checks:

```bash
# Check all services
docker-compose ps

# Test backend health
curl http://localhost:8000/health

# Test frontend
curl http://localhost:3000
```

### Logs

```bash
# Real-time logs
docker-compose logs -f

# Specific service
docker-compose logs -f backend

# Last N lines
docker-compose logs --tail=100 backend
```

### Resource Usage

```bash
# Check resource usage
docker stats

# Check container details
docker inspect auditor_backend
```

## Security

### Best Practices

1. **Never commit .env file** - Use .env.example as template
2. **Change default passwords** in docker-compose.yml for production
3. **Use secrets management** for sensitive data
4. **Enable HTTPS** in production
5. **Restrict network access** to required ports only
6. **Keep images updated** - Rebuild regularly

### Environment Variables

Store sensitive data in `.env` file:

```env
GEMINI_API_KEY=your_secret_key
OPENAI_API_KEY=your_secret_key
GOOGLE_API_KEY=your_secret_key
CSE_ID=your_secret_id
```

## Documentation

- **[DOCKER_QUICK_START.md](DOCKER_QUICK_START.md)** - Quick reference guide
- **[DOCKER_SETUP.md](DOCKER_SETUP.md)** - Comprehensive setup guide
- **[DOCKER_TROUBLESHOOTING.md](DOCKER_TROUBLESHOOTING.md)** - Detailed troubleshooting
- **[DOCKER_FIXES_SUMMARY.md](DOCKER_FIXES_SUMMARY.md)** - Summary of fixes

## File Structure

```
auditor/
├── Dockerfile.backend          # Backend container definition
├── Dockerfile.frontend         # Frontend container definition
├── docker-compose.yml          # Production configuration
├── docker-compose.dev.yml      # Development configuration
├── .dockerignore               # Docker build optimization
├─��� .env.example                # Environment template
├── docker-start.sh             # Linux/Mac startup script
├── docker-start.bat            # Windows startup script
├── Makefile                    # Make commands
├── README_DOCKER.md            # This file
├── DOCKER_QUICK_START.md       # Quick reference
├── DOCKER_SETUP.md             # Setup guide
├── DOCKER_TROUBLESHOOTING.md   # Troubleshooting guide
├── DOCKER_FIXES_SUMMARY.md     # Changes summary
├── backend/                    # FastAPI backend
│   ├── app/
│   ├── requirements.txt
│   └── main.py
└── frontend/                   # Next.js frontend
    ├── app/
    ├── components/
    ├── package.json
    └── next.config.mjs
```

## Next Steps

1. ✓ Review this guide
2. ✓ Copy `.env.example` to `.env`
3. ✓ Add your API keys to `.env`
4. ✓ Run `docker-compose up -d`
5. ✓ Access http://localhost:3000
6. ✓ Check http://localhost:8000/docs for API documentation

## Support

For issues:

1. Check [DOCKER_TROUBLESHOOTING.md](DOCKER_TROUBLESHOOTING.md)
2. View logs: `docker-compose logs -f`
3. Check service status: `docker-compose ps`
4. Test connectivity: `docker-compose exec backend curl http://postgres:5432`

## Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Next.js Documentation](https://nextjs.org/docs)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Redis Documentation](https://redis.io/documentation)

---

**Last Updated:** 2024  
**Version:** 1.0  
**Status:** Production Ready ✓

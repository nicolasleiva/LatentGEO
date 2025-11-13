# Docker Quick Start Guide

## 30-Second Setup

```bash
# 1. Copy environment file
cp .env.example .env

# 2. Start services
docker-compose up -d

# 3. Done! Access:
# Frontend: http://localhost:3000
# Backend: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

## Windows Users

```batch
# 1. Copy environment file
copy .env.example .env

# 2. Start services
docker-compose up -d

# 3. Or use the batch script
docker-start.bat prod up
```

## Development Mode (Hot Reload)

```bash
# Start with hot reload
docker-compose -f docker-compose.dev.yml up -d

# View logs
docker-compose -f docker-compose.dev.yml logs -f backend
```

## Common Commands

| Command | Purpose |
|---------|---------|
| `docker-compose up -d` | Start all services |
| `docker-compose down` | Stop all services |
| `docker-compose logs -f backend` | View backend logs |
| `docker-compose ps` | Check service status |
| `docker-compose build backend` | Rebuild backend |
| `docker-compose exec backend bash` | Enter backend container |

## Accessing Services

| Service | URL | Purpose |
|---------|-----|---------|
| Frontend | http://localhost:3000 | Web UI |
| Backend | http://localhost:8000 | API |
| API Docs | http://localhost:8000/docs | Swagger UI |
| Database | localhost:5432 | PostgreSQL |
| Cache | localhost:6379 | Redis |

## Troubleshooting

**Backend won't start?**
```bash
docker-compose logs backend
# Check if port 8000 is in use
```

**Frontend won't build?**
```bash
docker-compose logs frontend
# Try: docker-compose build --no-cache frontend
```

**Database connection failed?**
```bash
docker-compose ps postgres
# Wait for "healthy" status
```

**Need to reset everything?**
```bash
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
```

## Environment Variables

Edit `.env` file with your API keys:

```env
GEMINI_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
GOOGLE_API_KEY=your_key_here
CSE_ID=your_cse_id_here
```

## Next Steps

1. Read [DOCKER_SETUP.md](DOCKER_SETUP.md) for detailed setup
2. Check [DOCKER_TROUBLESHOOTING.md](DOCKER_TROUBLESHOOTING.md) if issues arise
3. Access API docs at http://localhost:8000/docs
4. Start creating audits!

## Need Help?

```bash
# Check all services
docker-compose ps

# View all logs
docker-compose logs

# Check specific service
docker-compose logs backend

# Test backend health
curl http://localhost:8000/health

# Test database
docker-compose exec postgres psql -U auditor -d auditor_db -c "SELECT 1"
```

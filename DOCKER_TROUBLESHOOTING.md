# Docker Troubleshooting Guide

## Quick Diagnostics

Run this to check your Docker setup:

```bash
# Check Docker version
docker --version
docker-compose --version

# Check if Docker daemon is running
docker ps

# Check all containers
docker-compose ps

# Check service health
docker-compose ps --format "table {{.Names}}\t{{.Status}}"
```

## Common Issues and Solutions

### 1. Backend Container Won't Start

**Symptoms:**
- `docker-compose ps` shows backend as "Exited"
- Logs show connection errors

**Solutions:**

```bash
# Check logs
docker-compose logs backend

# Common causes:

# A) Port 8000 already in use
# Solution: Change port in docker-compose.yml
# Change: "8000:8000" to "8001:8000"

# B) Database not ready
# Solution: Wait for postgres to be healthy
docker-compose ps postgres
# Wait until Status shows "healthy"

# C) Missing environment variables
# Solution: Check .env file
cat .env
# Ensure all required variables are set

# D) Python import errors
# Solution: Rebuild the image
docker-compose build --no-cache backend
docker-compose up -d backend
```

### 2. Frontend Container Won't Build

**Symptoms:**
- Build fails with npm errors
- Container exits immediately

**Solutions:**

```bash
# Check logs
docker-compose logs frontend

# Common causes:

# A) Node modules cache issue
docker-compose down -v
docker-compose build --no-cache frontend
docker-compose up -d frontend

# B) Port 3000 already in use
# Solution: Change port in docker-compose.yml
# Change: "3000:3000" to "3001:3000"

# C) Missing package.json
# Solution: Verify frontend directory structure
ls -la frontend/
# Should contain: package.json, next.config.mjs, etc.

# D) Out of memory during build
# Solution: Increase Docker memory limit
# Docker Desktop Settings > Resources > Memory
```

### 3. Database Connection Failed

**Symptoms:**
- Backend logs show "connection refused"
- "could not connect to server"

**Solutions:**

```bash
# Check if postgres is running
docker-compose ps postgres

# Check postgres logs
docker-compose logs postgres

# Test connection directly
docker-compose exec postgres psql -U auditor -d auditor_db

# If postgres won't start:
# A) Check port 5432 is not in use
netstat -an | grep 5432

# B) Check volume permissions
docker-compose down -v
docker-compose up -d postgres
docker-compose logs postgres

# C) Verify DATABASE_URL in .env
cat .env | grep DATABASE_URL
# Should be: postgresql+psycopg2://auditor:auditor_password@postgres:5432/auditor_db
```

### 4. Redis Connection Issues

**Symptoms:**
- "Error 10061 connecting to localhost:6379"
- Celery tasks not running

**Solutions:**

```bash
# Check if redis is running
docker-compose ps redis

# Test redis connection
docker-compose exec redis redis-cli ping
# Should return: PONG

# Check redis logs
docker-compose logs redis

# If redis won't start:
docker-compose down redis
docker-compose up -d redis
docker-compose logs redis

# Check redis info
docker-compose exec redis redis-cli info
```

### 5. API Not Responding

**Symptoms:**
- Cannot access http://localhost:8000
- Connection refused

**Solutions:**

```bash
# Check if backend is running
docker-compose ps backend

# Check backend logs
docker-compose logs backend

# Test connection from container
docker-compose exec backend curl http://localhost:8000/health

# Check if port is exposed
docker-compose port backend 8000

# If backend is running but not responding:
# A) Check CORS settings
docker-compose exec backend python -c "from app.core.config import settings; print(settings.CORS_ORIGINS)"

# B) Check if app is initialized
docker-compose logs backend | grep "Application startup complete"

# C) Restart backend
docker-compose restart backend
```

### 6. Frontend Not Loading

**Symptoms:**
- Cannot access http://localhost:3000
- Blank page or 404 errors

**Solutions:**

```bash
# Check if frontend is running
docker-compose ps frontend

# Check frontend logs
docker-compose logs frontend

# Test connection from container
docker-compose exec frontend curl http://localhost:3000

# Check if Next.js built successfully
docker-compose exec frontend ls -la .next/

# If frontend is running but not loading:
# A) Check API URL configuration
docker-compose exec frontend env | grep API_URL

# B) Check browser console for errors
# Open http://localhost:3000 and check browser DevTools

# C) Rebuild frontend
docker-compose build --no-cache frontend
docker-compose up -d frontend
```

### 7. Out of Disk Space

**Symptoms:**
- Build fails with "no space left on device"
- Docker commands hang

**Solutions:**

```bash
# Check Docker disk usage
docker system df

# Clean up unused images
docker image prune -a

# Clean up unused volumes
docker volume prune

# Clean up unused networks
docker network prune

# Full cleanup (WARNING: removes all unused Docker resources)
docker system prune -a --volumes

# Check available disk space
df -h
```

### 8. Permission Denied Errors

**Symptoms:**
- "permission denied" when accessing volumes
- Cannot write to /app/reports or /app/logs

**Solutions:**

```bash
# Check volume permissions
docker-compose exec backend ls -la /app/reports

# Fix permissions
docker-compose exec backend chmod -R 755 /app/reports
docker-compose exec backend chmod -R 755 /app/logs

# Or recreate volumes
docker-compose down -v
docker-compose up -d
```

### 9. Network Issues

**Symptoms:**
- Containers can't communicate with each other
- "name resolution failed"

**Solutions:**

```bash
# Check network
docker network ls
docker network inspect auditor_network

# Test connectivity between containers
docker-compose exec backend ping redis
docker-compose exec backend ping postgres

# If network issues persist:
docker-compose down
docker network prune
docker-compose up -d
```

### 10. Memory/CPU Issues

**Symptoms:**
- Containers crash or restart frequently
- High CPU usage
- Out of memory errors

**Solutions:**

```bash
# Check resource usage
docker stats

# Check container limits
docker inspect auditor_backend | grep -A 10 "HostConfig"

# Increase Docker resources
# Docker Desktop Settings > Resources
# Increase: CPUs, Memory, Swap

# Optimize docker-compose.yml
# Add resource limits:
# services:
#   backend:
#     deploy:
#       resources:
#         limits:
#           cpus: '1'
#           memory: 1G
```

## Advanced Debugging

### View Container Internals

```bash
# Enter container shell
docker-compose exec backend bash

# Check Python environment
python --version
pip list

# Check installed packages
pip show fastapi

# Run Python directly
python -c "import app; print('OK')"
```

### Check Network Connectivity

```bash
# From backend container
docker-compose exec backend curl http://postgres:5432
docker-compose exec backend curl http://redis:6379
docker-compose exec backend curl http://frontend:3000

# From frontend container
docker-compose exec frontend curl http://backend:8000/health
```

### Database Debugging

```bash
# Connect to database
docker-compose exec postgres psql -U auditor -d auditor_db

# List tables
\dt

# Check table structure
\d audits

# Run query
SELECT * FROM audits LIMIT 5;

# Exit
\q
```

### Redis Debugging

```bash
# Connect to redis
docker-compose exec redis redis-cli

# Check keys
KEYS *

# Get value
GET key_name

# Check memory
INFO memory

# Exit
EXIT
```

## Performance Optimization

### Build Optimization

```bash
# Use BuildKit for faster builds
DOCKER_BUILDKIT=1 docker-compose build

# Build specific service
docker-compose build backend

# Build without cache
docker-compose build --no-cache
```

### Runtime Optimization

```bash
# Use production compose file
docker-compose -f docker-compose.yml up -d

# Set resource limits
# Edit docker-compose.yml and add:
# deploy:
#   resources:
#     limits:
#       cpus: '2'
#       memory: 2G
```

## Logs and Monitoring

### View Logs

```bash
# All services
docker-compose logs

# Specific service
docker-compose logs backend

# Follow logs
docker-compose logs -f backend

# Last N lines
docker-compose logs --tail=100 backend

# Since specific time
docker-compose logs --since 2024-01-01 backend
```

### Export Logs

```bash
# Export to file
docker-compose logs backend > backend.log

# Export all logs
docker-compose logs > all_services.log
```

## Recovery Procedures

### Full Reset

```bash
# Stop all services
docker-compose down

# Remove all volumes (WARNING: deletes data)
docker volume prune -a

# Remove all images
docker image prune -a

# Start fresh
docker-compose build --no-cache
docker-compose up -d
```

### Backup and Restore

```bash
# Backup database
docker-compose exec postgres pg_dump -U auditor auditor_db > backup.sql

# Restore database
docker-compose exec -T postgres psql -U auditor auditor_db < backup.sql

# Backup volumes
docker run --rm -v auditor_postgres_data:/data -v $(pwd):/backup \
  alpine tar czf /backup/postgres_backup.tar.gz -C /data .
```

## Getting Help

If you're still having issues:

1. **Check logs first**
   ```bash
   docker-compose logs -f
   ```

2. **Verify configuration**
   ```bash
   docker-compose config
   ```

3. **Check Docker status**
   ```bash
   docker ps
   docker system df
   ```

4. **Restart everything**
   ```bash
   docker-compose down
   docker-compose up -d
   ```

5. **Full reset (last resort)**
   ```bash
   docker-compose down -v
   docker system prune -a
   docker-compose build --no-cache
   docker-compose up -d
   ```

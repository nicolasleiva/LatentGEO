# Quick Start - Production Ready Version

Get Auditor GEO up and running in 10 minutes with full light/dark theme and HubSpot integration.

## Prerequisites

- Docker and Docker Compose installed
- HubSpot account (for HubSpot integration)
- GitHub account (for GitHub integration)
- Auth0 account (for user authentication)

## 1. Clone and Setup (2 minutes)

```bash
# Clone repository
git clone <repository-url>
cd auditor_geo

# Create environment files
cp backend/.env.example backend/.env
cp frontend/.env.local.example frontend/.env.local
```

## 2. Configure Backend (3 minutes)

Edit `backend/.env`:

```bash
# Required - Generate these first
ENCRYPTION_KEY=$(python3 -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())")
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

# Database (Docker will handle this)
DATABASE_URL=postgresql://auditor:auditor@db:5432/auditor_db

# Redis (Docker will handle this)
REDIS_URL=redis://redis:6379/0

# HubSpot (get from https://developers.hubspot.com/)
HUBSPOT_CLIENT_ID=your_hubspot_client_id
HUBSPOT_CLIENT_SECRET=your_hubspot_client_secret
HUBSPOT_REDIRECT_URI=http://localhost:3000/integrations

# GitHub (get from GitHub Settings > Developer settings > GitHub Apps)
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret
GITHUB_APP_ID=your_github_app_id
GITHUB_PRIVATE_KEY_PATH=/app/github-private-key.pem

# API Keys (optional but recommended)
GEMINI_API_KEY=your_gemini_key
NVIDIA_API_KEY=your_nvidia_key
GOOGLE_PAGESPEED_API_KEY=your_pagespeed_key
```

## 3. Configure Frontend (2 minutes)

Edit `frontend/.env.local`:

```bash
# Backend API
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000

# Auth0 (get from https://auth0.com/)
AUTH0_SECRET=$(openssl rand -base64 32)
AUTH0_BASE_URL=http://localhost:3000
AUTH0_ISSUER_BASE_URL=https://your-tenant.auth0.com
AUTH0_CLIENT_ID=your_auth0_client_id
AUTH0_CLIENT_SECRET=your_auth0_client_secret

# App URL
APP_BASE_URL=http://localhost:3000
```

## 4. Start Application (1 minute)

```bash
# Start all services
docker-compose up --build

# Wait for services to start (about 30 seconds)
# You'll see: "Application startup complete"
```

## 5. Access Application (1 minute)

Open your browser:

- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs

## 6. Test Features (1 minute)

### Test Theme Switching

1. Navigate to Settings: http://localhost:3000/settings
2. Click Light/Dark/System theme buttons
3. Navigate through pages to see theme applied

### Test HubSpot Integration

1. Navigate to Integrations: http://localhost:3000/integrations
2. Click "Connect HubSpot"
3. Authorize the app
4. You should see "Connected" status

### Test GitHub Integration

1. Navigate to Integrations: http://localhost:3000/integrations
2. Click "Connect GitHub"
3. Authorize the app
4. You should see "Connected" status

### Create an Audit

1. Go to home page: http://localhost:3000
2. Enter a URL (e.g., https://example.com)
3. Click "Analyze"
4. Wait for audit to complete
5. View results with charts and recommendations

## Troubleshooting

### "Missing required environment variable"

**Solution:** Check backend logs for the specific variable:

```bash
docker-compose logs backend | grep "Missing"
```

Add the missing variable to `backend/.env` and restart:

```bash
docker-compose restart backend
```

### "HubSpot OAuth fails"

**Solutions:**

1. Verify redirect URI in HubSpot app settings matches exactly:
   ```
   http://localhost:3000/integrations
   ```

2. Check credentials in `backend/.env`:
   ```bash
   echo $HUBSPOT_CLIENT_ID
   echo $HUBSPOT_CLIENT_SECRET
   ```

3. Ensure HubSpot app has required scopes:
   - `content`
   - `cms.pages.read`
   - `cms.pages.write`

### "Database connection failed"

**Solution:** Ensure Docker containers are running:

```bash
docker-compose ps

# Should show:
# - backend (running)
# - frontend (running)
# - db (running)
# - redis (running)
# - worker (running)
```

If db is not running:

```bash
docker-compose up -d db
docker-compose restart backend
```

### "Theme not switching"

**Solution:** Clear browser cache and localStorage:

1. Open DevTools (F12)
2. Go to Application tab
3. Clear Storage
4. Refresh page

### "Port already in use"

**Solution:** Stop conflicting services:

```bash
# Check what's using port 3000
lsof -i :3000

# Kill the process
kill -9 <PID>

# Or change port in docker-compose.yml
```

## Quick Commands

```bash
# View logs
docker-compose logs -f backend
docker-compose logs -f frontend

# Restart services
docker-compose restart backend
docker-compose restart frontend

# Stop all services
docker-compose down

# Rebuild and start
docker-compose up --build

# Run database migrations
docker-compose exec backend alembic upgrade head

# Access database
docker-compose exec db psql -U auditor -d auditor_db

# Run tests
docker-compose exec backend pytest tests/
docker-compose exec frontend npm test
```

## What's Working

✅ **Light/Dark Theme:**
- All pages support both themes
- Theme toggle in settings
- Persists across navigation
- Charts adapt to theme

✅ **HubSpot Integration:**
- OAuth flow
- Connection management
- Page syncing (ready to test)
- Recommendations (ready to test)
- Apply changes (ready to test)

✅ **GitHub Integration:**
- OAuth flow
- Auto-fix functionality
- Pull request creation

✅ **Core Features:**
- Create audits
- View results
- Generate reports
- Dashboard with charts
- User authentication

## Next Steps

1. **Test HubSpot Features:**
   - Connect your HubSpot account
   - Sync pages
   - Generate recommendations
   - Apply changes

2. **Test GitHub Features:**
   - Connect your GitHub account
   - Select a repository
   - Apply auto-fixes
   - Review pull requests

3. **Customize:**
   - Add your branding
   - Configure additional integrations
   - Set up monitoring

4. **Deploy to Production:**
   - See ENVIRONMENT_SETUP.md for production deployment
   - Update URLs to production domains
   - Enable HTTPS
   - Set up monitoring

## Documentation

- **ENVIRONMENT_SETUP.md** - Detailed environment configuration
- **TESTING_GUIDE.md** - Comprehensive testing procedures
- **PRODUCTION_STATUS.md** - Current implementation status
- **PRODUCTION_READY_SUMMARY.md** - Complete feature overview

## Support

If you encounter issues:

1. Check logs: `docker-compose logs -f`
2. Review documentation in the files above
3. Verify environment variables are set correctly
4. Ensure all services are running: `docker-compose ps`

## Success!

You now have a fully functional Auditor GEO platform with:
- ✅ Light and dark theme support
- ✅ HubSpot integration ready to use
- ✅ GitHub integration working
- ✅ Complete audit functionality
- ✅ Professional UI with charts and visualizations

**Time to first audit: ~10 minutes** 🎉

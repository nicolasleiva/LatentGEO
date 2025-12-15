# Environment Setup Guide

Complete guide for setting up Auditor GEO in development and production environments.

## Table of Contents
- [Backend Environment Variables](#backend-environment-variables)
- [Frontend Environment Variables](#frontend-environment-variables)
- [HubSpot OAuth Setup](#hubspot-oauth-setup)
- [GitHub App Setup](#github-app-setup)
- [Encryption Key Generation](#encryption-key-generation)
- [Database Setup](#database-setup)
- [Quick Start](#quick-start)

---

## Backend Environment Variables

Create a `.env` file in the `auditor_geo/backend/` directory:

```bash
# Database Configuration
DATABASE_URL=postgresql://auditor:password@localhost:5432/auditor_db
# For development with SQLite:
# DATABASE_URL=sqlite:///./auditor.db

# Redis Configuration
REDIS_URL=redis://localhost:6379/0

# API Keys (Required)
GEMINI_API_KEY=your_gemini_api_key_here
NVIDIA_API_KEY=your_nvidia_api_key_here
GOOGLE_PAGESPEED_API_KEY=your_pagespeed_api_key_here

# Application Settings
SECRET_KEY=your_secret_key_here_min_32_chars
DEBUG=False

# HubSpot Integration (Required for HubSpot features)
HUBSPOT_CLIENT_ID=your_hubspot_client_id
HUBSPOT_CLIENT_SECRET=your_hubspot_client_secret
HUBSPOT_REDIRECT_URI=http://localhost:3000/integrations

# GitHub Integration (Required for GitHub features)
GITHUB_CLIENT_ID=your_github_app_client_id
GITHUB_CLIENT_SECRET=your_github_app_client_secret
GITHUB_APP_ID=your_github_app_id
GITHUB_PRIVATE_KEY_PATH=path/to/private-key.pem

# Encryption (Required for OAuth tokens)
ENCRYPTION_KEY=your_32_byte_encryption_key_base64_encoded

# Optional: Google API for additional features
GOOGLE_API_KEY=your_google_api_key
```

### Required Variables

The following variables are **required** and the application will fail to start without them:

- `DATABASE_URL` - Database connection string
- `HUBSPOT_CLIENT_ID` - HubSpot OAuth client ID
- `HUBSPOT_CLIENT_SECRET` - HubSpot OAuth client secret
- `GITHUB_CLIENT_ID` - GitHub App client ID
- `GITHUB_CLIENT_SECRET` - GitHub App client secret
- `ENCRYPTION_KEY` - 32-byte key for encrypting OAuth tokens

### Optional Variables

These variables are optional but recommended:

- `GOOGLE_PAGESPEED_API_KEY` - For PageSpeed Insights integration
- `NVIDIA_API_KEY` - For NVIDIA LLM features
- `GOOGLE_API_KEY` - For additional Google services

---

## Frontend Environment Variables

Create a `.env.local` file in the `auditor_geo/frontend/` directory:

```bash
# Backend API URL
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000

# Auth0 Configuration
AUTH0_SECRET=your_auth0_secret_min_32_chars
AUTH0_BASE_URL=http://localhost:3000
AUTH0_ISSUER_BASE_URL=https://your-tenant.auth0.com
AUTH0_CLIENT_ID=your_auth0_client_id
AUTH0_CLIENT_SECRET=your_auth0_client_secret

# Application Base URL
APP_BASE_URL=http://localhost:3000
```

### Production Frontend Variables

For production, update the URLs:

```bash
NEXT_PUBLIC_BACKEND_URL=https://api.yourdomain.com
AUTH0_BASE_URL=https://yourdomain.com
APP_BASE_URL=https://yourdomain.com
```

---

## HubSpot OAuth Setup

### 1. Create a HubSpot App

1. Go to [HubSpot Developer Portal](https://developers.hubspot.com/)
2. Click "Create app"
3. Fill in app details:
   - **App name:** Auditor GEO
   - **Description:** SEO/GEO auditing platform with HubSpot integration

### 2. Configure OAuth

1. In your app settings, go to "Auth" tab
2. Set **Redirect URL:**
   - Development: `http://localhost:3000/integrations`
   - Production: `https://yourdomain.com/integrations`

3. Select required **Scopes:**
   - `content` - Read and write CMS content
   - `cms.pages.read` - Read CMS pages
   - `cms.pages.write` - Update CMS pages

### 3. Get Credentials

1. Copy **Client ID** → `HUBSPOT_CLIENT_ID`
2. Copy **Client Secret** → `HUBSPOT_CLIENT_SECRET`
3. Add to backend `.env` file

### 4. Test Connection

```bash
# Start backend
cd backend
python main.py

# Start frontend
cd frontend
npm run dev

# Navigate to http://localhost:3000/integrations
# Click "Connect HubSpot" and authorize
```

---

## GitHub App Setup

### 1. Create a GitHub App

1. Go to GitHub Settings → Developer settings → GitHub Apps
2. Click "New GitHub App"
3. Fill in details:
   - **GitHub App name:** Auditor GEO
   - **Homepage URL:** `https://yourdomain.com`
   - **Callback URL:** `http://localhost:3000/integrations` (dev)
   - **Webhook URL:** Leave empty for now

### 2. Set Permissions

**Repository permissions:**
- Contents: Read & Write
- Pull requests: Read & Write
- Issues: Read & Write

### 3. Generate Private Key

1. Scroll to "Private keys" section
2. Click "Generate a private key"
3. Save the `.pem` file securely
4. Set path in `GITHUB_PRIVATE_KEY_PATH`

### 4. Get Credentials

1. Copy **App ID** → `GITHUB_APP_ID`
2. Copy **Client ID** → `GITHUB_CLIENT_ID`
3. Copy **Client Secret** → `GITHUB_CLIENT_SECRET`

---

## Encryption Key Generation

OAuth tokens are encrypted before storage. Generate a secure encryption key:

### Using Python

```python
import secrets
import base64

# Generate 32 random bytes
key = secrets.token_bytes(32)

# Encode as base64 for easy storage
encoded_key = base64.b64encode(key).decode('utf-8')

print(f"ENCRYPTION_KEY={encoded_key}")
```

### Using OpenSSL

```bash
openssl rand -base64 32
```

### Using Node.js

```javascript
const crypto = require('crypto');
const key = crypto.randomBytes(32).toString('base64');
console.log(`ENCRYPTION_KEY=${key}`);
```

Add the generated key to your backend `.env` file:

```bash
ENCRYPTION_KEY=your_generated_key_here
```

---

## Database Setup

### PostgreSQL (Production)

1. **Install PostgreSQL:**
   ```bash
   # Ubuntu/Debian
   sudo apt-get install postgresql postgresql-contrib
   
   # macOS
   brew install postgresql
   ```

2. **Create Database:**
   ```bash
   sudo -u postgres psql
   CREATE DATABASE auditor_db;
   CREATE USER auditor WITH PASSWORD 'your_password';
   GRANT ALL PRIVILEGES ON DATABASE auditor_db TO auditor;
   \q
   ```

3. **Update DATABASE_URL:**
   ```bash
   DATABASE_URL=postgresql://auditor:your_password@localhost:5432/auditor_db
   ```

### SQLite (Development)

For quick development setup:

```bash
DATABASE_URL=sqlite:///./auditor.db
```

### Run Migrations

```bash
cd backend
alembic upgrade head
```

---

## Quick Start

### Using Docker (Recommended)

```bash
# Clone repository
git clone <repository-url>
cd auditor_geo

# Copy environment files
cp backend/.env.example backend/.env
cp frontend/.env.local.example frontend/.env.local

# Edit .env files with your credentials
nano backend/.env
nano frontend/.env.local

# Start all services
docker-compose up --build

# Access application
# Frontend: http://localhost:3000
# Backend: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### Manual Setup

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
python main.py
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

**Redis (required for background tasks):**
```bash
# Ubuntu/Debian
sudo apt-get install redis-server
sudo systemctl start redis

# macOS
brew install redis
brew services start redis

# Windows
# Download from https://redis.io/download
```

**Celery Worker (for async tasks):**
```bash
cd backend
celery -A app.workers.tasks worker --loglevel=info
```

---

## Verification Checklist

After setup, verify everything works:

- [ ] Backend starts without errors
- [ ] Frontend loads at http://localhost:3000
- [ ] Can create an audit
- [ ] HubSpot integration visible in /integrations
- [ ] GitHub integration visible in /integrations
- [ ] OAuth flows work (test by connecting)
- [ ] Light/dark theme toggle works
- [ ] Database migrations applied successfully

---

## Troubleshooting

### "Missing required environment variable"

**Solution:** Check backend logs for specific variable name and add it to `.env`

### "HubSpot OAuth fails"

**Solutions:**
1. Verify redirect URI matches exactly in HubSpot app settings
2. Check HUBSPOT_CLIENT_ID and HUBSPOT_CLIENT_SECRET are correct
3. Ensure HTTPS in production (HubSpot requires HTTPS for OAuth)

### "Database connection failed"

**Solutions:**
1. Verify PostgreSQL is running: `sudo systemctl status postgresql`
2. Check DATABASE_URL format is correct
3. Ensure database exists: `psql -U auditor -d auditor_db`

### "Encryption key error"

**Solution:** Generate a new 32-byte key using the methods above

### "Redis connection refused"

**Solutions:**
1. Start Redis: `sudo systemctl start redis` or `brew services start redis`
2. Check REDIS_URL is correct (default: `redis://localhost:6379/0`)

---

## Production Deployment

### Additional Requirements

1. **HTTPS Required:**
   - HubSpot OAuth requires HTTPS
   - Use Let's Encrypt or similar for SSL certificates

2. **Environment Variables:**
   - Update all URLs to production domains
   - Use strong, unique secrets
   - Never commit `.env` files to version control

3. **Database:**
   - Use PostgreSQL (not SQLite)
   - Enable connection pooling
   - Set up regular backups

4. **Security:**
   - Set `DEBUG=False`
   - Use firewall rules
   - Enable rate limiting
   - Regular security updates

5. **Monitoring:**
   - Set up error tracking (Sentry, etc.)
   - Monitor API usage
   - Track OAuth token expiration

---

## Support

For issues or questions:
- Check logs: `docker-compose logs -f backend`
- Review API docs: http://localhost:8000/docs
- Verify environment variables are set correctly

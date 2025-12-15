# Testing Guide

Comprehensive guide for testing Auditor GEO features, integrations, and production readiness.

## Table of Contents
- [Quick Test Checklist](#quick-test-checklist)
- [Light/Dark Theme Testing](#lightdark-theme-testing)
- [HubSpot Integration Testing](#hubspot-integration-testing)
- [GitHub Integration Testing](#github-integration-testing)
- [API Endpoint Testing](#api-endpoint-testing)
- [Cross-Browser Testing](#cross-browser-testing)
- [Performance Testing](#performance-testing)

---

## Quick Test Checklist

Use this checklist to verify production readiness:

### Core Functionality
- [ ] Application starts without errors
- [ ] Can create a new audit
- [ ] Audit completes successfully
- [ ] Reports generate correctly (PDF, JSON, Markdown)
- [ ] Dashboard displays audit results

### Theme Testing
- [ ] Light theme works on all pages
- [ ] Dark theme works on all pages
- [ ] Theme toggle persists across navigation
- [ ] Text is readable in both themes
- [ ] Charts render correctly in both themes

### Integrations
- [ ] HubSpot integration visible
- [ ] HubSpot OAuth flow works
- [ ] GitHub integration visible
- [ ] GitHub OAuth flow works
- [ ] Can disconnect integrations

### User Experience
- [ ] Navigation menu works
- [ ] Forms validate correctly
- [ ] Error messages are user-friendly
- [ ] Loading states display properly
- [ ] Success confirmations appear

---

## Light/Dark Theme Testing

### Test All Pages

Visit each page and toggle between light and dark themes:

1. **Home Page** (`/`)
   - [ ] Navbar colors correct
   - [ ] Hero section readable
   - [ ] Search bar visible
   - [ ] Feature cards styled correctly
   - [ ] Recent audits section (if logged in)

2. **Audits List** (`/audits`)
   - [ ] Header and filters visible
   - [ ] Audit cards readable
   - [ ] Status badges colored correctly
   - [ ] Empty state displays properly

3. **Audit Detail** (`/audits/[id]`)
   - [ ] Stats cards readable
   - [ ] Charts render correctly
   - [ ] Issues list visible
   - [ ] Integration cards styled properly
   - [ ] PageSpeed section readable

4. **Settings** (`/settings`)
   - [ ] Profile section visible
   - [ ] Theme selector works
   - [ ] Notification toggles visible
   - [ ] Form inputs readable

5. **Content Editor** (`/tools/content-editor`)
   - [ ] Editor area visible
   - [ ] Analysis panel readable
   - [ ] Score display correct
   - [ ] Suggestions styled properly

6. **Integrations** (`/integrations`)
   - [ ] Integration cards visible
   - [ ] Connection status clear
   - [ ] Action buttons styled correctly

### Test Components

1. **Charts:**
   - [ ] Score history chart
   - [ ] Keyword gap chart
   - [ ] Issues heatmap
   - [ ] Core Web Vitals chart

2. **Dialogs:**
   - [ ] GitHub integration dialog
   - [ ] HubSpot integration dialog
   - [ ] Confirmation dialogs

### Automated Theme Test

```bash
# Run visual regression tests (if configured)
npm run test:visual

# Or manually test with browser DevTools
# 1. Open DevTools (F12)
# 2. Toggle theme in settings
# 3. Check for hardcoded colors in Elements tab
# 4. Look for: text-white, bg-black, border-white/10
```

---

## HubSpot Integration Testing

### Prerequisites

1. HubSpot account with CMS Hub
2. Test portal with sample pages
3. OAuth app configured (see ENVIRONMENT_SETUP.md)

### Test OAuth Flow

1. **Navigate to Integrations:**
   ```
   http://localhost:3000/integrations
   ```

2. **Connect HubSpot:**
   - [ ] Click "Connect HubSpot" button
   - [ ] Redirects to HubSpot OAuth page
   - [ ] Can authorize the app
   - [ ] Redirects back to integrations page
   - [ ] Shows "Connected" status
   - [ ] Displays portal ID

3. **Verify Backend:**
   ```bash
   # Check database for connection
   psql -U auditor -d auditor_db
   SELECT * FROM hubspot_connections;
   
   # Should show:
   # - portal_id
   # - encrypted access_token
   # - encrypted refresh_token
   # - expires_at timestamp
   ```

### Test Page Syncing

1. **Sync Pages:**
   ```bash
   # Via API
   curl -X POST http://localhost:8000/api/hubspot/sync/{connection_id}
   
   # Or via frontend (if implemented)
   # Click "Sync Pages" button in integrations page
   ```

2. **Verify Pages:**
   ```bash
   # Check database
   SELECT * FROM hubspot_pages WHERE connection_id = 'your_connection_id';
   
   # Should show:
   # - hubspot_id
   # - url
   # - title
   # - html_title
   # - meta_description
   # - last_synced_at
   ```

### Test Recommendations

1. **Create an Audit:**
   - Run audit on a website
   - Wait for completion

2. **View Recommendations:**
   ```bash
   # Via API
   curl http://localhost:8000/api/hubspot/recommendations/{audit_id}
   
   # Should return:
   # - List of recommendations
   # - Each with: field, current_value, recommended_value
   # - Priority and auto_fixable flags
   ```

3. **In Audit Detail Page:**
   - [ ] Open HubSpot integration dialog
   - [ ] Select portal/connection
   - [ ] Recommendations load
   - [ ] Can select recommendations to apply
   - [ ] Shows current vs recommended values

### Test Apply Changes

1. **Apply Single Recommendation:**
   - [ ] Select a recommendation
   - [ ] Click "Apply"
   - [ ] Shows loading state
   - [ ] Displays success message
   - [ ] Updates HubSpot page

2. **Apply Multiple Recommendations:**
   - [ ] Select multiple recommendations
   - [ ] Click "Apply Selected"
   - [ ] Shows progress
   - [ ] Displays results (success/failed count)
   - [ ] Lists any errors

3. **Verify in HubSpot:**
   - Log into HubSpot CMS
   - Check the updated page
   - Verify changes applied correctly

### Test Error Handling

1. **Expired Token:**
   ```bash
   # Manually expire token in database
   UPDATE hubspot_connections 
   SET expires_at = NOW() - INTERVAL '1 hour'
   WHERE id = 'your_connection_id';
   
   # Try to sync pages
   # Should automatically refresh token
   ```

2. **Invalid Page ID:**
   ```bash
   # Try to apply change to non-existent page
   curl -X POST http://localhost:8000/api/hubspot/apply-recommendations \
     -H "Content-Type: application/json" \
     -d '{"audit_id": 1, "recommendations": [{"hubspot_page_id": "invalid"}]}'
   
   # Should return error message
   ```

3. **Network Failure:**
   - Disconnect internet
   - Try to sync pages
   - Should show user-friendly error

### Test Disconnect

1. **Disconnect HubSpot:**
   - [ ] Click "Disconnect" button
   - [ ] Shows confirmation dialog
   - [ ] Confirms disconnect
   - [ ] Removes connection from database
   - [ ] Revokes OAuth token (if possible)

---

## GitHub Integration Testing

### Test OAuth Flow

1. **Connect GitHub:**
   - [ ] Navigate to /integrations
   - [ ] Click "Connect GitHub"
   - [ ] Authorize GitHub App
   - [ ] Redirects back successfully
   - [ ] Shows connected status

### Test Auto-Fix

1. **In Audit Detail:**
   - [ ] Open GitHub integration dialog
   - [ ] Select repository
   - [ ] View suggested fixes
   - [ ] Apply fixes
   - [ ] Creates pull request
   - [ ] PR contains correct changes

2. **Verify PR:**
   - Check GitHub repository
   - PR should have:
     - [ ] Descriptive title
     - [ ] List of fixes applied
     - [ ] Link back to audit
     - [ ] Correct file changes

---

## API Endpoint Testing

### Using cURL

```bash
# Health check
curl http://localhost:8000/health

# Create audit
curl -X POST http://localhost:8000/api/audits \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "user_email": "test@example.com"}'

# Get audit status
curl http://localhost:8000/api/audits/{audit_id}

# HubSpot auth URL
curl http://localhost:8000/api/hubspot/auth-url

# HubSpot connections
curl http://localhost:8000/api/hubspot/connections

# GitHub repositories
curl http://localhost:8000/api/github/repos
```

### Using Postman

1. Import API collection (if available)
2. Set environment variables
3. Test each endpoint
4. Verify responses

### Using FastAPI Docs

1. Navigate to http://localhost:8000/docs
2. Test endpoints interactively
3. View request/response schemas
4. Check error responses

---

## Cross-Browser Testing

### Browsers to Test

- [ ] Chrome (latest)
- [ ] Firefox (latest)
- [ ] Safari (latest)
- [ ] Edge (latest)
- [ ] Mobile Safari (iOS)
- [ ] Chrome Mobile (Android)

### Test Cases

For each browser:

1. **Basic Functionality:**
   - [ ] Pages load correctly
   - [ ] Navigation works
   - [ ] Forms submit
   - [ ] Buttons clickable

2. **Theme Toggle:**
   - [ ] Can switch themes
   - [ ] Theme persists
   - [ ] Colors render correctly

3. **Integrations:**
   - [ ] OAuth flows work
   - [ ] Dialogs open/close
   - [ ] Data loads

4. **Responsive Design:**
   - [ ] Mobile view (< 768px)
   - [ ] Tablet view (768px - 1024px)
   - [ ] Desktop view (> 1024px)

### Browser-Specific Issues

**Safari:**
- Check date/time formatting
- Verify fetch API calls
- Test localStorage

**Firefox:**
- Check CSS grid layouts
- Verify WebSocket connections
- Test file uploads

**Mobile:**
- Touch interactions
- Viewport scaling
- Performance on slower devices

---

## Performance Testing

### Lighthouse Audit

```bash
# Install Lighthouse
npm install -g lighthouse

# Run audit
lighthouse http://localhost:3000 --view

# Check scores:
# - Performance: > 90
# - Accessibility: > 90
# - Best Practices: > 90
# - SEO: > 90
```

### Load Testing

```bash
# Install Apache Bench
sudo apt-get install apache2-utils

# Test backend
ab -n 1000 -c 10 http://localhost:8000/health

# Test frontend
ab -n 100 -c 5 http://localhost:3000/
```

### Database Performance

```sql
-- Check slow queries
SELECT * FROM pg_stat_statements 
ORDER BY mean_exec_time DESC 
LIMIT 10;

-- Check table sizes
SELECT 
  schemaname,
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

---

## Automated Testing

### Backend Tests

```bash
cd backend
pytest tests/ -v

# With coverage
pytest tests/ --cov=app --cov-report=html

# Specific test file
pytest tests/test_hubspot.py -v
```

### Frontend Tests

```bash
cd frontend
npm test

# With coverage
npm test -- --coverage

# E2E tests (if configured)
npm run test:e2e
```

---

## Production Smoke Tests

After deploying to production:

1. **Health Checks:**
   ```bash
   curl https://api.yourdomain.com/health
   curl https://yourdomain.com
   ```

2. **Create Test Audit:**
   - Use a test URL
   - Verify completion
   - Check report generation

3. **Test Integrations:**
   - Connect HubSpot (use test account)
   - Connect GitHub (use test repo)
   - Verify OAuth flows with HTTPS

4. **Monitor Logs:**
   ```bash
   # Backend logs
   tail -f /var/log/auditor-geo/backend.log
   
   # Frontend logs (if applicable)
   tail -f /var/log/auditor-geo/frontend.log
   ```

5. **Check Metrics:**
   - Response times
   - Error rates
   - Database connections
   - Memory usage

---

## Troubleshooting Tests

### Tests Fail Locally

1. Check environment variables are set
2. Verify database is running
3. Ensure Redis is running
4. Check for port conflicts

### OAuth Tests Fail

1. Verify redirect URIs match exactly
2. Check client IDs and secrets
3. Ensure HTTPS in production
4. Clear browser cookies/cache

### Theme Tests Fail

1. Check for hardcoded colors
2. Verify CSS variables are defined
3. Test in incognito mode
4. Clear localStorage

---

## Test Reporting

Document test results:

```markdown
## Test Report - [Date]

### Environment
- OS: [Operating System]
- Browser: [Browser Version]
- Backend: [Version]
- Frontend: [Version]

### Results
- Total Tests: X
- Passed: Y
- Failed: Z
- Skipped: W

### Failed Tests
1. [Test Name]
   - Expected: [Expected Result]
   - Actual: [Actual Result]
   - Steps to Reproduce: [Steps]

### Notes
- [Any additional observations]
```

---

## Continuous Testing

Set up automated testing in CI/CD:

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run backend tests
        run: |
          cd backend
          pip install -r requirements.txt
          pytest tests/

  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run frontend tests
        run: |
          cd frontend
          npm install
          npm test
```

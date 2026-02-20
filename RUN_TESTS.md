# How to Run Tests

Complete guide for running all tests in the Auditor GEO platform.

## Quick Start

### Fast Validation Commands

```bash
cd auditor_geo
pnpm --dir frontend lint
pnpm --dir frontend run format:check
pnpm --dir frontend run type-check
pnpm --dir frontend test:ci
pnpm --dir frontend build
python -m ruff check backend/app backend/tests
python -m black --check backend
python -m isort --check-only backend
python -m mypy backend/app --ignore-missing-imports --show-error-codes
python -m bandit -r backend/app -q
python -m pip_audit -r backend/requirements.txt
pytest -q backend/tests -m "not integration and not live"
# External smoke (strict release gate)
SMOKE_BASE_URL=https://your-staging-or-prod-url \
SMOKE_BEARER_TOKEN=optional-token \
pytest -q backend/tests/test_release_smoke_external.py
```

These commands validate:
- ✓ Frontend lint/format/types/tests/build
- ✓ Backend quality/security checks
- ✓ Backend deterministic local suite (no integration/live)
- ✓ External smoke availability on critical endpoints

---

## Preproduction Release Gate (No Deploy)

Use this exact sequence before any staging/production promotion:

```bash
cd auditor_geo
pnpm --dir frontend lint
pnpm --dir frontend run format:check
pnpm --dir frontend run type-check
pnpm --dir frontend test:ci
STRICT_BUILD=1 pnpm --dir frontend build
python -m ruff check backend/app
python -m mypy backend/app --ignore-missing-imports --show-error-codes
python -m bandit -r backend/app -q
pytest -q backend/tests -m "not integration and not live"
SMOKE_BASE_URL=https://your-staging-or-prod-url pytest -q backend/tests/test_release_smoke_external.py
```

Blocking rules:
- `Release blocked` if any command above fails.
- `Release blocked` if smoke suite fails on `/health`, `/docs`, `/api/webhooks/health`, or `/api/geo/content-templates`.
- `No deploy` until all commands are green.

---

## Backend Tests

### Using pytest (Recommended)

```bash
cd auditor_geo/backend

# Activate virtual environment
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html
# View coverage: open htmlcov/index.html

# Run specific test file
pytest tests/test_audits.py -v
pytest tests/test_hubspot.py -v

# Run tests matching pattern
pytest tests/ -k "hubspot" -v
pytest tests/ -k "oauth" -v

# Run with detailed output
pytest tests/ -vv -s

# Stop on first failure
pytest tests/ -x

# Run in parallel (faster)
pytest tests/ -n auto
```

### Using Docker

```bash
# Run all backend tests
docker-compose exec backend pytest tests/ -v

# Run with coverage
docker-compose exec backend pytest tests/ --cov=app --cov-report=html

# Run specific test
docker-compose exec backend pytest tests/test_audits.py -v

# Run during build (without starting services)
docker-compose run --rm backend pytest tests/
```

### Test Structure

```
backend/tests/
├── conftest.py              # Shared fixtures
├── test_audits.py          # Audit functionality
├── test_audits_api.py      # Audit API endpoints
├── test_hubspot.py         # HubSpot integration (if exists)
├── test_github.py          # GitHub integration (if exists)
└── test_database.py        # Database operations (if exists)
```

---

## Frontend Tests

### Using npm/jest

```bash
cd auditor_geo/frontend

# Run all tests
npm test

# Run with coverage
npm test -- --coverage

# Run in watch mode (auto-rerun on changes)
npm test -- --watch

# Run specific test file
npm test -- score-history-chart.test.tsx
npm test -- hubspot-integration.test.tsx

# Run tests matching pattern
npm test -- --testNamePattern="theme"

# Update snapshots
npm test -- -u

# Run with verbose output
npm test -- --verbose
```

### Using Docker

```bash
# Run all frontend tests
docker-compose exec frontend npm test

# Run with coverage
docker-compose exec frontend npm test -- --coverage

# Run during build
docker-compose run --rm frontend npm test
```

### Test Structure

```
frontend/
├── __tests__/              # Test files
│   ├── components/
│   │   ├── score-history-chart.test.tsx
│   │   └── hubspot-integration.test.tsx
│   └── pages/
│       └── home.test.tsx
└── jest.config.js          # Jest configuration
```

---

## Integration Tests

### Manual Integration Testing

**1. Start all services:**
```bash
docker-compose up --build
```

**2. Test HubSpot Integration:**
```bash
# Get auth URL
curl http://localhost:8000/api/hubspot/auth-url

# Check connections
curl http://localhost:8000/api/hubspot/connections

# Test page sync (after connecting)
curl -X POST http://localhost:8000/api/hubspot/sync/{connection_id}

# Get recommendations
curl http://localhost:8000/api/hubspot/recommendations/{audit_id}
```

**3. Test GitHub Integration:**
```bash
# Check repositories
curl http://localhost:8000/api/github/repos

# Test auto-fix
curl -X POST http://localhost:8000/api/github/apply-fixes \
  -H "Content-Type: application/json" \
  -d '{"audit_id": 1, "repo": "owner/repo"}'
```

### Automated Integration Tests

```bash
# Backend integration tests
cd backend
pytest tests/integration/ -v

# Frontend E2E tests (if configured)
cd frontend
npm run test:e2e
```

---

## API Tests

### Using cURL

```bash
# Health check
curl http://localhost:8000/health

# Create audit
curl -X POST http://localhost:8000/api/audits \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "user_email": "test@example.com"
  }'

# Get audit
curl http://localhost:8000/api/audits/1

# List audits
curl http://localhost:8000/api/audits

# HubSpot endpoints
curl http://localhost:8000/api/hubspot/auth-url
curl http://localhost:8000/api/hubspot/connections
```

### Using Postman

1. Import API collection (if available)
2. Set environment variables:
   - `base_url`: http://localhost:8000
   - `frontend_url`: http://localhost:3000
3. Run collection tests

### Using FastAPI Docs

1. Navigate to http://localhost:8000/docs
2. Click "Try it out" on any endpoint
3. Fill in parameters
4. Click "Execute"
5. View response

---

## Theme Tests

### Manual Theme Testing

**Test each page in both themes:**

```bash
# 1. Start application
docker-compose up

# 2. Open browser
open http://localhost:3000

# 3. Navigate to Settings
open http://localhost:3000/settings

# 4. Toggle between Light/Dark/System

# 5. Test each page:
- Home (/)
- Audits list (/audits)
- Audit detail (/audits/[id])
- Settings (/settings)
- Content editor (/tools/content-editor)
- Integrations (/integrations)

# 6. Verify for each page:
✓ Text is readable
✓ Backgrounds are appropriate
✓ Borders are visible
✓ Charts render correctly
✓ Buttons are styled properly
✓ Forms are usable
```

### Automated Theme Tests

```bash
# Visual regression tests (if configured)
cd frontend
npm run test:visual

# Accessibility tests
npm run test:a11y
```

---

## Performance Tests

### Lighthouse

```bash
# Install Lighthouse
npm install -g lighthouse

# Run audit on frontend
lighthouse http://localhost:3000 --view

# Run on specific page
lighthouse http://localhost:3000/audits --view

# Save report
lighthouse http://localhost:3000 --output html --output-path ./lighthouse-report.html
```

### Load Testing

```bash
# Install Apache Bench
sudo apt-get install apache2-utils  # Linux
brew install ab                      # Mac

# Test backend
ab -n 1000 -c 10 http://localhost:8000/health

# Test frontend
ab -n 100 -c 5 http://localhost:3000/

# Test specific endpoint
ab -n 500 -c 20 http://localhost:8000/api/audits
```

### Database Performance

```bash
# Connect to database
docker-compose exec db psql -U auditor -d auditor_db

# Check slow queries
SELECT * FROM pg_stat_statements 
ORDER BY mean_exec_time DESC 
LIMIT 10;

# Check table sizes
SELECT 
  schemaname,
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

---

## Cross-Browser Tests

### Manual Testing

Test on each browser:
- Chrome (latest)
- Firefox (latest)
- Safari (latest)
- Edge (latest)
- Mobile Safari (iOS)
- Chrome Mobile (Android)

**For each browser:**
1. Open http://localhost:3000
2. Test navigation
3. Toggle theme
4. Create an audit
5. Test integrations
6. Check responsive design

### Automated Cross-Browser

```bash
# Using Playwright (if configured)
cd frontend
npm run test:browsers

# Using Selenium (if configured)
cd backend
pytest tests/selenium/ -v
```

---

## Continuous Integration

### GitHub Actions

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.11
      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
      - name: Run tests
        run: |
          cd backend
          pytest tests/ -v

  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Node
        uses: actions/setup-node@v2
        with:
          node-version: 18
      - name: Install dependencies
        run: |
          cd frontend
          npm install
      - name: Run tests
        run: |
          cd frontend
          npm test
```

---

## Test Coverage

### Backend Coverage

```bash
cd backend

# Generate coverage report
pytest tests/ --cov=app --cov-report=html --cov-report=term

# View HTML report
open htmlcov/index.html  # Mac
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows

# Check coverage percentage
pytest tests/ --cov=app --cov-report=term-missing
```

### Frontend Coverage

```bash
cd frontend

# Generate coverage report
npm test -- --coverage

# View HTML report
open coverage/lcov-report/index.html  # Mac
xdg-open coverage/lcov-report/index.html  # Linux
start coverage/lcov-report/index.html  # Windows
```

---

## Troubleshooting Tests

### Tests Fail to Start

**Problem:** `pytest: command not found`
```bash
# Solution: Install pytest
pip install pytest pytest-asyncio pytest-cov
```

**Problem:** `npm test: command not found`
```bash
# Solution: Install dependencies
cd frontend
npm install
```

### Database Tests Fail

**Problem:** Database connection errors
```bash
# Solution: Ensure database is running
docker-compose up -d db

# Or start PostgreSQL locally
sudo systemctl start postgresql  # Linux
brew services start postgresql   # Mac
```

### Redis Tests Fail

**Problem:** Redis connection errors
```bash
# Solution: Ensure Redis is running
docker-compose up -d redis

# Or start Redis locally
sudo systemctl start redis  # Linux
brew services start redis   # Mac
```

### Import Errors

**Problem:** `ModuleNotFoundError`
```bash
# Solution: Install dependencies
cd backend
pip install -r requirements.txt

cd frontend
npm install
```

---

## Test Checklist

Before considering production-ready:

### Backend Tests
- [ ] All pytest tests pass
- [ ] Coverage > 80%
- [ ] API endpoints respond correctly
- [ ] Database operations work
- [ ] OAuth flows function
- [ ] Token encryption works

### Frontend Tests
- [ ] All jest tests pass
- [ ] Coverage > 80%
- [ ] Pages render correctly
- [ ] Components work in isolation
- [ ] Theme switching works
- [ ] Forms validate properly

### Integration Tests
- [ ] HubSpot OAuth works
- [ ] GitHub OAuth works
- [ ] Can create audits
- [ ] Reports generate correctly
- [ ] Integrations connect successfully

### Manual Tests
- [ ] Light theme on all pages
- [ ] Dark theme on all pages
- [ ] Mobile responsive
- [ ] Cross-browser compatible
- [ ] Performance acceptable
- [ ] No console errors

---

## Next Steps

After running tests:

1. **Review Results:**
   - Check test output
   - Review coverage reports
   - Identify failing tests

2. **Fix Issues:**
   - Debug failing tests
   - Improve coverage
   - Fix bugs

3. **Document:**
   - Update test documentation
   - Add new test cases
   - Document known issues

4. **Deploy:**
   - Run tests in CI/CD
   - Deploy to staging
   - Run smoke tests
   - Deploy to production

---

## Support

If tests fail:
1. Check logs: `docker-compose logs -f`
2. Review error messages
3. Verify environment variables
4. Ensure all services are running
5. Check documentation: TESTING_GUIDE.md

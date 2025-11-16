# SEO/GEO Auditor - Setup Instructions

## 🚀 Quick Start

### 1. Start Development Servers

Simply run:
```bash
start-dev.bat
```

This will start both backend and frontend servers automatically.

### 2. Access the Application

- **Frontend Dashboard**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

## 📋 Manual Setup

### Backend Setup

```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup

```bash
cd frontend
npm install  # First time only
npm run dev
```

## 🎯 Features

### Dashboard View
- Overview of all audits
- Create new audits
- Monitor audit progress in real-time

### Audit Analysis View
- **Dashboard Tab**: Performance metrics with radar charts and competitor comparison
- **Pages Tab**: Detailed analysis of each subpage with individual scores
- **Competitors Tab**: Comparison with competitor sites
- **Keywords Tab**: Keyword analysis and search results

### Metrics Tracked
- H1 Score
- Structure Score
- Content Score
- E-E-A-T Score
- Schema Score
- Overall Score

### Issue Severity Levels
- Critical (Red)
- High (Orange)
- Medium (Yellow)
- Low (Gray)

## 🎨 Design

Minimalist black and white theme with:
- Clean, modern interface
- Smooth transitions
- Responsive charts and graphs
- Dynamic data visualization

## 📊 Data Flow

1. User submits URL for audit
2. Backend crawls and analyzes pages
3. Generates comprehensive report with:
   - Page-by-page analysis
   - Competitor comparison
   - Keyword insights
   - Fix recommendations
4. Frontend displays interactive dashboard
5. PDF report available for download

## 🔧 Configuration

### Backend (.env)
- `DATABASE_URL`: Database connection
- `GEMINI_API_KEY`: AI model API key
- `GOOGLE_API_KEY`: Google Search API
- `CSE_ID`: Custom Search Engine ID

### Frontend (.env.local)
- `NEXT_PUBLIC_API_URL`: Backend API URL (default: http://localhost:8000)

## 📝 Notes

- Audits run asynchronously in the background
- Progress updates every 3 seconds
- All data persists in SQLite database
- JSON reports saved in `reports/audit_{id}/` directory

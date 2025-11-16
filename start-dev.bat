@echo off
echo Starting SEO/GEO Auditor Development Servers...
echo.

start "Backend Server" cmd /k "cd backend && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
timeout /t 3 /nobreak > nul

start "Frontend Server" cmd /k "cd frontend && pnpm run dev"

echo.
echo Servers starting...
echo Backend: http://localhost:8000
echo Frontend: http://localhost:3000
echo API Docs: http://localhost:8000/docs
echo.

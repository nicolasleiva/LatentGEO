@echo off
REM Production Ready Test Script for Windows
REM Tests core functionality of Auditor GEO

echo Testing Auditor GEO Production Readiness
echo ==========================================
echo.

set PASSED=0
set FAILED=0

echo 1. Checking Services
echo -------------------

REM Check Backend
curl -s -o nul -w "%%{http_code}" http://localhost:8000/health > nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Backend on port 8000... [32mRunning[0m
    set /a PASSED+=1
) else (
    echo Backend on port 8000... [31mNot running[0m
    set /a FAILED+=1
)

REM Check Frontend
curl -s -o nul http://localhost:3000 > nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Frontend on port 3000... [32mRunning[0m
    set /a PASSED+=1
) else (
    echo Frontend on port 3000... [31mNot running[0m
    set /a FAILED+=1
)

echo.
echo 2. Testing Backend Endpoints
echo ----------------------------

curl -s -o nul -w "%%{http_code}" http://localhost:8000/health | findstr "200" > nul
if %ERRORLEVEL% EQU 0 (
    echo Health Check... [32mPASS[0m
    set /a PASSED+=1
) else (
    echo Health Check... [31mFAIL[0m
    set /a FAILED+=1
)

curl -s -o nul -w "%%{http_code}" http://localhost:8000/docs | findstr "200" > nul
if %ERRORLEVEL% EQU 0 (
    echo API Docs... [32mPASS[0m
    set /a PASSED+=1
) else (
    echo API Docs... [31mFAIL[0m
    set /a FAILED+=1
)

curl -s -o nul -w "%%{http_code}" http://localhost:8000/api/hubspot/auth-url | findstr "200" > nul
if %ERRORLEVEL% EQU 0 (
    echo HubSpot Auth URL... [32mPASS[0m
    set /a PASSED+=1
) else (
    echo HubSpot Auth URL... [31mFAIL[0m
    set /a FAILED+=1
)

echo.
echo 3. Testing Frontend Pages
echo ------------------------

curl -s -o nul -w "%%{http_code}" http://localhost:3000 | findstr "200" > nul
if %ERRORLEVEL% EQU 0 (
    echo Home Page... [32mPASS[0m
    set /a PASSED+=1
) else (
    echo Home Page... [31mFAIL[0m
    set /a FAILED+=1
)

curl -s -o nul -w "%%{http_code}" http://localhost:3000/integrations | findstr "200" > nul
if %ERRORLEVEL% EQU 0 (
    echo Integrations Page... [32mPASS[0m
    set /a PASSED+=1
) else (
    echo Integrations Page... [31mFAIL[0m
    set /a FAILED+=1
)

echo.
echo 4. Checking Environment Files
echo -----------------------------

if exist "backend\.env" (
    echo Backend .env exists... [32mPASS[0m
    set /a PASSED+=1
) else (
    echo Backend .env exists... [31mFAIL[0m
    set /a FAILED+=1
)

if exist "frontend\.env.local" (
    echo Frontend .env.local exists... [32mPASS[0m
    set /a PASSED+=1
) else (
    echo Frontend .env.local exists... [33mWARNING[0m
)

echo.
echo 5. Summary
echo ----------
echo Tests Passed: %PASSED%
echo Tests Failed: %FAILED%
echo.

if %FAILED% EQU 0 (
    echo [32mAll tests passed! Ready for manual testing.[0m
    exit /b 0
) else (
    echo [31mSome tests failed. Please check the output above.[0m
    exit /b 1
)

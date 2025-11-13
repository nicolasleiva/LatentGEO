@echo off
REM Docker Setup Validation Script (Windows)

setlocal enabledelayedexpansion

REM Colors (using ANSI escape codes)
set "GREEN=[92m"
set "YELLOW=[93m"
set "RED=[91m"
set "BLUE=[94m"
set "NC=[0m"

REM Counters
set "PASSED=0"
set "FAILED=0"
set "WARNINGS=0"

REM Functions
echo %BLUE%========================================%NC%
echo %BLUE%Docker Setup Validation%NC%
echo %BLUE%========================================%NC%
echo.

REM 1. Check Docker installation
echo 1. Checking Docker installation...
docker --version >nul 2>&1
if errorlevel 1 (
    echo %RED%X Docker not installed%NC%
    set /a FAILED+=1
) else (
    for /f "tokens=*" %%i in ('docker --version') do set DOCKER_VERSION=%%i
    echo %GREEN%+ Docker installed: !DOCKER_VERSION!%NC%
    set /a PASSED+=1
)

REM 2. Check Docker Compose
echo.
echo 2. Checking Docker Compose...
docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo %RED%X Docker Compose not installed%NC%
    set /a FAILED+=1
) else (
    for /f "tokens=*" %%i in ('docker-compose --version') do set COMPOSE_VERSION=%%i
    echo %GREEN%+ Docker Compose installed: !COMPOSE_VERSION!%NC%
    set /a PASSED+=1
)

REM 3. Check Docker daemon
echo.
echo 3. Checking Docker daemon...
docker info >nul 2>&1
if errorlevel 1 (
    echo %RED%X Docker daemon is not running%NC%
    set /a FAILED+=1
) else (
    echo %GREEN%+ Docker daemon is running%NC%
    set /a PASSED+=1
)

REM 4. Check required files
echo.
echo 4. Checking required files...
set "FILES=Dockerfile.backend Dockerfile.frontend docker-compose.yml docker-compose.dev.yml .env.example backend\requirements.txt frontend\package.json"

for %%F in (%FILES%) do (
    if exist "%%F" (
        echo %GREEN%+ Found: %%F%NC%
        set /a PASSED+=1
    ) else (
        echo %RED%X Missing: %%F%NC%
        set /a FAILED+=1
    )
)

REM 5. Check .env file
echo.
echo 5. Checking environment configuration...
if exist ".env" (
    echo %GREEN%+ .env file exists%NC%
    set /a PASSED+=1
) else (
    echo %YELLOW%! .env file not found (creating from .env.example)%NC%
    if exist ".env.example" (
        copy .env.example .env >nul
        echo %GREEN%+ Created .env from .env.example%NC%
        set /a PASSED+=1
    ) else (
        echo %RED%X Cannot create .env - .env.example not found%NC%
        set /a FAILED+=1
    )
)

REM 6. Check backend structure
echo.
echo 6. Checking backend structure...
set "BACKEND_FILES=backend\app\main.py backend\app\core\config.py backend\app\core\database.py backend\app\api\routes\audits.py"

for %%F in (%BACKEND_FILES%) do (
    if exist "%%F" (
        echo %GREEN%+ Found: %%F%NC%
        set /a PASSED+=1
    ) else (
        echo %RED%X Missing: %%F%NC%
        set /a FAILED+=1
    )
)

REM 7. Check frontend structure
echo.
echo 7. Checking frontend structure...
set "FRONTEND_FILES=frontend\package.json frontend\next.config.mjs frontend\tsconfig.json frontend\app\page.tsx"

for %%F in (%FRONTEND_FILES%) do (
    if exist "%%F" (
        echo %GREEN%+ Found: %%F%NC%
        set /a PASSED+=1
    ) else (
        echo %RED%X Missing: %%F%NC%
        set /a FAILED+=1
    )
)

REM 8. Check ports availability
echo.
echo 8. Checking port availability...
set "PORTS=3000 8000 5432 6379"

for %%P in (%PORTS%) do (
    netstat -an | find ":%%P " >nul
    if errorlevel 1 (
        echo %GREEN%+ Port %%P is available%NC%
        set /a PASSED+=1
    ) else (
        echo %YELLOW%! Port %%P is already in use%NC%
        set /a WARNINGS+=1
    )
)

REM 9. Check documentation
echo.
echo 9. Checking documentation...
set "DOCS=README_DOCKER.md DOCKER_QUICK_START.md DOCKER_SETUP.md DOCKER_TROUBLESHOOTING.md DOCKER_FIXES_SUMMARY.md"

for %%D in (%DOCS%) do (
    if exist "%%D" (
        echo %GREEN%+ Found: %%D%NC%
        set /a PASSED+=1
    ) else (
        echo %RED%X Missing: %%D%NC%
        set /a FAILED+=1
    )
)

REM Summary
echo.
echo %BLUE%========================================%NC%
echo %BLUE%Validation Summary%NC%
echo %BLUE%========================================%NC%
echo.
echo %GREEN%Passed: !PASSED!%NC%
echo %YELLOW%Warnings: !WARNINGS!%NC%
echo %RED%Failed: !FAILED!%NC%
echo.

if !FAILED! equ 0 (
    echo %GREEN%+ All checks passed! Your Docker setup is ready.%NC%
    echo.
    echo %BLUE%Next steps:%NC%
    echo 1. Edit .env with your API keys (optional)
    echo 2. Run: docker-compose up -d
    echo 3. Access: http://localhost:3000
    exit /b 0
) else (
    echo %RED%X Some checks failed. Please fix the issues above.%NC%
    exit /b 1
)

endlocal

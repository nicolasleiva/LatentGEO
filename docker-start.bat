@echo off
REM Docker startup script for GEO Audit Platform (Windows)

setlocal enabledelayedexpansion

REM Colors (using ANSI escape codes)
set "GREEN=[92m"
set "YELLOW=[93m"
set "RED=[91m"
set "NC=[0m"

REM Check if Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo %RED%Error: Docker daemon is not running. Please start Docker Desktop.%NC%
    exit /b 1
)

echo %GREEN%Docker daemon is running%NC%

REM Check if .env file exists
if not exist .env (
    echo %YELLOW%Creating .env file from .env.example...%NC%
    copy .env.example .env
    echo %YELLOW%Please edit .env with your API keys before running again%NC%
    exit /b 0
)

REM Parse arguments
set "MODE=%1"
set "ACTION=%2"

if "%MODE%"=="" set "MODE=prod"
if "%ACTION%"=="" set "ACTION=up"

if "%MODE%"=="dev" (
    echo %GREEN%========================================%NC%
    echo %GREEN%Starting Development Environment%NC%
    echo %GREEN%========================================%NC%
    set "COMPOSE_FILE=docker-compose.dev.yml"
) else if "%MODE%"=="prod" (
    echo %GREEN%========================================%NC%
    echo %GREEN%Starting Production Environment%NC%
    echo %GREEN%========================================%NC%
    set "COMPOSE_FILE=docker-compose.yml"
) else (
    echo %RED%Invalid mode: %MODE%. Use 'dev' or 'prod'%NC%
    exit /b 1
)

if "%ACTION%"=="up" (
    echo %YELLOW%Building and starting services...%NC%
    docker-compose -f !COMPOSE_FILE! up -d
    echo %GREEN%Services started%NC%
    
    echo %YELLOW%Waiting for services to be healthy...%NC%
    timeout /t 5 /nobreak
    
    docker-compose -f !COMPOSE_FILE! ps
    
    echo %GREEN%========================================%NC%
    echo %GREEN%Services Ready%NC%
    echo %GREEN%========================================%NC%
    echo %GREEN%Frontend:%NC% http://localhost:3000
    echo %GREEN%Backend:%NC% http://localhost:8000
    echo %GREEN%API Docs:%NC% http://localhost:8000/docs
    echo %GREEN%Database:%NC% localhost:5432
    echo %GREEN%Redis:%NC% localhost:6379
) else if "%ACTION%"=="down" (
    echo %YELLOW%Stopping services...%NC%
    docker-compose -f !COMPOSE_FILE! down
    echo %GREEN%Services stopped%NC%
) else if "%ACTION%"=="restart" (
    echo %YELLOW%Restarting services...%NC%
    docker-compose -f !COMPOSE_FILE! restart
    echo %GREEN%Services restarted%NC%
) else if "%ACTION%"=="logs" (
    echo %YELLOW%Showing logs (Ctrl+C to exit)...%NC%
    docker-compose -f !COMPOSE_FILE! logs -f
) else if "%ACTION%"=="build" (
    echo %YELLOW%Building services...%NC%
    docker-compose -f !COMPOSE_FILE! build --no-cache
    echo %GREEN%Services built%NC%
) else if "%ACTION%"=="clean" (
    echo %YELLOW%Cleaning up containers and volumes...%NC%
    docker-compose -f !COMPOSE_FILE! down -v
    echo %GREEN%Cleanup complete%NC%
) else (
    echo %RED%Invalid action: %ACTION%%NC%
    echo Available actions: up, down, restart, logs, build, clean
    exit /b 1
)

endlocal

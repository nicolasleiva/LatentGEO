
@echo off
echo ==========================================
echo   Testing V11 Report Integration via Docker
echo ==========================================

echo 1. Stopping existing containers...
docker-compose down

echo 2. Rebuilding backend to include new V11 code...
docker-compose build backend worker

echo 3. Starting services...
docker-compose up -d

echo 4. Waiting for services to initialize (15s)...
timeout /t 15

echo 5. Running test script...
python test_docker_v11.py

echo ==========================================
echo   Check the output above for SUCCESS
echo ==========================================
echo Done.

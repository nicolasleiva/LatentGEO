@echo off
echo ========================================
echo Instalando Chat Flow con KIMI
echo ========================================
echo.

echo [1/4] Instalando dependencias de Python...
cd backend
pip install openai
echo.

echo [2/4] Migrando base de datos...
python migrate_add_chat_fields.py
echo.

echo [3/4] Rebuilding Docker containers...
cd ..
docker-compose down
docker-compose up -d --build backend worker
echo.

echo [4/4] Instalando dependencias de frontend...
cd frontend
call pnpm install
echo.



echo ========================================
echo Instalacion completada!
echo ========================================
echo.
echo Siguiente paso:
echo   cd frontend
echo   pnpm run dev
echo.
echo Luego visita: http://localhost:3000
echo.
pause

@echo off
REM Script de verificación rápida del sistema
REM Verifica que todos los cambios estén funcionando correctamente

echo ========================================
echo   VERIFICACION RAPIDA DEL SISTEMA
echo ========================================
echo.

echo [1/5] Verificando Docker containers...
docker-compose ps
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Docker containers no estan corriendo
    echo Ejecuta: docker-compose up -d
    pause
    exit /b 1
)
echo OK: Containers corriendo
echo.

echo [2/5] Verificando Backend Health...
curl -s http://localhost:8000/health > nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Backend no responde
    echo Verifica: docker-compose logs backend
    pause
    exit /b 1
)
echo OK: Backend respondiendo
echo.

echo [3/5] Verificando Frontend...
curl -s http://localhost:3000 > nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Frontend no responde
    echo Verifica: docker-compose logs frontend
    pause
    exit /b 1
)
echo OK: Frontend respondiendo
echo.

echo [4/5] Verificando configuracion...
echo Verificando variables de entorno...
findstr /C:"ENABLE_PAGESPEED=False" .env > nul
if %ERRORLEVEL% EQU 0 (
    echo OK: PageSpeed desactivado por defecto
) else (
    echo ADVERTENCIA: ENABLE_PAGESPEED no esta en False
)

findstr /C:"NVIDIA_API_KEY" .env > nul
if %ERRORLEVEL% EQU 0 (
    echo OK: NVIDIA_API_KEY configurada
) else (
    echo ERROR: NVIDIA_API_KEY no configurada
)
echo.

echo [5/5] Ejecutando tests...
cd backend
python tests\test_complete_system.py
cd ..
echo.

echo ========================================
echo   VERIFICACION COMPLETADA
echo ========================================
echo.
echo Siguiente paso:
echo   1. Abre http://localhost:3000
echo   2. Crea una auditoria
echo   3. Verifica que SSE funciona (F12 - Console)
echo   4. Verifica que PageSpeed NO se ejecuta automaticamente
echo   5. Haz clic en "Analyze PageSpeed" para ejecutarlo manualmente
echo.
pause

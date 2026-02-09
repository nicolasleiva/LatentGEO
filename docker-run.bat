@echo off
chcp 65001 >nul
echo ========================================
echo  COMANDOS DOCKER - AUDITOR GEO
echo ========================================
echo.

:menu
echo ¿Qué modo quieres usar?
echo.
echo 1. PRODUCCION (build completo, optimizado)
echo 2. DESARROLLO (hot reload, mas rapido)
echo 3. LIMPIAR TODO (detener y eliminar contenedores)
echo 4. Verificar configuracion
echo 5. Salir
echo.
set /p opcion="Elige una opcion (1-5): "

if "%opcion%"=="1" goto produccion
if "%opcion%"=="2" goto desarrollo
if "%opcion%"=="3" goto limpiar
if "%opcion%"=="4" goto verificar
if "%opcion%"=="5" goto salir
goto menu

:produccion
echo.
echo ========================================
echo  MODO PRODUCCION
echo ========================================
echo.
echo Comandos a ejecutar:
echo.
echo   docker compose down -v
echo   docker compose build --no-cache frontend
echo   docker compose up -d
echo.
echo NOTA: La primera vez tardara varios minutos en construir
echo.
pause
docker compose down -v
docker compose build --no-cache frontend
docker compose up -d
echo.
echo ✅ Servicios en produccion iniciados
echo    Frontend: http://localhost:3000
echo    Backend:  http://localhost:8000
echo.
pause
goto menu

:desarrollo
echo.
echo ========================================
echo  MODO DESARROLLO (Hot Reload)
echo ========================================
echo.
echo Comandos a ejecutar:
echo.
echo   docker compose -f docker-compose.dev.yml down -v
echo   docker compose -f docker-compose.dev.yml up
echo.
echo NOTA: Este modo permite ver cambios en tiempo real
echo.
pause
docker compose -f docker-compose.dev.yml down -v
docker compose -f docker-compose.dev.yml up
goto menu

:limpiar
echo.
echo ========================================
echo  LIMPIANDO TODO
echo ========================================
echo.
echo Comandos a ejecutar:
echo.
echo   docker compose down -v
echo   docker compose -f docker-compose.dev.yml down -v
echo   docker system prune -f
echo.
pause
docker compose down -v
docker compose -f docker-compose.dev.yml down -v
docker system prune -f
echo.
echo ✅ Todo limpiado correctamente
echo.
pause
goto menu

:verificar
echo.
echo ========================================
echo  VERIFICANDO CONFIGURACION
echo ========================================
echo.
echo Verificando archivos...
echo.
if exist "Dockerfile.frontend" (
    echo ✓ Dockerfile.frontend
) else (
    echo ✗ Dockerfile.frontend NO EXISTE
)

if exist "docker-compose.yml" (
    echo ✓ docker-compose.yml
) else (
    echo ✗ docker-compose.yml NO EXISTE
)

if exist "docker-compose.dev.yml" (
    echo ✓ docker-compose.dev.yml
) else (
    echo ✗ docker-compose.dev.yml NO EXISTE
)

if exist "frontend\next.config.mjs" (
    findstr /C:"output: 'standalone'" frontend\next.config.mjs >nul && (
        echo ✓ next.config.mjs tiene 'output: standalone'
    ) || (
        echo ✗ next.config.mjs NO tiene 'output: standalone'
    )
) else (
    echo ✗ frontend\next.config.mjs NO EXISTE
)

echo.
echo Verificando volúmenes conflictivos en docker-compose.yml...
findstr /C:"./frontend:/app" docker-compose.yml >nul && (
    echo ⚠ ADVERTENCIA: docker-compose.yml tiene volumen conflictivo
    echo   Esto causara errores en produccion
) || (
    echo ✓ docker-compose.yml NO tiene volúmenes conflictivos
)

echo.
pause
goto menu

:salir
echo.
echo 👋 Hasta luego!
echo.
exit /b

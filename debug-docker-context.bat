# Debug Docker Context
# Uso: .\debug-docker-context.bat

@echo off
echo 🔍 Analizando contexto de build de Docker...

echo.
echo 📊 Archivos más grandes en el directorio:
powershell "Get-ChildItem -Recurse -File | Sort-Object Length -Descending | Select-Object FullName, @{Name='SizeMB';Expression={[math]::Round($_.Length/1MB,2)}} -First 20"

echo.
echo 📁 Directorios que deberían estar excluidos:
powershell "Get-ChildItem -Recurse -Directory | Where-Object { $_.Name -match '(__pycache__|node_modules|\.git|\.next|reports|logs|\.pytest_cache|\.mypy_cache)' } | Select-Object FullName -First 10"

echo.
echo 📋 Contenido del .dockerignore:
type .dockerignore

echo.
echo 💡 Para build limpio, ejecuta: .\docker-clean-build.bat
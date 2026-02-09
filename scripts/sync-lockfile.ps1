# =============================================================================
# Script de sincronización de lockfile para Docker (PowerShell)
# Asegura que pnpm-lock.yaml sea compatible antes del build
# =============================================================================

# Colores
function Write-Info { param([string]$Message) Write-Host "[INFO] $Message" -ForegroundColor Cyan }
function Write-Success { param([string]$Message) Write-Host "[SUCCESS] $Message" -ForegroundColor Green }
function Write-Warning { param([string]$Message) Write-Host "[WARNING] $Message" -ForegroundColor Yellow }
function Write-Error { param([string]$Message) Write-Host "[ERROR] $Message" -ForegroundColor Red }

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$FrontendDir = Join-Path $ScriptDir "..\frontend"

Set-Location $FrontendDir

Write-Info "Verificando sincronización del lockfile..."

# Verificar si packageManager está definido
$PackageJson = Get-Content "package.json" -Raw | ConvertFrom-Json
if (-not $PackageJson.packageManager) {
    Write-Warning "No se encontró 'packageManager' en package.json"
    Write-Info "Detectando versión de pnpm..."
    
    try {
        $PnpmVersion = (pnpm --version).Trim()
        Write-Info "Versión detectada: pnpm@$PnpmVersion"
    } catch {
        Write-Error "No se pudo detectar la versión de pnpm. Asegúrate de tener pnpm instalado."
        exit 1
    }
    
    # Agregar packageManager al package.json
    Write-Info "Agregando packageManager al package.json..."
    $PackageJson | Add-Member -NotePropertyName "packageManager" -NotePropertyValue "pnpm@$PnpmVersion" -Force
    $PackageJson | ConvertTo-Json -Depth 10 | Set-Content "package.json" -Encoding UTF8
    
    Write-Success "packageManager agregado: pnpm@$PnpmVersion"
}

# Verificar si el lockfile existe
if (-not (Test-Path "pnpm-lock.yaml")) {
    Write-Warning "No existe pnpm-lock.yaml"
    Write-Info "Generando lockfile..."
    pnpm install --lockfile-only
    Write-Success "Lockfile generado"
} else {
    # Verificar si está sincronizado
    Write-Info "Verificando si lockfile está sincronizado..."
    
    try {
        $null = pnpm install --frozen-lockfile --lockfile-only 2>$null
        Write-Success "Lockfile está sincronizado"
    } catch {
        Write-Warning "Lockfile desincronizado"
        Write-Info "Actualizando lockfile..."
        pnpm install --lockfile-only
        Write-Success "Lockfile actualizado"
        
        Write-Host ""
        Write-Warning "IMPORTANTE: Se modificó pnpm-lock.yaml"
        Write-Warning "Por favor commitea los cambios:"
        Write-Host "  git add pnpm-lock.yaml"
        Write-Host "  git commit -m 'chore: sync pnpm-lock.yaml'"
    }
}

Write-Success "Verificación completada. Listo para Docker build."

# =============================================================================
# Script de build Docker profesional para Frontend (PowerShell)
# Manejo robusto de errores, caché, retries y logging detallado
# =============================================================================

param(
    [switch]$Clean,
    [switch]$NoCache,
    [string]$Tag = "latest",
    [switch]$Help
)

# -----------------------------------------------------------------------------
# CONFIGURACIÓN
# -----------------------------------------------------------------------------
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectName = "auditor-geo"
$ImageName = "${ProjectName}-frontend:${Tag}"
$Dockerfile = "Dockerfile.frontend"
$BuildContext = "."
$MaxRetries = 3
$RetryDelay = 10

# -----------------------------------------------------------------------------
# FUNCIONES DE UTILIDAD
# -----------------------------------------------------------------------------

function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

# -----------------------------------------------------------------------------
# VALIDACIONES PRE-BUILD
# -----------------------------------------------------------------------------

function Test-Prerequisites {
    Write-Info "Validando prerequisitos..."
    
    # Verificar Docker
    try {
        $null = docker version 2>$null
    } catch {
        Write-Error "Docker no está instalado o no está en el PATH"
        exit 1
    }
    
    # Verificar Docker Buildx
    try {
        $null = docker buildx version 2>$null
    } catch {
        Write-Warning "Docker Buildx no está disponible. Creando builder..."
        docker buildx create --use --name "${ProjectName}-builder" 2>$null | Out-Null
    }
    
    # Verificar archivos necesarios
    $dockerfilePath = Join-Path $ScriptDir $Dockerfile
    $packageJsonPath = Join-Path $ScriptDir "frontend\package.json"
    $pnpmLockPath = Join-Path $ScriptDir "frontend\pnpm-lock.yaml"
    
    if (-not (Test-Path $dockerfilePath)) {
        Write-Error "No se encuentra $Dockerfile"
        exit 1
    }
    
    if (-not (Test-Path $packageJsonPath)) {
        Write-Error "No se encuentra frontend\package.json"
        exit 1
    }
    
    if (-not (Test-Path $pnpmLockPath)) {
        Write-Error "No se encuentra frontend\pnpm-lock.yaml"
        Write-Error "Ejecuta 'cd frontend && pnpm install' primero"
        exit 1
    }
    
    Write-Success "Prerequisitos validados"
}

# -----------------------------------------------------------------------------
# SINCRONIZACIÓN DE LOCKFILE
# -----------------------------------------------------------------------------

function Sync-Lockfile {
    Write-Info "Sincronizando lockfile..."
    
    $SyncScript = Join-Path $ScriptDir "sync-lockfile.ps1"
    if (Test-Path $SyncScript) {
        & $SyncScript
    } else {
        Write-Warning "Script de sincronización no encontrado, verificando manualmente..."
        $FrontendDir = Join-Path $ScriptDir "..\frontend"
        Set-Location $FrontendDir
        
        try {
            $null = pnpm install --frozen-lockfile --lockfile-only 2>$null
            Write-Success "Lockfile está sincronizado"
        } catch {
            Write-Error "El lockfile está desincronizado con package.json"
            Write-Error "Ejecuta 'pnpm install' en frontend/ y commitea los cambios"
            exit 1
        }
    }
    
    Write-Success "Lockfile verificado y sincronizado"
}

# -----------------------------------------------------------------------------
# LIMPIEZA DE CACHÉ
# -----------------------------------------------------------------------------

function Clear-BuildCache {
    if ($Clean) {
        Write-Warning "Limpiando caché de Docker..."
        docker builder prune -f 2>$null | Out-Null
        Write-Success "Caché limpiado"
    }
}

# -----------------------------------------------------------------------------
# BUILD CON RETRY LOGIC
# -----------------------------------------------------------------------------

function Invoke-DockerBuildWithRetry {
    $attempt = 1
    $buildArgs = @(
        "--file", $Dockerfile
        "--tag", $ImageName
        "--build-arg", "BUILDKIT_INLINE_CACHE=1"
        "--progress=plain"
    )
    
    if ($NoCache) {
        $buildArgs += "--no-cache"
    }
    
    # Añadir caché si está disponible Buildx
    try {
        $null = docker buildx version 2>$null
        $buildArgs += @(
            "--cache-from", "type=local,src=$env:TEMP\.buildx-cache"
            "--cache-to", "type=local,dest=$env:TEMP\.buildx-cache-new,mode=max"
        )
    } catch {
        Write-Warning "Buildx no disponible, construyendo sin caché optimizada"
    }
    
    $buildArgs += $BuildContext
    
    $env:DOCKER_BUILDKIT = "1"
    $env:BUILDKIT_PROGRESS = "plain"
    
    while ($attempt -le $MaxRetries) {
        Write-Info "Intento de build $attempt/$MaxRetries..."
        
        $logFile = "build-attempt-$attempt.log"
        
        try {
            $output = docker build @buildArgs 2>&1
            $output | Tee-Object -FilePath $logFile
            
            if ($LASTEXITCODE -eq 0) {
                Write-Success "Build completado exitosamente"
                
                # Mover caché
                $cacheNew = Join-Path $env:TEMP ".buildx-cache-new"
                $cacheOld = Join-Path $env:TEMP ".buildx-cache"
                if (Test-Path $cacheNew) {
                    if (Test-Path $cacheOld) {
                        Remove-Item $cacheOld -Recurse -Force
                    }
                    Rename-Item $cacheNew $cacheOld
                }
                
                return $true
            }
        } catch {
            Write-Error "Build falló en intento $attempt`: $_"
        }
        
        if ($attempt -lt $MaxRetries) {
            Write-Warning "Reintentando en ${RetryDelay} segundos..."
            Start-Sleep -Seconds $RetryDelay
        }
        
        $attempt++
    }
    
    Write-Error "Build falló después de $MaxRetries intentos"
    Write-Error "Revisa los logs: build-attempt-*.log"
    return $false
}

# -----------------------------------------------------------------------------
# INFORMACIÓN POST-BUILD
# -----------------------------------------------------------------------------

function Show-BuildInfo {
    Write-Info "Información de la imagen construida:"
    docker images $ImageName.Split(':')[0] --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"
    
    Write-Host ""
    Write-Info "Para ejecutar la imagen:"
    Write-Host "  docker run -p 3000:3000 $ImageName"
    
    Write-Host ""
    Write-Info "Para debuggear la imagen:"
    Write-Host "  docker run -it --entrypoint sh $ImageName"
}

# -----------------------------------------------------------------------------
# FUNCIÓN PRINCIPAL
# -----------------------------------------------------------------------------

function Main {
    if ($Help) {
        Write-Host "Uso: .\build-frontend.ps1 [OPTIONS]"
        Write-Host ""
        Write-Host "Opciones:"
        Write-Host "  -Clean       Limpiar caché antes de build"
        Write-Host "  -NoCache     Build sin usar caché"
        Write-Host "  -Tag TAG     Etiqueta personalizada para la imagen"
        Write-Host "  -Help        Mostrar esta ayuda"
        exit 0
    }
    
    Write-Host "================================================================"
    Write-Host "  DOCKER BUILD - ${ProjectName} FRONTEND"
    Write-Host "================================================================"
    Write-Host ""
    
    Test-Prerequisites
    Sync-Lockfile
    Clear-BuildCache
    
    Write-Host ""
    Write-Info "Iniciando build de Docker..."
    Write-Host "----------------------------------------------------------------"
    
    if (Invoke-DockerBuildWithRetry) {
        Write-Host ""
        Write-Host "================================================================"
        Write-Success "BUILD COMPLETADO EXITOSAMENTE"
        Write-Host "================================================================"
        Write-Host ""
        Show-BuildInfo
        exit 0
    } else {
        Write-Host ""
        Write-Host "================================================================"
        Write-Error "BUILD FALLÓ"
        Write-Host "================================================================"
        exit 1
    }
}

# Ejecutar
Main

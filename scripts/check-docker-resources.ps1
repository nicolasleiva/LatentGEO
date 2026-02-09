# =============================================================================
# Script de diagnóstico de recursos Docker (PowerShell)
# Verifica configuración de memoria y recursos
# =============================================================================

# Colores
function Write-Info { param([string]$Message) Write-Host "[INFO] $Message" -ForegroundColor Cyan }
function Write-Success { param([string]$Message) Write-Host "[SUCCESS] $Message" -ForegroundColor Green }
function Write-Warning { param([string]$Message) Write-Host "[WARNING] $Message" -ForegroundColor Yellow }
function Write-Error { param([string]$Message) Write-Host "[ERROR] $Message" -ForegroundColor Red }

Write-Host "================================================================"
Write-Host "  DIAGNÓSTICO DE RECURSOS DOCKER"
Write-Host "================================================================"
Write-Host ""

# Verificar Docker está corriendo
try {
    $null = docker info 2>$null
    Write-Success "Docker está activo"
} catch {
    Write-Error "Docker no está corriendo"
    exit 1
}

# Verificar versión de Docker
$DockerVersion = (docker version --format '{{.Server.Version}}' 2>$null) || "unknown"
Write-Info "Versión de Docker: $DockerVersion"

# Verificar sistema operativo
Write-Info "Sistema: Windows"

# Obtener información de memoria de Docker Desktop
try {
    $DockerInfo = docker info 2>$null
    if ($DockerInfo -match "Total Memory:\s+(\S+)") {
        $TotalMem = $matches[1]
        Write-Info "Memoria total asignada a Docker: $TotalMem"
        
        # Convertir a GB
        $MemValue = $TotalMem -replace '[a-zA-Z]', ''
        $MemUnit = $TotalMem -replace '[0-9.]', ''
        
        $MemGB = switch ($MemUnit) {
            "GiB" { [double]$MemValue }
            "MiB" { [double]$MemValue / 1024 }
            "GB" { [double]$MemValue }
            "MB" { [double]$MemValue / 1024 }
            default { [double]$MemValue }
        }
        
        if ($MemGB -lt 3) {
            Write-Warning "⚠️  Memoria asignada a Docker es menor a 3GB"
            Write-Warning "   Recomendado: 4GB o más para evitar errores ENOMEM"
            Write-Info "   Solución: Docker Desktop → Settings → Resources → Memory"
        } else {
            Write-Success "✓ Memoria asignada es suficiente (≥3GB)"
        }
    } else {
        Write-Warning "No se pudo determinar memoria asignada a Docker"
    }
} catch {
    Write-Warning "No se pudo obtener información de recursos de Docker"
}

# Verificar uso de disco de Docker
Write-Host ""
Write-Info "Uso de disco de Docker:"
docker system df

# Verificar si hay contenedores usando mucha memoria
Write-Host ""
Write-Info "Contenedores activos y uso de recursos:"
try {
    $Containers = docker ps -q 2>$null
    if ($Containers) {
        docker stats --no-stream --format "table {{.Name}}`t{{.CPUPerc}}`t{{.MemUsage}}`t{{.MemPerc}}"
    } else {
        Write-Info "No hay contenedores activos"
    }
} catch {
    Write-Info "No se pudo obtener estadísticas de contenedores"
}

# Verificar imágenes
Write-Host ""
Write-Info "Imágenes Docker:"
docker images --format "table {{.Repository}}`t{{.Tag}}`t{{.Size}}" | Select-Object -First 10

# Verificar memoria del sistema
Write-Host ""
Write-Info "Memoria del sistema:"
try {
    $ComputerInfo = Get-ComputerInfo | Select-Object TotalPhysicalMemory
    $TotalRamGB = [math]::Round($ComputerInfo.TotalPhysicalMemory / 1GB, 2)
    Write-Info "RAM total: ${TotalRamGB}GB"
    
    $AvailableRam = Get-CimInstance Win32_OperatingSystem | Select-Object FreePhysicalMemory
    $AvailableRamGB = [math]::Round($AvailableRam.FreePhysicalMemory / 1MB, 2)
    Write-Info "RAM disponible: ${AvailableRamGB}GB"
    
    $UsedPercent = [math]::Round((($TotalRamGB - $AvailableRamGB) / $TotalRamGB) * 100, 1)
    Write-Info "Uso de RAM: ${UsedPercent}%"
    
    if ($UsedPercent -gt 80) {
        Write-Warning "⚠️  Uso de RAM del sistema está alto (>80%)"
    }
} catch {
    Write-Warning "No se pudo obtener información de memoria del sistema"
}

# Recomendaciones
Write-Host ""
Write-Host "================================================================"
Write-Host "  RECOMENDACIONES"
Write-Host "================================================================"

$MinMemoryGB = 4

Write-Host ""
Write-Info "Para Windows:"
Write-Host "  1. Abrir Docker Desktop"
Write-Host "  2. Settings (⚙️) → Resources → Advanced"
Write-Host "  3. Configurar:"
Write-Host "     - Memory: ${MinMemoryGB}GB o más"
Write-Host "     - Swap: 2GB"
Write-Host "     - CPUs: 2"
Write-Host "  4. Apply & Restart"

Write-Host ""
Write-Info "Para ejecutar con límites de memoria:"
Write-Host "  docker run --memory=2g --cpus=1.0 -p 3000:3000 <imagen>"

Write-Host ""
Write-Info "Ver documentación completa: MEMORY_ERROR_SOLUTION.md"

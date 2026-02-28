Write-Host "Iniciando compilacion de imagenes Docker para distribucion..."

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RootDir

function Get-DotEnvMap {
    param([string]$Path)

    $map = @{}
    if (-not (Test-Path $Path)) {
        return $map
    }

    foreach ($line in Get-Content $Path) {
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        if ($line -match '^\s*#') { continue }
        if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$') {
            $key = $matches[1]
            $value = $matches[2].Trim()
            if (
                ($value.StartsWith('"') -and $value.EndsWith('"')) -or
                ($value.StartsWith("'") -and $value.EndsWith("'"))
            ) {
                $value = $value.Substring(1, $value.Length - 2)
            }
            $map[$key] = $value
        }
    }

    return $map
}

function Resolve-ConfigValue {
    param(
        [string]$Name,
        [hashtable]$DotEnvMap
    )

    $processValue = [Environment]::GetEnvironmentVariable($Name)
    if (-not [string]::IsNullOrWhiteSpace($processValue)) {
        return $processValue
    }

    if ($DotEnvMap.ContainsKey($Name) -and -not [string]::IsNullOrWhiteSpace($DotEnvMap[$Name])) {
        return $DotEnvMap[$Name]
    }

    return $null
}

$dotenvPath = Join-Path $RootDir ".env"
$dotEnvMap = Get-DotEnvMap -Path $dotenvPath

$requiredBuildVars = @(
    "NEXT_PUBLIC_API_URL",
    "NEXT_PUBLIC_BACKEND_URL",
    "NEXT_PUBLIC_AUTH0_API_AUDIENCE"
)

$resolved = @{}
$missing = @()

foreach ($name in $requiredBuildVars) {
    $value = Resolve-ConfigValue -Name $name -DotEnvMap $dotEnvMap
    if ([string]::IsNullOrWhiteSpace($value)) {
        $missing += $name
    } else {
        $resolved[$name] = $value
    }
}

if ($missing.Count -gt 0) {
    Write-Error "Faltan variables requeridas para el build del frontend: $($missing -join ', ')"
    Write-Error "Definilas en .env o como variables de entorno del proceso."
    exit 1
}

$auth0Scopes = Resolve-ConfigValue -Name "NEXT_PUBLIC_AUTH0_API_SCOPES" -DotEnvMap $dotEnvMap
if ([string]::IsNullOrWhiteSpace($auth0Scopes)) {
    $auth0Scopes = "read:app"
}

# 1. Compilar Backend (y Worker)
Write-Host "Compilando Backend..."
docker build -t auditor_geo-backend:latest -f Dockerfile.backend .
if ($LASTEXITCODE -ne 0) { Write-Error "Fallo al compilar Backend"; exit 1 }

# 2. Compilar Frontend (build args leidos de .env / entorno, sin imprimir secretos)
Write-Host "Compilando Frontend..."
docker build `
  -t auditor_geo-frontend:latest `
  -f Dockerfile.frontend `
  --build-arg "NEXT_PUBLIC_API_URL=$($resolved["NEXT_PUBLIC_API_URL"])" `
  --build-arg "NEXT_PUBLIC_BACKEND_URL=$($resolved["NEXT_PUBLIC_BACKEND_URL"])" `
  --build-arg "NEXT_PUBLIC_AUTH0_API_AUDIENCE=$($resolved["NEXT_PUBLIC_AUTH0_API_AUDIENCE"])" `
  --build-arg "NEXT_PUBLIC_AUTH0_API_SCOPES=$auth0Scopes" `
  .
if ($LASTEXITCODE -ne 0) { Write-Error "Fallo al compilar Frontend"; exit 1 }

# 3. Guardar imagenes en archivo .tar
Write-Host "Guardando imagenes en auditor_geo_release.tar..."
docker save -o auditor_geo_release.tar auditor_geo-backend:latest auditor_geo-frontend:latest
if ($LASTEXITCODE -ne 0) { Write-Error "Fallo al guardar imagenes"; exit 1 }

Write-Host "Proceso completado. Archivo generado: auditor_geo_release.tar"
Write-Host "Para distribuir, comparte:"
Write-Host "  1. auditor_geo_release.tar"
Write-Host "  2. docker-compose.release.yml"
Write-Host "  3. .env.example (como plantilla)"

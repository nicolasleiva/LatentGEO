param(
    [ValidateSet("local", "staging", "postdeploy")]
    [string]$Stage = "local",
    [switch]$AllowDirty,
    [switch]$SkipDocker,
    [switch]$SkipBaseline,
    [switch]$SkipPerf,
    [switch]$SkipLiveAudit
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "=== $Message ===" -ForegroundColor Cyan
}

function Invoke-CheckedCommand {
    param(
        [string]$Exe,
        [string[]]$CmdArgs
    )

    & $Exe @CmdArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $Exe $($CmdArgs -join ' ')"
    }
}

function Load-DotEnv {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    Get-Content -LiteralPath $Path | ForEach-Object {
        $line = $_.Trim()
        if ([string]::IsNullOrWhiteSpace($line) -or $line.StartsWith("#")) {
            return
        }

        $eqIndex = $line.IndexOf("=")
        if ($eqIndex -lt 1) {
            return
        }

        $key = $line.Substring(0, $eqIndex).Trim()
        $value = $line.Substring($eqIndex + 1).Trim()
        [Environment]::SetEnvironmentVariable($key, $value, "Process")
    }
}

function Require-Env {
    param([string]$Name)
    $value = [Environment]::GetEnvironmentVariable($Name, "Process")
    if ([string]::IsNullOrWhiteSpace($value)) {
        throw "$Name is required for stage '$Stage'."
    }
    return $value.Trim()
}

function Require-ReleasePolicy {
    if ((Require-Env "OPENAPI_DOCS_ENABLED").ToLower() -ne "false") {
        throw "OPENAPI_DOCS_ENABLED must be false for release certification."
    }
    if ((Require-Env "PDF_ALLOW_DETERMINISTIC_FALLBACK").ToLower() -ne "false") {
        throw "PDF_ALLOW_DETERMINISTIC_FALLBACK must be false for release certification."
    }
    [void](Require-Env "WEB_CONCURRENCY")
}

function Set-LocalBuildOverrides {
    [Environment]::SetEnvironmentVariable("ALLOW_LOCALHOST_API_ORIGIN", "1", "Process")
}

function Wait-ForHttpReady {
    param(
        [string]$Url,
        [int[]]$AllowedStatusCodes = @(200),
        [int]$TimeoutSeconds = 180,
        [int]$SleepSeconds = 3
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $Url -Method GET -MaximumRedirection 0 -ErrorAction Stop
            if ($AllowedStatusCodes -contains [int]$response.StatusCode) {
                return
            }
        } catch {
            $statusCode = $null
            if ($_.Exception.Response) {
                try {
                    $statusCode = [int]$_.Exception.Response.StatusCode.value__
                } catch {
                    $statusCode = $null
                }
            }
            if ($null -ne $statusCode -and $AllowedStatusCodes -contains $statusCode) {
                return
            }
        }

        Start-Sleep -Seconds $SleepSeconds
    }

    throw "Timed out waiting for $Url to become ready."
}

function Ensure-CleanWorktree {
    if ($AllowDirty) {
        return
    }
    $status = git status --porcelain
    if (-not [string]::IsNullOrWhiteSpace($status)) {
        throw "Worktree is dirty. Commit or stash changes before strict release certification, or re-run with -AllowDirty."
    }
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot
Load-DotEnv (Join-Path $repoRoot ".env")
Ensure-CleanWorktree

if ($Stage -eq "local") {
    Write-Step "Local baseline"
    if (-not $SkipDocker) {
        Invoke-CheckedCommand docker @("compose", "up", "-d", "--build", "redis", "backend", "frontend", "worker")
        Wait-ForHttpReady -Url "http://localhost:8000/health/live" -AllowedStatusCodes @(200)
        Wait-ForHttpReady -Url "http://localhost:3000/signin" -AllowedStatusCodes @(200, 302)
    }

    Invoke-CheckedCommand pnpm @("--dir", "frontend", "type-check")
    Invoke-CheckedCommand pnpm @("--dir", "frontend", "lint")
    Invoke-CheckedCommand pnpm @("--dir", "frontend", "test:ci")

    Set-LocalBuildOverrides
    $env:STRICT_BUILD = "1"
    try {
        Invoke-CheckedCommand pnpm @("--dir", "frontend", "build")
    } finally {
        Remove-Item Env:STRICT_BUILD -ErrorAction SilentlyContinue
    }

    $env:DATABASE_URL = "sqlite:///:memory:"
    $env:CELERY_BROKER_URL = "memory://"
    $env:CELERY_RESULT_BACKEND = "cache+memory://"
    Invoke-CheckedCommand pytest @("-q")
    return
}

Write-Step "Staging/post-deploy release gate"
Require-ReleasePolicy

$smokeBaseUrl = Require-Env "SMOKE_BASE_URL"
[void](Require-Env "SMOKE_BEARER_TOKEN")
[void](Require-Env "PERF_AUTH_EMAIL")
[void](Require-Env "PERF_AUTH_PASSWORD")

if (-not [Environment]::GetEnvironmentVariable("LIVE_BASE_URL", "Process")) {
    [Environment]::SetEnvironmentVariable(
        "LIVE_BASE_URL",
        $smokeBaseUrl.TrimEnd("/"),
        "Process"
    )
}

if ($Stage -eq "staging") {
    if (-not $SkipBaseline) {
        Invoke-CheckedCommand pnpm @("--dir", "frontend", "type-check")
        Invoke-CheckedCommand pnpm @("--dir", "frontend", "lint")
        Invoke-CheckedCommand pnpm @("--dir", "frontend", "test:ci")

        $env:STRICT_BUILD = "1"
        try {
            Invoke-CheckedCommand pnpm @("--dir", "frontend", "build")
        } finally {
            Remove-Item Env:STRICT_BUILD -ErrorAction SilentlyContinue
        }

        $env:DATABASE_URL = "sqlite:///:memory:"
        $env:CELERY_BROKER_URL = "memory://"
        $env:CELERY_RESULT_BACKEND = "cache+memory://"
        Invoke-CheckedCommand pytest @("-q")
    }

    Invoke-CheckedCommand pytest @("-q", "backend/tests/test_release_smoke_external.py")

    if (-not $SkipPerf) {
        [void](Require-Env "PERF_BASE_URL")
        Invoke-CheckedCommand pnpm @("--dir", "frontend", "quality:web:full")
        Invoke-CheckedCommand pnpm @("--dir", "frontend", "perf:e2e")
        Invoke-CheckedCommand pnpm @("--dir", "frontend", "release:smoke:e2e")
    }

    if (-not $SkipLiveAudit) {
        [void](Require-Env "LIVE_TARGET_URL")
        [void](Require-Env "PROD_TEST_URL")
        [void](Require-Env "PROD_TEST_USER_ID")
        [void](Require-Env "PROD_TEST_KEYWORDS")

        $hasLiveBearer = -not [string]::IsNullOrWhiteSpace(
            [Environment]::GetEnvironmentVariable("LIVE_BEARER_TOKEN", "Process")
        )
        $hasAuth0MachineCreds =
            -not [string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable("AUTH0_CLIENT_ID", "Process")) -and
            -not [string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable("AUTH0_CLIENT_SECRET", "Process")) -and
            (
                -not [string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable("AUTH0_API_AUDIENCE", "Process")) -or
                -not [string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable("NEXT_PUBLIC_AUTH0_API_AUDIENCE", "Process"))
            )

        if (-not ($hasLiveBearer -or $hasAuth0MachineCreds)) {
            throw "Provide LIVE_BEARER_TOKEN or Auth0 machine credentials before running live audit/PDF certification."
        }

        $env:RUN_INTEGRATION_TESTS = "1"
        $env:RUN_LIVE_E2E = "1"
        Invoke-CheckedCommand pytest @("-q", "backend/tests/test_live_plataforma5_agent1_pdf.py", "-s")
    }

    return
}

Invoke-CheckedCommand pytest @("-q", "backend/tests/test_release_smoke_external.py")
Invoke-CheckedCommand pnpm @("--dir", "frontend", "release:smoke:e2e")

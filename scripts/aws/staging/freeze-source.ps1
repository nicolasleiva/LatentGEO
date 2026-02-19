[CmdletBinding()]
param(
    [string]$BranchPrefix = 'deploy/staging',
    [string]$TagPrefix = 'release/staging',
    [switch]$Push
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$timestamp = Get-Date -Format 'yyyyMMdd-HHmm'
$branchName = "$BranchPrefix-$timestamp"
$tagName = "$TagPrefix-$timestamp"

Write-Host "[freeze-source] Creating branch: $branchName" -ForegroundColor Cyan
git checkout -b $branchName
if ($LASTEXITCODE -ne 0) {
    throw 'Failed to create deploy branch.'
}

Write-Host '[freeze-source] Staging all files' -ForegroundColor Cyan
git add -A
if ($LASTEXITCODE -ne 0) {
    throw 'Failed to stage files.'
}

$staged = git diff --cached --name-only
if (-not $staged) {
    throw 'No staged changes found. Nothing to freeze.'
}

$commitMessage = "chore(staging): freeze source snapshot $timestamp"
Write-Host "[freeze-source] Commit: $commitMessage" -ForegroundColor Cyan
git commit -m $commitMessage
if ($LASTEXITCODE -ne 0) {
    throw 'Failed to create freeze commit.'
}

Write-Host "[freeze-source] Tag: $tagName" -ForegroundColor Cyan
git tag $tagName
if ($LASTEXITCODE -ne 0) {
    throw 'Failed to create release tag.'
}

if ($Push) {
    Write-Host "[freeze-source] Pushing branch: $branchName" -ForegroundColor Cyan
    git push -u origin $branchName
    if ($LASTEXITCODE -ne 0) {
        throw 'Failed to push branch.'
    }

    Write-Host "[freeze-source] Pushing tag: $tagName" -ForegroundColor Cyan
    git push origin $tagName
    if ($LASTEXITCODE -ne 0) {
        throw 'Failed to push tag.'
    }
}

Write-Host '[freeze-source] Done.' -ForegroundColor Green
Write-Host "Branch: $branchName"
Write-Host "Tag:    $tagName"

[CmdletBinding()]
param(
    [switch]$CheckOnly,
    [switch]$NoOpen,
    [switch]$SkipModelPull
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

if ($env:OS -ne 'Windows_NT' -or -not [Environment]::Is64BitOperatingSystem) {
    throw 'This launcher supports 64-bit Windows 10 or Windows 11.'
}

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$requiredFiles = @(
    'docker-compose.yml',
    'Dockerfile.backend',
    'package-lock.json',
    'scripts\bootstrap.ps1',
    'apps\web\Dockerfile'
)
foreach ($relativePath in $requiredFiles) {
    if (-not (Test-Path -LiteralPath (Join-Path $projectRoot $relativePath) -PathType Leaf)) {
        throw "The package is incomplete: $relativePath is missing. Extract the entire ZIP before running it."
    }
}

function Refresh-LocalGuardPath {
    $machinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $knownPaths = @(
        (Join-Path $env:ProgramFiles 'PowerShell\7'),
        (Join-Path $env:ProgramFiles 'Docker\Docker\resources\bin'),
        (Join-Path $env:ProgramFiles 'nodejs')
    )
    $env:Path = (@($machinePath, $userPath) + $knownPaths | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }) -join ';'
}

function Install-LocalGuardPackage {
    param(
        [Parameter(Mandatory = $true)][string]$Id,
        [Parameter(Mandatory = $true)][string]$DisplayName
    )
    if (-not (Get-Command winget.exe -ErrorAction SilentlyContinue)) {
        throw "Windows Package Manager is required to install $DisplayName. Install Microsoft App Installer from the Microsoft Store, then run the launcher again."
    }
    Write-Host "Installing $DisplayName..." -ForegroundColor Cyan
    & winget.exe install --exact --id $Id --accept-source-agreements --accept-package-agreements --silent
    if ($LASTEXITCODE -ne 0) {
        throw "$DisplayName installation failed with exit code $LASTEXITCODE. You can install it manually, then rerun this launcher."
    }
    Refresh-LocalGuardPath
}

function Confirm-LocalGuardInstall {
    param([Parameter(Mandatory = $true)][string[]]$Missing)
    Write-Host ''
    Write-Host 'LocalGuard needs these free prerequisites:' -ForegroundColor Yellow
    $Missing | ForEach-Object { Write-Host "  - $_" }
    Write-Host ''
    $answer = Read-Host 'Install the missing prerequisites now with Windows Package Manager? [Y/N]'
    return $answer -match '^(?i:y|yes)$'
}

function Get-LocalGuardNodeVersion {
    if (-not (Get-Command node.exe -ErrorAction SilentlyContinue)) { return $null }
    $raw = (& node.exe --version).Trim().TrimStart('v')
    try { return [Version]$raw } catch { return $null }
}

function Test-LocalGuardDocker {
    if (-not (Get-Command docker.exe -ErrorAction SilentlyContinue)) { return $false }
    & docker.exe info --format '{{.ServerVersion}}' *> $null
    return $LASTEXITCODE -eq 0
}

function Start-LocalGuardDockerDesktop {
    $candidates = @(
        (Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\Docker Desktop.exe')
    )
    $desktop = $candidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
    if ($null -eq $desktop) {
        throw 'Docker Desktop is installed but its application could not be located. Start Docker Desktop manually, then rerun this launcher.'
    }
    Write-Host 'Starting Docker Desktop. Keep it open while LocalGuard is running...' -ForegroundColor Cyan
    Start-Process -FilePath $desktop | Out-Null
    foreach ($attempt in 1..48) {
        Start-Sleep -Seconds 5
        if (Test-LocalGuardDocker) { return }
        if (($attempt % 6) -eq 0) { Write-Host 'Still waiting for the Docker Linux engine...' }
    }
    throw 'Docker Desktop did not become ready within four minutes. A first installation may require a Windows restart. Restart, open Docker Desktop, wait for Engine running, and run this launcher again.'
}

Refresh-LocalGuardPath
$missing = @()
if (-not (Get-Command pwsh.exe -ErrorAction SilentlyContinue)) { $missing += 'PowerShell 7' }
if (-not (Get-Command docker.exe -ErrorAction SilentlyContinue)) { $missing += 'Docker Desktop' }
$nodeVersion = Get-LocalGuardNodeVersion
if ($null -eq $nodeVersion -or $nodeVersion -lt [Version]'24.13.0' -or $nodeVersion -ge [Version]'25.0.0') {
    $missing += 'Node.js 24 LTS'
}

if ($missing.Count -gt 0) {
    if ($CheckOnly) {
        throw "Missing or unsupported prerequisites: $($missing -join ', ')."
    }
    if (-not (Confirm-LocalGuardInstall -Missing $missing)) {
        throw 'Prerequisite installation was cancelled. No LocalGuard setup changes were made.'
    }
    if ($missing -contains 'PowerShell 7') { Install-LocalGuardPackage -Id 'Microsoft.PowerShell' -DisplayName 'PowerShell 7' }
    if ($missing -contains 'Docker Desktop') { Install-LocalGuardPackage -Id 'Docker.DockerDesktop' -DisplayName 'Docker Desktop' }
    if ($missing -contains 'Node.js 24 LTS') { Install-LocalGuardPackage -Id 'OpenJS.NodeJS.LTS' -DisplayName 'Node.js LTS' }
}

Refresh-LocalGuardPath
$pwsh = Get-Command pwsh.exe -ErrorAction SilentlyContinue
if ($null -eq $pwsh) { throw 'PowerShell 7 is still unavailable. Close this window and run START-LOCALGUARD.cmd again.' }
$nodeVersion = Get-LocalGuardNodeVersion
if ($null -eq $nodeVersion -or $nodeVersion -lt [Version]'24.13.0' -or $nodeVersion -ge [Version]'25.0.0') {
    throw "LocalGuard requires Node.js >=24.13.0 and <25. Detected: $nodeVersion."
}
if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) { throw 'npm was not found with Node.js.' }
if (-not (Get-Command docker.exe -ErrorAction SilentlyContinue)) { throw 'Docker was not found after installation.' }

if (-not (Test-LocalGuardDocker)) {
    if ($CheckOnly) { throw 'Docker Desktop is installed, but its Linux engine is not running.' }
    Start-LocalGuardDockerDesktop
}

$systemDrive = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='$($env:SystemDrive)'"
if ($null -ne $systemDrive -and $systemDrive.FreeSpace -lt 16GB) {
    Write-Warning 'Less than 16 GB is free on the Windows system drive. The first LocalGuard build may run out of disk space.'
}

if ($CheckOnly) {
    Write-Host 'Package and prerequisites are ready.' -ForegroundColor Green
    Write-Host "PowerShell: $(& $pwsh.Source --version)"
    Write-Host "Node.js: v$nodeVersion"
    Write-Host "Docker: $(& docker.exe info --format '{{.ServerVersion}}')"
    exit 0
}

$environmentPath = Join-Path $projectRoot '.env'
if (-not (Test-Path -LiteralPath $environmentPath -PathType Leaf)) {
    Write-Host ''
    Write-Host 'First setup: generating local credentials and downloading the pinned runtime.' -ForegroundColor Cyan
    Write-Host 'This is the longest step and is safe to resume if the connection is interrupted.'
    $bootstrapArguments = @('-NoLogo', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $projectRoot 'scripts\bootstrap.ps1'))
    if ($SkipModelPull) { $bootstrapArguments += '-SkipModelPull' }
    & $pwsh.Source @bootstrapArguments
    if ($LASTEXITCODE -ne 0) { throw "LocalGuard bootstrap failed with exit code $LASTEXITCODE." }
}

Write-Host ''
Write-Host 'Starting LocalGuard...' -ForegroundColor Cyan
& $pwsh.Source -NoLogo -NoProfile -ExecutionPolicy Bypass -File (Join-Path $projectRoot 'scripts\dev.ps1')
if ($LASTEXITCODE -ne 0) { throw "LocalGuard startup failed with exit code $LASTEXITCODE." }

if (-not $NoOpen) {
    Start-Process 'http://127.0.0.1:3000/login' | Out-Null
}

Write-Host ''
Write-Host 'LocalGuard AI is ready.' -ForegroundColor Green
Write-Host 'App: http://localhost:3000'
Write-Host 'Username: demo-reviewer'
Write-Host 'Password helper: VIEW-LOCALGUARD-LOGIN.cmd'

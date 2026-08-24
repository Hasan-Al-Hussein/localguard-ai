[CmdletBinding()]
param(
    [ValidateSet('admin', 'reviewer', 'viewer')]
    [string]$Role = 'reviewer'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$environmentPath = Join-Path $projectRoot '.env'
if (-not (Test-Path -LiteralPath $environmentPath -PathType Leaf)) {
    throw 'Local credentials do not exist yet. Run START-LOCALGUARD.cmd first.'
}

$key = "BOOTSTRAP_$($Role.ToUpperInvariant())_PASSWORD"
$prefix = "$key="
$matchingLines = @(Get-Content -LiteralPath $environmentPath | Where-Object { $_.StartsWith($prefix, [StringComparison]::Ordinal) })
if ($matchingLines.Count -ne 1) {
    throw "The local .env file does not contain exactly one $key entry."
}

$password = $matchingLines[0].Substring($prefix.Length)
if ([string]::IsNullOrWhiteSpace($password) -or $password -eq 'generated-by-bootstrap') {
    throw 'The demo password has not been generated yet. Run START-LOCALGUARD.cmd first.'
}

Write-Host ''
Write-Host 'LocalGuard demo login' -ForegroundColor Cyan
Write-Host "Username: demo-$Role"
Write-Host "Password: $password"
Write-Host ''
Write-Host 'Keep this local password private. Close this window when finished.' -ForegroundColor Yellow

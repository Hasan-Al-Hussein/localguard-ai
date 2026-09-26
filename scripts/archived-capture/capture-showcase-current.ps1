[CmdletBinding()]
param(
    [string]$Script = "capture-showcase-current.cjs"
)

$ErrorActionPreference = "Stop"

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$envFile = Join-Path $repositoryRoot ".env"
$passwordLine = Get-Content -LiteralPath $envFile | Where-Object { $_ -match '^BOOTSTRAP_REVIEWER_PASSWORD=' } | Select-Object -First 1
if (-not $passwordLine) {
    throw "BOOTSTRAP_REVIEWER_PASSWORD is missing from .env"
}

$env:LOCALGUARD_CAPTURE_PASSWORD = $passwordLine.Substring($passwordLine.IndexOf("=") + 1)
try {
    & node (Join-Path $PSScriptRoot $Script)
    if ($LASTEXITCODE -ne 0) {
        throw "Showcase capture failed with exit code $LASTEXITCODE"
    }
}
finally {
    Remove-Item Env:LOCALGUARD_CAPTURE_PASSWORD -ErrorAction SilentlyContinue
}

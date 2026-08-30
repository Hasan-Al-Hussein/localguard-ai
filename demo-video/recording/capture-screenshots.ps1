[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$environmentFile = Join-Path $repoRoot '.env'
if (-not (Test-Path -LiteralPath $environmentFile -PathType Leaf)) {
    throw 'The ignored .env file is required for the generated demo credentials.'
}

$configuration = @{}
Get-Content -LiteralPath $environmentFile | ForEach-Object {
    if ($_ -match '^(?<key>[A-Z0-9_]+)=(?<value>.*)$') {
        $configuration[$Matches.key] = $Matches.value
    }
}

$env:LOCALGUARD_BASE_URL = 'http://127.0.0.1:3000'
$env:LOCALGUARD_DEMO_USERNAME = 'demo-reviewer'
$env:LOCALGUARD_DEMO_PASSWORD = $configuration.BOOTSTRAP_REVIEWER_PASSWORD

try {
    & node (Join-Path $PSScriptRoot 'run-flow.mjs') '--mode=screenshots'
    if ($LASTEXITCODE -ne 0) {
        throw "Screenshot capture failed with exit code $LASTEXITCODE."
    }
}
finally {
    Remove-Item Env:LOCALGUARD_BASE_URL -ErrorAction SilentlyContinue
    Remove-Item Env:LOCALGUARD_DEMO_USERNAME -ErrorAction SilentlyContinue
    Remove-Item Env:LOCALGUARD_DEMO_PASSWORD -ErrorAction SilentlyContinue
    $configuration.Clear()
}

. (Join-Path $PSScriptRoot 'common.ps1')
Assert-DockerEngine

$environmentPath = Join-Path $script:ProjectRoot '.env'
if (-not (Test-Path -LiteralPath $environmentPath)) {
    throw 'Local .env is missing. Run scripts/bootstrap.ps1 first.'
}

function Write-LocalGuardEnvironment {
    param([Parameter(Mandatory)][AllowEmptyString()][string[]]$Lines)

    $temporaryPath = Join-Path $script:ProjectRoot (
        '.env.rotate.' + [Guid]::NewGuid().ToString('N') + '.tmp'
    )
    try {
        [IO.File]::WriteAllLines($temporaryPath, $Lines, [Text.UTF8Encoding]::new($false))
        [IO.File]::Move($temporaryPath, $environmentPath, $true)
    }
    finally {
        if (Test-Path -LiteralPath $temporaryPath) {
            Remove-Item -LiteralPath $temporaryPath -Force
        }
    }
}

$originalLines = [IO.File]::ReadAllLines($environmentPath)
$credentialLines = @($originalLines | Where-Object { $_ -match '^BOOTSTRAP_ADMIN_PASSWORD=' })
if ($credentialLines.Count -ne 1) {
    throw 'Expected exactly one BOOTSTRAP_ADMIN_PASSWORD entry in .env.'
}

$rotatedSecret = New-LocalSecret -Bytes 24
$rotatedLines = @(
    $originalLines | ForEach-Object {
        if ($_ -match '^BOOTSTRAP_ADMIN_PASSWORD=') {
            "BOOTSTRAP_ADMIN_PASSWORD=$rotatedSecret"
        }
        else {
            $_
        }
    }
)

try {
    Write-LocalGuardEnvironment -Lines $rotatedLines
    Invoke-LocalGuardCompose -Arguments @(
        'run', '--rm', 'admin-cli', 'python', '-m', 'localguard_api.cli', 'seed'
    )
}
catch {
    Write-LocalGuardEnvironment -Lines $originalLines
    try {
        Invoke-LocalGuardCompose -Arguments @(
            'run', '--rm', 'admin-cli', 'python', '-m', 'localguard_api.cli', 'seed'
        )
    }
    catch {
        throw 'Credential rotation and automatic database rollback both failed. Stop the app and rerun bootstrap before signing in.'
    }
    throw
}
finally {
    $rotatedSecret = $null
}

Write-Host 'The local demo-admin credential and database hash were rotated without printing the value.'

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
$tokenLines = @($originalLines | Where-Object { $_ -match '^MCP_BOOTSTRAP_TOKEN=' })
if ($tokenLines.Count -ne 1) {
    throw 'Expected exactly one MCP_BOOTSTRAP_TOKEN entry in .env.'
}

$rotatedSecret = New-LocalSecret -Bytes 32
$rotatedLines = @(
    $originalLines | ForEach-Object {
        if ($_ -match '^MCP_BOOTSTRAP_TOKEN=') {
            "MCP_BOOTSTRAP_TOKEN=$rotatedSecret"
        }
        else {
            $_
        }
    }
)

try {
    Write-LocalGuardEnvironment -Lines $rotatedLines
    Invoke-LocalGuardCompose -Arguments @(
        'run', '--rm', 'admin-cli', 'python', '-m', 'localguard_api.cli',
        'sync-mcp-token'
    )
}
catch {
    Write-LocalGuardEnvironment -Lines $originalLines
    try {
        Invoke-LocalGuardCompose -Arguments @(
            'run', '--rm', 'admin-cli', 'python', '-m', 'localguard_api.cli',
            'sync-mcp-token'
        )
    }
    catch {
        throw 'MCP token rotation and automatic database rollback both failed. Stop the app and rerun bootstrap before using MCP.'
    }
    throw
}
finally {
    $rotatedSecret = $null
}

Write-Host 'The local MCP bearer was rotated, prior bootstrap bearers were revoked, and no value was printed.'

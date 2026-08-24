. (Join-Path $PSScriptRoot 'common.ps1')
Assert-DockerEngine
Invoke-LocalGuardCompose -Arguments @(
    '--profile', 'app', 'up', '-d', '--build', '--wait', '--wait-timeout', '300'
)
Invoke-LocalGuardCompose -Arguments @('--profile', 'app', 'ps')

$apiHealth = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health/ready' -TimeoutSec 5
$webResponse = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:3000/login' -TimeoutSec 5
$mcpSocket = [Net.Sockets.TcpClient]::new()
try {
    $mcpSocket.Connect('127.0.0.1', 8001)
}
finally {
    $mcpSocket.Dispose()
}
$artifact = Write-VerificationJson -Name 'health.json' -Value ([ordered]@{
    timestamp = (Get-Date).ToUniversalTime().ToString('o')
    api = $apiHealth
    web_status = $webResponse.StatusCode
    mcp_tcp = 'connected'
})
Write-Host 'LocalGuard AI: http://localhost:3000'
Write-Host 'FastAPI docs (development only): http://localhost:8000/docs'
Write-Host 'MCP Streamable HTTP: http://localhost:8001/mcp'
Write-Host "Health evidence: $artifact"

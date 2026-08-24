. (Join-Path $PSScriptRoot 'common.ps1')
Assert-DockerEngine
Invoke-LocalGuardCompose -Arguments @('--profile', 'app', 'stop')
Write-Host 'LocalGuard containers stopped; project volumes were preserved.'

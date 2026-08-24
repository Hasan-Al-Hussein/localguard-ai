param([switch]$Reset)

. (Join-Path $PSScriptRoot 'common.ps1')
Assert-DockerEngine
$configured = Select-String -LiteralPath (Join-Path $script:ProjectRoot '.env') -Pattern '^AI_PROVIDER=(.+)$'
if (-not $configured -or $configured.Matches[0].Groups[1].Value -ne 'ollama') {
    throw 'The demo path refuses the fake provider. Set AI_PROVIDER=ollama and bootstrap the local model.'
}
Invoke-LocalGuardCompose -Arguments @(
    '--profile', 'app', 'up', '-d', '--build', '--wait', '--wait-timeout', '300'
)
$arguments = @('run', '--rm', 'admin-cli', 'python', '-m', 'localguard_api.cli', 'demo')
if ($Reset) { $arguments += '--reset' }
Invoke-LocalGuardCompose -Arguments $arguments

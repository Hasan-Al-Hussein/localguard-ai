param([ValidateSet('unit', 'integration', 'e2e', 'all')][string]$Suite = 'all')

. (Join-Path $PSScriptRoot 'common.ps1')
Assert-DockerEngine

$buildServices = @()
if ($Suite -in @('unit', 'integration', 'all')) { $buildServices += 'api' }
if ($Suite -in @('e2e', 'all')) { $buildServices += @('api', 'web') }
Invoke-LocalGuardCompose -Arguments (@('build') + @($buildServices | Select-Object -Unique))

if ($Suite -in @('unit', 'all')) {
    Invoke-LocalGuardCompose -Arguments @(
        'run', '--rm', '--no-deps',
        '-e', 'APP_ENV=test',
        '-e', 'ALLOW_TEST_PROVIDERS=true',
        '-e', 'AI_PROVIDER=deterministic',
        '-e', 'EMBEDDING_PROVIDER=deterministic',
        'api', 'python', '-m', 'pytest', '-m', 'not integration and not real_model',
        '--junitxml=artifacts/pytest-unit.xml'
    )
    Invoke-LocalGuardCompose -Arguments @(
        'run', '--rm', '--no-deps',
        '-e', 'APP_ENV=test',
        '-e', 'ALLOW_TEST_PROVIDERS=true',
        '-e', 'AI_PROVIDER=deterministic',
        '-e', 'EMBEDDING_PROVIDER=deterministic',
        'api', 'python', 'packages/contracts/scripts/export_openapi.py',
        '--check', 'packages/contracts/openapi.json'
    )
    foreach ($command in @('contracts', 'lint', 'typecheck', 'test')) {
        Invoke-LocalGuardNpm -Arguments @('run', $command)
    }
}
if ($Suite -in @('integration', 'all')) {
    Invoke-LocalGuardCompose -Arguments @(
        'up', '-d', '--wait', '--wait-timeout', '120', 'db', 'redis'
    )
    Invoke-LocalGuardCompose -Arguments @(
        'run', '--rm',
        '-e', 'APP_ENV=test',
        '-e', 'ALLOW_TEST_PROVIDERS=true',
        '-e', 'AI_PROVIDER=deterministic',
        '-e', 'EMBEDDING_PROVIDER=deterministic',
        '-e', 'RUN_DB_INTEGRATION=1',
        '-e', 'RUN_INTEGRATION_TESTS=1',
        'api', 'python', '-m', 'pytest', '-m', 'integration',
        '--junitxml=artifacts/pytest-integration.xml'
    )
}
if ($Suite -in @('e2e', 'all')) {
    Assert-LocalGuardCommand -Name npx -Recovery 'npx is included with the supported Node.js installation.'
    Invoke-LocalGuardNpm -Arguments @('exec', '--', 'playwright', 'install', 'chromium')
    Write-Host 'Running deterministic UI/browser contract journeys against intercepted API fixtures.'
    Invoke-LocalGuardNpm -Arguments @(
        'run', 'test:e2e:ui-contract', '--workspace', '@localguard/web'
    )

    $localConfigPath = Join-Path $script:ProjectRoot '.env'
    if (-not (Test-Path -LiteralPath $localConfigPath)) {
        throw 'The unmocked browser gate requires the ignored .env created by scripts/bootstrap.ps1.'
    }
    $adminPasswordLine = Get-Content -LiteralPath $localConfigPath |
        Where-Object { $_ -match '^BOOTSTRAP_ADMIN_PASSWORD=' } |
        Select-Object -First 1
    $adminPassword = if ($adminPasswordLine) { ($adminPasswordLine -split '=', 2)[1] } else { $null }
    if (-not $adminPassword -or $adminPassword -eq 'generated-by-bootstrap') {
        throw 'The unmocked browser gate requires the generated demo-admin password in .env.'
    }

    $previousAppEnv = $env:APP_ENV
    $previousAllowTestProviders = $env:ALLOW_TEST_PROVIDERS
    $previousAiProvider = $env:AI_PROVIDER
    $previousEmbeddingProvider = $env:EMBEDDING_PROVIDER
    $previousRealStack = $env:LOCALGUARD_REAL_STACK
    $previousBaseUrl = $env:LOCALGUARD_BASE_URL
    $previousUsername = $env:LOCALGUARD_E2E_USERNAME
    $previousPassword = $env:BOOTSTRAP_ADMIN_PASSWORD
    try {
        $env:APP_ENV = 'test'
        $env:ALLOW_TEST_PROVIDERS = 'true'
        $env:AI_PROVIDER = 'deterministic'
        $env:EMBEDDING_PROVIDER = 'deterministic'
        Invoke-LocalGuardCompose -Arguments @(
            '--profile', 'app', 'up', '-d', '--wait', '--wait-timeout', '300'
        )
        $env:LOCALGUARD_REAL_STACK = '1'
        $env:LOCALGUARD_BASE_URL = 'http://127.0.0.1:3000'
        $env:LOCALGUARD_E2E_USERNAME = 'demo-admin'
        $env:BOOTSTRAP_ADMIN_PASSWORD = $adminPassword
        Write-Host 'Running the unmocked production-stack browser journey.'
        Invoke-LocalGuardNpm -Arguments @(
            'run', 'test:e2e', '--workspace', '@localguard/web'
        )
    }
    finally {
        $env:APP_ENV = $previousAppEnv
        $env:ALLOW_TEST_PROVIDERS = $previousAllowTestProviders
        $env:AI_PROVIDER = $previousAiProvider
        $env:EMBEDDING_PROVIDER = $previousEmbeddingProvider
        $env:LOCALGUARD_REAL_STACK = $previousRealStack
        $env:LOCALGUARD_BASE_URL = $previousBaseUrl
        $env:LOCALGUARD_E2E_USERNAME = $previousUsername
        $env:BOOTSTRAP_ADMIN_PASSWORD = $previousPassword
    }
}

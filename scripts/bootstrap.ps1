param([switch]$SkipModelPull, [switch]$ConfigOnly)

. (Join-Path $PSScriptRoot 'common.ps1')
Assert-LocalGuardCommand -Name docker -Recovery 'Free install: winget install --exact --id Docker.DockerDesktop'
Assert-LocalGuardCommand -Name node -Recovery 'Free install: winget install --exact --id OpenJS.NodeJS.LTS'
Assert-LocalGuardCommand -Name npm -Recovery 'npm is included with the supported Node.js installation.'
Assert-DockerEngine

$envPath = Join-Path $script:ProjectRoot '.env'
$createdEnv = $false
if (-not (Test-Path -LiteralPath $envPath)) {
    $dbPassword = New-LocalSecret
    $adminPassword = New-LocalSecret -Bytes 18
    $reviewerPassword = New-LocalSecret -Bytes 18
    $viewerPassword = New-LocalSecret -Bytes 18
    $mcpToken = New-LocalSecret -Bytes 32
    $content = Get-Content -LiteralPath (Join-Path $script:ProjectRoot '.env.example') -Raw
    $content = $content.Replace('generate-a-long-random-local-password', $dbPassword)
    $content = $content.Replace('BOOTSTRAP_ADMIN_PASSWORD=generated-by-bootstrap', "BOOTSTRAP_ADMIN_PASSWORD=$adminPassword")
    $content = $content.Replace('BOOTSTRAP_REVIEWER_PASSWORD=generated-by-bootstrap', "BOOTSTRAP_REVIEWER_PASSWORD=$reviewerPassword")
    $content = $content.Replace('BOOTSTRAP_VIEWER_PASSWORD=generated-by-bootstrap', "BOOTSTRAP_VIEWER_PASSWORD=$viewerPassword")
    $content = $content.Replace('MCP_BOOTSTRAP_TOKEN=generated-by-bootstrap', "MCP_BOOTSTRAP_TOKEN=$mcpToken")
    Set-Content -LiteralPath $envPath -Value $content -Encoding utf8
    $createdEnv = $true
    Write-Host 'Generated local-only credentials in ignored .env; values were not printed or logged.'
}

if ($ConfigOnly) {
    $artifact = Write-VerificationJson -Name 'bootstrap-config.json' -Value ([ordered]@{
        timestamp = (Get-Date).ToUniversalTime().ToString('o')
        docker_server = (docker info --format '{{.ServerVersion}}')
        node = (node --version)
        config_created = $createdEnv
        secrets_printed = $false
    })
    Write-Host "Local configuration ready: $artifact"
    exit 0
}

Invoke-LocalGuardNpm -Arguments @('ci')
Invoke-LocalGuardCompose -Arguments @('pull', 'db', 'redis')
Invoke-LocalGuardCompose -Arguments @('up', '-d', '--wait', '--wait-timeout', '120', 'db', 'redis')
Invoke-LocalGuardCompose -Arguments @('build', 'api', 'web')
Invoke-LocalGuardCompose -Arguments @(
    'run', '--rm', '--no-deps', 'api', 'python',
    'packages/contracts/scripts/export_openapi.py', '--check', 'packages/contracts/openapi.json'
)
Invoke-LocalGuardNpm -Arguments @('run', 'contracts')
Invoke-LocalGuardCompose -Arguments @('run', '--rm', 'api', 'alembic', 'upgrade', 'head')
Invoke-LocalGuardCompose -Arguments @('run', '--rm', 'api', 'alembic', 'check')
Invoke-LocalGuardCompose -Arguments @('run', '--rm', 'api', 'python', '-m', 'localguard_api.cli', 'setup-checkpoints')
Invoke-LocalGuardCompose -Arguments @('run', '--rm', 'admin-cli', 'python', '-m', 'localguard_api.cli', 'seed')

$verifiedModels = @()
$modelLockArtifact = $null
if (-not $SkipModelPull) {
    $environmentLines = Get-Content -LiteralPath $envPath
    $chatModel = (($environmentLines | Where-Object { $_ -like 'OLLAMA_CHAT_MODEL=*' }) -split '=', 2)[1]
    $embedModel = (($environmentLines | Where-Object { $_ -like 'OLLAMA_EMBED_MODEL=*' }) -split '=', 2)[1]
    $runtimeLock = Get-Content -LiteralPath (Join-Path $script:ProjectRoot 'docs\runtime-lock.json') -Raw | ConvertFrom-Json
    $expectedModels = @(
        [ordered]@{
            configured = $chatModel
            locked = $runtimeLock.models.generation_selected.tag
            digest = $runtimeLock.models.generation_selected.manifest_sha256
        },
        [ordered]@{
            configured = $embedModel
            locked = $runtimeLock.models.embedding.tag
            digest = $runtimeLock.models.embedding.manifest_sha256
        }
    )
    Push-Location $script:ProjectRoot
    try {
        docker compose -f docker-compose.yml -f docker-compose.bootstrap.yml --profile app up -d --wait --wait-timeout 120 ollama
        if ($LASTEXITCODE -ne 0) { throw 'Could not start the CPU-only Ollama bootstrap service.' }
        foreach ($model in $expectedModels) {
            if ($model.configured -ne $model.locked) {
                throw "Configured model '$($model.configured)' does not match runtime lock '$($model.locked)'."
            }
            docker compose exec -T ollama ollama pull $model.configured
            if ($LASTEXITCODE -ne 0) { throw "Required local model '$($model.configured)' could not be pulled." }

            $modelParts = $model.configured -split ':', 2
            if ($modelParts.Count -ne 2 -or $modelParts[0] -notmatch '^[a-zA-Z0-9._/-]+$' -or $modelParts[1] -notmatch '^[a-zA-Z0-9._-]+$') {
                throw "Model identifier '$($model.configured)' cannot be verified safely."
            }
            $manifestPath = "/root/.ollama/models/manifests/registry.ollama.ai/library/$($modelParts[0])/$($modelParts[1])"
            $digestOutput = docker compose exec -T ollama sha256sum $manifestPath
            if ($LASTEXITCODE -ne 0) { throw "Could not hash the local manifest for '$($model.configured)'." }
            $actualDigest = (($digestOutput | Select-Object -First 1) -split '\s+')[0].ToLowerInvariant()
            if ($actualDigest -ne $model.digest.ToLowerInvariant()) {
                throw "Manifest digest mismatch for '$($model.configured)'; expected $($model.digest), received $actualDigest."
            }
            $verifiedModels += [ordered]@{ tag = $model.configured; manifest_sha256 = $actualDigest }
        }
        docker compose exec -T ollama ollama list
        if ($LASTEXITCODE -ne 0) { throw 'Could not list the verified local models.' }
        docker compose -f docker-compose.yml -f docker-compose.bootstrap.yml stop ollama
        if ($LASTEXITCODE -ne 0) { throw 'Could not stop the temporary model-download service.' }
    }
    finally { Pop-Location }
    $modelLockArtifact = Write-VerificationJson -Name 'model-lock.json' -Value ([ordered]@{
        timestamp = (Get-Date).ToUniversalTime().ToString('o')
        models = $verifiedModels
        runtime_lock = 'docs/runtime-lock.json'
    })
}

$artifact = Write-VerificationJson -Name 'bootstrap.json' -Value ([ordered]@{
    schema_version = '1.0'
    bootstrap_complete = $true
    timestamp = (Get-Date).ToUniversalTime().ToString('o')
    docker_server = (docker info --format '{{.ServerVersion}}')
    node = (node --version)
    runtime_lock_sha256 = (Get-FileHash -LiteralPath (Join-Path $script:ProjectRoot 'docs\runtime-lock.json') -Algorithm SHA256).Hash.ToLowerInvariant()
    model_pull_skipped = [bool]$SkipModelPull
    verified_models = $verifiedModels
    model_lock_artifact = $modelLockArtifact
    secrets_written = $createdEnv
})
Write-Host "Bootstrap verified: $artifact"

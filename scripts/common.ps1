Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$script:ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

function Assert-LocalGuardCommand {
    param([Parameter(Mandatory)][string]$Name, [string]$Recovery)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' was not found. $Recovery"
    }
}

function Assert-DockerEngine {
    docker info --format '{{.ServerVersion}}' *> $null
    if ($LASTEXITCODE -ne 0) {
        $userDesktop = Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\Docker Desktop.exe'
        $systemDesktop = Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'
        $desktop = @($userDesktop, $systemDesktop) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
        $startHint = if ($desktop) { "Start '$desktop'" } else { 'Start Docker Desktop' }
        throw "Docker Desktop's Linux engine is not ready. $startHint, wait for Engine running, then retry. Free reinstall command if needed: winget install --exact --id Docker.DockerDesktop"
    }
}

function Invoke-LocalGuardCompose {
    param([Parameter(ValueFromRemainingArguments)][string[]]$Arguments)
    Push-Location $script:ProjectRoot
    try {
        & docker compose @Arguments
        if ($LASTEXITCODE -ne 0) { throw "docker compose failed with exit code $LASTEXITCODE" }
    }
    finally { Pop-Location }
}

function Invoke-LocalGuardNpm {
    param([Parameter(ValueFromRemainingArguments)][string[]]$Arguments)
    Push-Location $script:ProjectRoot
    try {
        & npm @Arguments
        if ($LASTEXITCODE -ne 0) { throw "npm failed with exit code $LASTEXITCODE" }
    }
    finally { Pop-Location }
}

function Assert-LocalGuardOrdinaryDirectory {
    param([Parameter(Mandatory)][string]$Path)
    $item = Get-Item -LiteralPath $Path -Force
    if (-not $item.PSIsContainer) {
        throw "Expected an ordinary directory: $Path"
    }
    if (
        (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) -or
        -not [string]::IsNullOrEmpty([string]$item.LinkType)
    ) {
        throw "Directory must not be a symbolic link, junction, or reparse point: $Path"
    }
}

function Resolve-LocalGuardEvaluationResultsPath {
    param([Parameter(Mandatory)][string]$ProjectRoot)
    $rootPath = [IO.Path]::GetFullPath($ProjectRoot)
    $evalsPath = [IO.Path]::GetFullPath((Join-Path $rootPath 'evals'))
    Assert-LocalGuardOrdinaryDirectory -Path $rootPath
    Assert-LocalGuardOrdinaryDirectory -Path $evalsPath

    $expectedPath = [IO.Path]::GetFullPath((Join-Path $evalsPath 'results'))
    [IO.Directory]::CreateDirectory($expectedPath) | Out-Null
    foreach ($componentPath in @($rootPath, $evalsPath, $expectedPath)) {
        Assert-LocalGuardOrdinaryDirectory -Path $componentPath
    }
    $resultsItem = Get-Item -LiteralPath $expectedPath -Force
    $resolvedPath = [IO.Path]::GetFullPath($resultsItem.FullName)
    if (-not [StringComparer]::OrdinalIgnoreCase.Equals($resolvedPath, $expectedPath)) {
        throw 'Evaluation results path resolved outside the exact repository results directory.'
    }
    return $resolvedPath
}

function Initialize-LocalGuardEvaluationResults {
    $resolvedPath = Resolve-LocalGuardEvaluationResultsPath -ProjectRoot $script:ProjectRoot

    $mount = "type=bind,source=$resolvedPath,target=/workspace/evals/results"
    $maintenanceArguments = @(
        'run', '--rm', '--network', 'none', '--read-only',
        '--user', '0:0', '--security-opt', 'no-new-privileges:true',
        '--cap-drop', 'ALL', '--cap-add', 'CHOWN', '--cap-add', 'FOWNER',
        '--cap-add', 'DAC_READ_SEARCH',
        '--mount', $mount,
        'localguard-backend:dev',
        'python', '-m', 'scripts.prepare_evaluation_results', 'normalize'
    )
    & docker @maintenanceArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Evaluation results maintenance failed with exit code $LASTEXITCODE"
    }

    $probeArguments = @(
        'run', '--rm', '--network', 'none', '--read-only',
        '--user', '10001:10001', '--security-opt', 'no-new-privileges:true',
        '--cap-drop', 'ALL', '--mount', $mount,
        'localguard-backend:dev',
        'python', '-m', 'scripts.prepare_evaluation_results', 'probe'
    )
    & docker @probeArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Non-root evaluation results probe failed with exit code $LASTEXITCODE"
    }
}

function New-LocalSecret {
    param([int]$Bytes = 24)
    $buffer = New-Object byte[] $Bytes
    [Security.Cryptography.RandomNumberGenerator]::Fill($buffer)
    return [Convert]::ToBase64String($buffer).TrimEnd('=').Replace('+', '-').Replace('/', '_')
}

function Write-VerificationJson {
    param([Parameter(Mandatory)][string]$Name, [Parameter(Mandatory)]$Value)
    $directory = Join-Path $script:ProjectRoot 'artifacts\verification'
    New-Item -ItemType Directory -Force -Path $directory | Out-Null
    $path = Join-Path $directory $Name
    $Value | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $path -Encoding utf8
    return $path
}

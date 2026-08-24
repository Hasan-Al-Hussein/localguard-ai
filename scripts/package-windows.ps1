[CmdletBinding()]
param(
    [string]$Version,
    [string]$DestinationDirectory
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$packageJson = Get-Content -LiteralPath (Join-Path $projectRoot 'package.json') -Raw | ConvertFrom-Json
if ([string]::IsNullOrWhiteSpace($Version)) { $Version = [string]$packageJson.version }
if ($Version -notmatch '^\d+\.\d+\.\d+(?:[-.][A-Za-z0-9]+)*$') { throw "Package version is not safe: $Version" }
if ([string]::IsNullOrWhiteSpace($DestinationDirectory)) {
    $DestinationDirectory = Join-Path $projectRoot 'dist'
}
[IO.Directory]::CreateDirectory($DestinationDirectory) | Out-Null
$destinationRoot = (Resolve-Path $DestinationDirectory).Path

$packageName = "LocalGuard-AI-Windows-v$Version"
$archivePath = Join-Path $destinationRoot "$packageName.zip"
$hashPath = "$archivePath.sha256"
$stagingParent = Join-Path $destinationRoot (".staging-" + [Guid]::NewGuid().ToString('N'))
$stagingRoot = Join-Path $stagingParent $packageName
[IO.Directory]::CreateDirectory($stagingRoot) | Out-Null

$rootFiles = @(
    '.dockerignore', '.editorconfig', '.env.example', '.gitattributes', '.gitignore', '.python-version',
    'alembic.ini', 'CONTRIBUTING.md', 'docker-compose.bootstrap.yml', 'docker-compose.evaluation.yml',
    'docker-compose.yml', 'Dockerfile.backend', 'LICENSE', 'package-lock.json', 'package.json',
    'pyproject.toml', 'README.md', 'README-WINDOWS.txt', 'requirements.lock',
    'START-LOCALGUARD.cmd', 'STOP-LOCALGUARD.cmd', 'VIEW-LOCALGUARD-LOGIN.cmd'
)
$sourceDirectories = @('.github', 'apps', 'docs', 'evals', 'fixtures', 'packages', 'scripts', 'services', 'tests')
$excludedSegments = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
@('node_modules', '.next', '__pycache__', 'output', 'results', 'playwright-report', 'test-results') | ForEach-Object { [void]$excludedSegments.Add($_) }

function Copy-LocalGuardPackageFile {
    param([Parameter(Mandatory = $true)][string]$SourcePath, [Parameter(Mandatory = $true)][string]$RelativePath)
    $sourceItem = Get-Item -LiteralPath $SourcePath -Force
    if (($sourceItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or -not [string]::IsNullOrEmpty([string]$sourceItem.LinkType)) {
        throw "Package source must not contain links or reparse points: $SourcePath"
    }
    $targetPath = Join-Path $stagingRoot $RelativePath
    [IO.Directory]::CreateDirectory((Split-Path $targetPath -Parent)) | Out-Null
    Copy-Item -LiteralPath $SourcePath -Destination $targetPath
}

try {
    foreach ($relativePath in $rootFiles) {
        $sourcePath = Join-Path $projectRoot $relativePath
        if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) { throw "Required package file is missing: $relativePath" }
        Copy-LocalGuardPackageFile -SourcePath $sourcePath -RelativePath $relativePath
    }

    foreach ($directoryName in $sourceDirectories) {
        $sourceDirectory = Join-Path $projectRoot $directoryName
        if (-not (Test-Path -LiteralPath $sourceDirectory -PathType Container)) { throw "Required package directory is missing: $directoryName" }
        foreach ($file in Get-ChildItem -LiteralPath $sourceDirectory -Recurse -Force -File) {
            $relativePath = [IO.Path]::GetRelativePath($projectRoot, $file.FullName)
            $segments = $relativePath -split '[\\/]'
            if (@($segments | Where-Object { $excludedSegments.Contains($_) }).Count -gt 0) { continue }
            Copy-LocalGuardPackageFile -SourcePath $file.FullName -RelativePath $relativePath
        }
    }

    $manifestFiles = @(Get-ChildItem -LiteralPath $stagingRoot -Recurse -File | Sort-Object FullName | ForEach-Object {
        [ordered]@{
            path = [IO.Path]::GetRelativePath($stagingRoot, $_.FullName).Replace('\', '/')
            bytes = $_.Length
            sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    })
    [ordered]@{
        schema_version = '1.0'
        product = 'LocalGuard AI'
        package_version = $Version
        created_at = (Get-Date).ToUniversalTime().ToString('o')
        file_count = $manifestFiles.Count
        files = $manifestFiles
    } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $stagingRoot 'PACKAGE-MANIFEST.json') -Encoding utf8

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    if (Test-Path -LiteralPath $archivePath -PathType Leaf) { Remove-Item -LiteralPath $archivePath }
    [IO.Compression.ZipFile]::CreateFromDirectory($stagingParent, $archivePath, [IO.Compression.CompressionLevel]::Optimal, $false)

    $archiveEntries = [IO.Compression.ZipFile]::OpenRead($archivePath)
    try {
        $forbidden = @($archiveEntries.Entries | Where-Object {
            $_.FullName -match '(^|/)(\.env|\.git|node_modules|\.next|results|artifacts)(/|$)'
        })
        if ($forbidden.Count -gt 0) { throw "Archive contains forbidden local state: $($forbidden[0].FullName)" }
        if (-not @($archiveEntries.Entries | Where-Object { $_.FullName -eq "$packageName/START-LOCALGUARD.cmd" }).Count) {
            throw 'Archive does not contain the Windows launcher at its package root.'
        }
    }
    finally { $archiveEntries.Dispose() }

    $archiveHash = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
    "$archiveHash  $([IO.Path]::GetFileName($archivePath))" | Set-Content -LiteralPath $hashPath -Encoding ascii
    Write-Host "Windows package: $archivePath"
    Write-Host "SHA-256: $archiveHash"
}
finally {
    if (Test-Path -LiteralPath $stagingParent -PathType Container) {
        $resolvedStaging = (Resolve-Path $stagingParent).Path
        $resolvedDestination = (Resolve-Path $destinationRoot).Path
        $expectedPrefix = $resolvedDestination.TrimEnd('\') + '\.staging-'
        if (-not $resolvedStaging.StartsWith($expectedPrefix, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to remove unexpected staging directory: $resolvedStaging"
        }
        Remove-Item -LiteralPath $resolvedStaging -Recurse -Force
    }
}

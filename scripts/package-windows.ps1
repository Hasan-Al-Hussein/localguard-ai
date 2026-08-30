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
$operationId = [Guid]::NewGuid().ToString('N')
$candidateArchivePath = Join-Path $destinationRoot ".$packageName.candidate-$operationId.zip"
$candidateHashPath = "$candidateArchivePath.sha256"
$stagingParent = Join-Path $destinationRoot (".staging-" + $operationId)
$stagingRoot = Join-Path $stagingParent $packageName

$rootFiles = @(
    '.dockerignore', '.editorconfig', '.env.example', '.gitattributes', '.gitignore', '.python-version',
    'alembic.ini', 'CITATION.cff', 'CONTRIBUTING.md', 'docker-compose.bootstrap.yml', 'docker-compose.evaluation.yml',
    'docker-compose.yml', 'Dockerfile.backend', 'LICENSE', 'package-lock.json', 'package.json',
    'NOTICE.md', 'pyproject.toml', 'README.md', 'README-WINDOWS.txt', 'requirements.lock', 'SECURITY.md',
    'START-LOCALGUARD.cmd', 'STOP-LOCALGUARD.cmd', 'VIEW-LOCALGUARD-LOGIN.cmd',
    'demo-video\output\product-demo.mp4', 'demo-video\output\product-demo.srt'
)
$sourceDirectories = @('.github', 'apps', 'docs', 'evals', 'fixtures', 'packages', 'scripts', 'services', 'tests')
$excludedSegments = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
@(
    'node_modules', '.next', '.venv', '__pycache__', 'build', 'out', 'output', 'results',
    'playwright-report', 'project-handoff', 'test-results'
) | ForEach-Object { [void]$excludedSegments.Add($_) }

foreach ($directoryName in $sourceDirectories) {
    $sourceDirectory = [IO.Path]::GetFullPath((Join-Path $projectRoot $directoryName))
    $sourcePrefix = $sourceDirectory.TrimEnd('\') + '\'
    if (
        $destinationRoot.Equals($sourceDirectory, [StringComparison]::OrdinalIgnoreCase) -or
        $destinationRoot.StartsWith($sourcePrefix, [StringComparison]::OrdinalIgnoreCase)
    ) {
        throw "Package destination must not be inside an included source directory: $destinationRoot"
    }
}
[IO.Directory]::CreateDirectory($stagingRoot) | Out-Null

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
            if (
                $file.Name.StartsWith('.env', [StringComparison]::OrdinalIgnoreCase) -and
                -not $file.Name.Equals('.env.example', [StringComparison]::OrdinalIgnoreCase)
            ) {
                throw "Refusing to package a local environment file: $($file.FullName)"
            }
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
    [IO.Compression.ZipFile]::CreateFromDirectory($stagingParent, $candidateArchivePath, [IO.Compression.CompressionLevel]::Optimal, $false)

    $archiveEntries = [IO.Compression.ZipFile]::OpenRead($candidateArchivePath)
    try {
        $forbidden = @($archiveEntries.Entries | Where-Object {
            $entryPath = $_.FullName.Replace('\', '/')
            $leafName = [IO.Path]::GetFileName($entryPath)
            ($leafName.StartsWith('.env', [StringComparison]::OrdinalIgnoreCase) -and -not $leafName.Equals('.env.example', [StringComparison]::OrdinalIgnoreCase)) -or
            $entryPath -match '(^|/)(\.git|node_modules|\.next|\.venv|__pycache__|build|out|results|artifacts|project-handoff)(/|$)'
        })
        if ($forbidden.Count -gt 0) { throw "Archive contains forbidden local state: $($forbidden[0].FullName)" }
        if (-not @($archiveEntries.Entries | Where-Object { $_.FullName -eq "$packageName/START-LOCALGUARD.cmd" }).Count) {
            throw 'Archive does not contain the Windows launcher at its package root.'
        }
        foreach ($requiredDemoFile in @('product-demo.mp4', 'product-demo.srt')) {
            $expectedEntry = "$packageName/demo-video/output/$requiredDemoFile"
            if (-not @($archiveEntries.Entries | Where-Object { $_.FullName -eq $expectedEntry }).Count) {
                throw "Archive does not contain the final product demo asset: $requiredDemoFile"
            }
        }
        $allowedDemoEntries = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
        [void]$allowedDemoEntries.Add("$packageName/demo-video/output/product-demo.mp4")
        [void]$allowedDemoEntries.Add("$packageName/demo-video/output/product-demo.srt")
        $unexpectedDemoEntry = $archiveEntries.Entries | Where-Object {
            -not [string]::IsNullOrEmpty($_.Name) -and
            $_.FullName.Replace('\', '/').StartsWith("$packageName/demo-video/", [StringComparison]::Ordinal) -and
            -not $allowedDemoEntries.Contains($_.FullName.Replace('\', '/'))
        } | Select-Object -First 1
        if ($null -ne $unexpectedDemoEntry) {
            throw "Archive contains an unexpected demo asset: $($unexpectedDemoEntry.FullName)"
        }
    }
    finally { $archiveEntries.Dispose() }

    $archiveHash = (Get-FileHash -LiteralPath $candidateArchivePath -Algorithm SHA256).Hash.ToLowerInvariant()
    "$archiveHash  $([IO.Path]::GetFileName($archivePath))" | Set-Content -LiteralPath $candidateHashPath -Encoding ascii

    $backupArchivePath = "$archivePath.backup-$operationId"
    $backupHashPath = "$hashPath.backup-$operationId"
    $archiveBackedUp = $false
    $hashBackedUp = $false
    $archivePromoted = $false
    $hashPromoted = $false
    try {
        if (Test-Path -LiteralPath $archivePath -PathType Leaf) {
            Move-Item -LiteralPath $archivePath -Destination $backupArchivePath
            $archiveBackedUp = $true
        }
        if (Test-Path -LiteralPath $hashPath -PathType Leaf) {
            Move-Item -LiteralPath $hashPath -Destination $backupHashPath
            $hashBackedUp = $true
        }
        Move-Item -LiteralPath $candidateArchivePath -Destination $archivePath
        $archivePromoted = $true
        Move-Item -LiteralPath $candidateHashPath -Destination $hashPath
        $hashPromoted = $true
    }
    catch {
        if ($hashPromoted -and (Test-Path -LiteralPath $hashPath -PathType Leaf)) { Remove-Item -LiteralPath $hashPath }
        if ($archivePromoted -and (Test-Path -LiteralPath $archivePath -PathType Leaf)) { Remove-Item -LiteralPath $archivePath }
        if ($hashBackedUp) { Move-Item -LiteralPath $backupHashPath -Destination $hashPath }
        if ($archiveBackedUp) { Move-Item -LiteralPath $backupArchivePath -Destination $archivePath }
        throw
    }
    if ($hashBackedUp) { Remove-Item -LiteralPath $backupHashPath }
    if ($archiveBackedUp) { Remove-Item -LiteralPath $backupArchivePath }

    Write-Host "Windows package: $archivePath"
    Write-Host "SHA-256: $archiveHash"
}
finally {
    foreach ($candidatePath in @($candidateArchivePath, $candidateHashPath)) {
        if (Test-Path -LiteralPath $candidatePath -PathType Leaf) { Remove-Item -LiteralPath $candidatePath }
    }
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

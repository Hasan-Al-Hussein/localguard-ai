[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ArchivePath,
    [switch]$CheckPrerequisites,
    [switch]$KeepExtracted
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$resolvedArchive = (Resolve-Path $ArchivePath).Path
if ([IO.Path]::GetExtension($resolvedArchive) -ne '.zip') { throw 'The package validator requires a ZIP archive.' }
$archiveBaseName = [IO.Path]::GetFileNameWithoutExtension($resolvedArchive)
if ($archiveBaseName -notmatch '^LocalGuard-AI-Windows-v\d+\.\d+\.\d+(?:[-.][A-Za-z0-9]+)*$') {
    throw "Unexpected LocalGuard package name: $archiveBaseName"
}

$temporaryRoot = (Resolve-Path $env:TEMP).Path
$extractionRoot = Join-Path $temporaryRoot ("localguard-package-validation-" + [Guid]::NewGuid().ToString('N'))
[IO.Directory]::CreateDirectory($extractionRoot) | Out-Null
$packageRoot = Join-Path $extractionRoot $archiveBaseName

Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [IO.Compression.ZipFile]::OpenRead($resolvedArchive)
try {
    foreach ($entry in $archive.Entries) {
        $entryPath = $entry.FullName.Replace('\', '/')
        $unsafeEntry = $entryPath.StartsWith('/', [StringComparison]::Ordinal) -or $entryPath.Contains('../', [StringComparison]::Ordinal) -or (-not $entryPath.StartsWith("$archiveBaseName/", [StringComparison]::Ordinal))
        if ($unsafeEntry) {
            throw "Unsafe or unexpected archive entry: $entryPath"
        }
    }
}
finally {
    $archive.Dispose()
}

try {
    [IO.Compression.ZipFile]::ExtractToDirectory($resolvedArchive, $extractionRoot)
    if (-not (Test-Path -LiteralPath $packageRoot -PathType Container)) { throw 'Package root missing after extraction.' }

    $manifestPath = Join-Path $packageRoot 'PACKAGE-MANIFEST.json'
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    if ($manifest.product -ne 'LocalGuard AI' -or $manifest.schema_version -ne '1.0') { throw 'Package manifest identity is invalid.' }
    if ([int]$manifest.file_count -ne @($manifest.files).Count) { throw 'Package manifest file count is inconsistent.' }

    $manifestPaths = @($manifest.files | ForEach-Object { ([string]$_.path).Replace('\', '/') })
    if (@($manifestPaths | Sort-Object -Unique).Count -ne $manifestPaths.Count) {
        throw 'Package manifest contains duplicate paths.'
    }

    foreach ($record in $manifest.files) {
        $manifestRecordPath = ([string]$record.path).Replace('\', '/')
        if (
            [string]::IsNullOrWhiteSpace($manifestRecordPath) -or
            $manifestRecordPath.StartsWith('/', [StringComparison]::Ordinal) -or
            $manifestRecordPath.Contains('../', [StringComparison]::Ordinal)
        ) {
            throw "Unsafe package manifest path: $manifestRecordPath"
        }
        $relativePath = $manifestRecordPath.Replace('/', [IO.Path]::DirectorySeparatorChar)
        $path = Join-Path $packageRoot $relativePath
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Manifest file missing: $($record.path)" }
        $actualHash = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actualHash -ne $record.sha256) { throw "Hash mismatch: $($record.path)" }
        if ((Get-Item -LiteralPath $path).Length -ne [long]$record.bytes) { throw "Byte-length mismatch: $($record.path)" }
    }

    $forbidden = @(Get-ChildItem -LiteralPath $packageRoot -Recurse -Force | Where-Object {
        ($_.Name.StartsWith('.env', [StringComparison]::OrdinalIgnoreCase) -and -not $_.Name.Equals('.env.example', [StringComparison]::OrdinalIgnoreCase)) -or
        ($_.Name -in @('.git', 'node_modules', '.next', '.venv', '__pycache__', 'build', 'out', 'artifacts', 'project-handoff')) -or
        ($_.FullName -match '[\\/]evals[\\/]results(?:[\\/]|$)')
    })
    if ($forbidden.Count -gt 0) { throw "Forbidden local state: $($forbidden[0].FullName)" }

    $actualFiles = @(Get-ChildItem -LiteralPath $packageRoot -Recurse -File)
    $actualPayloadPaths = @($actualFiles | Where-Object { $_.FullName -ne $manifestPath } | ForEach-Object {
        [IO.Path]::GetRelativePath($packageRoot, $_.FullName).Replace('\', '/')
    })
    $payloadDifference = @(Compare-Object `
        -ReferenceObject @($manifestPaths | Sort-Object) `
        -DifferenceObject @($actualPayloadPaths | Sort-Object) `
        -CaseSensitive)
    if ($payloadDifference.Count -gt 0) {
        throw 'Extracted package file set does not exactly match the manifest.'
    }
    if (-not (Test-Path -LiteralPath (Join-Path $packageRoot 'START-LOCALGUARD.cmd') -PathType Leaf)) {
        throw 'Windows launcher is missing from the extracted package.'
    }
    foreach ($requiredDemoFile in @('product-demo.mp4', 'product-demo.srt')) {
        $demoPath = Join-Path $packageRoot "demo-video\output\$requiredDemoFile"
        if (-not (Test-Path -LiteralPath $demoPath -PathType Leaf)) {
            throw "Final product demo asset is missing: $requiredDemoFile"
        }
    }
    $allowedDemoPaths = @(
        'demo-video/output/product-demo.mp4',
        'demo-video/output/product-demo.srt'
    )
    $actualDemoPaths = @($actualPayloadPaths | Where-Object { $_.StartsWith('demo-video/', [StringComparison]::Ordinal) })
    $demoDifference = @(Compare-Object `
        -ReferenceObject @($allowedDemoPaths | Sort-Object) `
        -DifferenceObject @($actualDemoPaths | Sort-Object) `
        -CaseSensitive)
    if ($demoDifference.Count -gt 0) {
        throw 'Package contains unexpected or missing demo-video assets.'
    }
    if (Test-Path -LiteralPath (Join-Path $packageRoot 'artifacts\verification\bootstrap.json')) {
        throw 'Fresh package unexpectedly contains a local bootstrap completion record.'
    }

    Push-Location $packageRoot
    try {
        docker compose --env-file .env.example config --quiet
        if ($LASTEXITCODE -ne 0) { throw 'Extracted Docker Compose configuration is invalid.' }
        if ($CheckPrerequisites) {
            & powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File '.\scripts\first-run-windows.ps1' -CheckOnly -NoOpen
            if ($LASTEXITCODE -ne 0) { throw 'Extracted fresh-machine prerequisite check failed.' }
        }
    }
    finally {
        Pop-Location
    }

    Write-Host "PACKAGE_VALIDATION_PASS package=$archiveBaseName files=$($actualFiles.Count) forbidden_local_state=0 compose=valid"
    if ($KeepExtracted) { Write-Host "Extracted package retained at: $packageRoot" }
}
finally {
    if (-not $KeepExtracted -and (Test-Path -LiteralPath $extractionRoot -PathType Container)) {
        $resolvedExtraction = (Resolve-Path $extractionRoot).Path
        $expectedPrefix = $temporaryRoot.TrimEnd('\') + '\localguard-package-validation-'
        if (-not $resolvedExtraction.StartsWith($expectedPrefix, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to remove unexpected validation directory: $resolvedExtraction"
        }
        [IO.Directory]::Delete($resolvedExtraction, $true)
    }
}

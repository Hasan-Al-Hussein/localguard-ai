param(
    [Uri]$BaseUrl = 'http://127.0.0.1:8000',
    [ValidateRange(30, 3600)][int]$TimeoutSeconds = 900,
    [ValidateRange(5, 300)][int]$RequestTimeoutSeconds = 60,
    [string]$OutputPath = ''
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'common.ps1')
Assert-DockerEngine

function Get-BenchmarkRequestTimeout {
    param(
        [Parameter(Mandatory)][System.Diagnostics.Stopwatch]$Stopwatch,
        [Parameter(Mandatory)][int]$OverallTimeoutSeconds,
        [Parameter(Mandatory)][int]$PerRequestTimeoutSeconds
    )
    $remaining = $OverallTimeoutSeconds - $Stopwatch.Elapsed.TotalSeconds
    if ($remaining -lt 1) {
        throw "Indexing benchmark timed out after $OverallTimeoutSeconds seconds."
    }
    return [Math]::Max(1, [Math]::Min($PerRequestTimeoutSeconds, [Math]::Floor($remaining)))
}

$loopbackHosts = @('localhost', '127.0.0.1')
if (
    -not $BaseUrl.IsAbsoluteUri -or
    $BaseUrl.Scheme -ne 'http' -or
    $BaseUrl.Host -notin $loopbackHosts -or
    $BaseUrl.Port -ne 8000 -or
    $BaseUrl.UserInfo -or
    $BaseUrl.Query -or
    $BaseUrl.Fragment -or
    $BaseUrl.AbsolutePath -ne '/'
) {
    throw 'BaseUrl must be an HTTP loopback origin on port 8000 with no credentials, path, query, or fragment.'
}
$apiOrigin = $BaseUrl.GetLeftPart([System.UriPartial]::Authority)

$configPath = Join-Path $script:ProjectRoot '.env'
$manifestPath = Join-Path $script:ProjectRoot 'fixtures/documents/manifest.json'
if (-not (Test-Path -LiteralPath $configPath)) {
    throw 'The indexing benchmark requires the ignored .env created by scripts/bootstrap.ps1.'
}
if (-not (Test-Path -LiteralPath $manifestPath)) {
    throw 'The synthetic fixture manifest is missing.'
}

$credentialLines = @(
    Get-Content -LiteralPath $configPath |
        Where-Object { $_ -match '^BOOTSTRAP_REVIEWER_PASSWORD=' }
)
if ($credentialLines.Count -ne 1) {
    throw 'Expected exactly one BOOTSTRAP_REVIEWER_PASSWORD entry in .env.'
}
$reviewerPassword = ($credentialLines[0] -split '=', 2)[1]
if (-not $reviewerPassword -or $reviewerPassword -eq 'generated-by-bootstrap') {
    throw 'The indexing benchmark requires a generated demo-reviewer password.'
}

$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$fixtureRows = @(
    foreach ($entry in $manifest.documents) {
        $fixturePath = Join-Path $script:ProjectRoot $entry.path
        if (-not (Test-Path -LiteralPath $fixturePath)) {
            throw "Fixture is missing: $($entry.path)"
        }
        $actualHash = (Get-FileHash -LiteralPath $fixturePath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actualHash -ne $entry.sha256) {
            throw "Fixture digest mismatch: $($entry.path)"
        }
        [pscustomobject]@{
            source_id = [string]$entry.source_id
            path = [string]$entry.path
            sha256 = $actualHash
            absolute_path = $fixturePath
        }
    }
)
if ($fixtureRows.Count -ne 13) {
    throw "Expected 13 synthetic fixtures, found $($fixtureRows.Count)."
}

$session = [Microsoft.PowerShell.Commands.WebRequestSession]::new()
$httpClient = $null
$loginBody = @{
    username = 'demo-reviewer'
    password = $reviewerPassword
} | ConvertTo-Json
$csrfToken = $null
try {
$login = Invoke-RestMethod `
    -Uri "$apiOrigin/auth/login" `
    -Method Post `
    -ContentType 'application/json' `
    -Body $loginBody `
    -WebSession $session `
    -MaximumRedirection 0 `
    -TimeoutSec $RequestTimeoutSeconds
$reviewerPassword = $null
$loginBody = $null
$csrfToken = [string]$login.csrf_token
if (-not $csrfToken) {
    throw 'Login succeeded without returning the required CSRF token.'
}

$httpHandler = [System.Net.Http.HttpClientHandler]::new()
$httpHandler.AllowAutoRedirect = $false
$httpHandler.UseCookies = $true
$httpHandler.CookieContainer = $session.Cookies
$httpClient = [System.Net.Http.HttpClient]::new($httpHandler, $true)
$httpClient.BaseAddress = [Uri]$apiOrigin
$httpClient.Timeout = [System.Threading.Timeout]::InfiniteTimeSpan

if (-not $OutputPath) {
    $stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
    $OutputPath = Join-Path $script:ProjectRoot "artifacts/verification/index-benchmark-$stamp.json"
}
elseif (-not [System.IO.Path]::IsPathRooted($OutputPath)) {
    $OutputPath = Join-Path $script:ProjectRoot $OutputPath
}
$outputDirectory = Split-Path -Parent $OutputPath
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
if (Test-Path -LiteralPath $OutputPath) {
    throw "Refusing to overwrite an existing benchmark artifact: $OutputPath"
}

$headers = @{ 'X-CSRF-Token' = $csrfToken }
$observations = @()
$startedAt = (Get-Date).ToUniversalTime()
$timer = [System.Diagnostics.Stopwatch]::StartNew()

foreach ($fixture in $fixtureRows) {
    $requestTimeout = Get-BenchmarkRequestTimeout `
        -Stopwatch $timer `
        -OverallTimeoutSeconds $TimeoutSeconds `
        -PerRequestTimeoutSeconds $RequestTimeoutSeconds
    $mediaType = switch ([System.IO.Path]::GetExtension($fixture.absolute_path).ToLowerInvariant()) {
        '.pdf' { 'application/pdf' }
        '.docx' { 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' }
        '.txt' { 'text/plain' }
        default { throw "Unsupported benchmark fixture type: $($fixture.path)" }
    }
    $stream = [System.IO.File]::OpenRead($fixture.absolute_path)
    $request = $null
    $response = $null
    $cancellation = [System.Threading.CancellationTokenSource]::new(
        [TimeSpan]::FromSeconds($requestTimeout)
    )
    try {
        $fileContent = [System.Net.Http.StreamContent]::new($stream)
        $fileContent.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::new($mediaType)
        $multipart = [System.Net.Http.MultipartFormDataContent]::new()
        $multipart.Add($fileContent, 'file', [System.IO.Path]::GetFileName($fixture.absolute_path))
        $request = [System.Net.Http.HttpRequestMessage]::new(
            [System.Net.Http.HttpMethod]::Post,
            '/documents'
        )
        $request.Headers.TryAddWithoutValidation('X-CSRF-Token', $csrfToken) | Out-Null
        $request.Content = $multipart
        $response = $httpClient.SendAsync($request, $cancellation.Token).GetAwaiter().GetResult()
        $responseBody = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
        if (-not $response.IsSuccessStatusCode) {
            throw "Upload failed with HTTP $([int]$response.StatusCode): $responseBody"
        }
        $accepted = $responseBody | ConvertFrom-Json
    }
    finally {
        if ($response) { $response.Dispose() }
        if ($request) { $request.Dispose() }
        $cancellation.Dispose()
        $stream.Dispose()
    }
    if ($accepted.duplicate) {
        throw "Benchmark data is not clean: $($fixture.source_id) was already uploaded by demo-reviewer."
    }
    $observations += [pscustomobject]@{
        source_id = $fixture.source_id
        path = $fixture.path
        sha256 = $fixture.sha256
        document_id = [string]$accepted.document.id
        revision_id = [string]$accepted.revision_id
        accepted_at = (Get-Date).ToUniversalTime().ToString('o')
        ready_at = $null
        state = [string]$accepted.document.state
    }
    Write-Host "Accepted $($fixture.source_id) ($($observations.Count)/$($fixtureRows.Count))."
}
$uploadsCompletedAt = (Get-Date).ToUniversalTime()

while (@($observations | Where-Object { $_.state -ne 'ready' }).Count -gt 0) {
    if ($timer.Elapsed.TotalSeconds -gt $TimeoutSeconds) {
        throw "Indexing benchmark timed out after $TimeoutSeconds seconds."
    }
    foreach ($observation in @($observations | Where-Object { $_.state -ne 'ready' })) {
        $requestTimeout = Get-BenchmarkRequestTimeout `
            -Stopwatch $timer `
            -OverallTimeoutSeconds $TimeoutSeconds `
            -PerRequestTimeoutSeconds $RequestTimeoutSeconds
        $detail = Invoke-RestMethod `
            -Uri "$apiOrigin/documents/$($observation.document_id)" `
            -Method Get `
            -WebSession $session `
            -MaximumRedirection 0 `
            -TimeoutSec $requestTimeout
        $observation.state = [string]$detail.state
        if ($observation.state -eq 'ready' -and -not $observation.ready_at) {
            $observation.ready_at = (Get-Date).ToUniversalTime().ToString('o')
            Write-Host "Ready $($observation.source_id)."
        }
        elseif ($observation.state -eq 'failed') {
            throw "Indexing failed for $($observation.source_id)."
        }
    }
    if (@($observations | Where-Object { $_.state -ne 'ready' }).Count -gt 0) {
        $remainingMilliseconds = [Math]::Floor(
            ($TimeoutSeconds - $timer.Elapsed.TotalSeconds) * 1000
        )
        if ($remainingMilliseconds -lt 1) {
            throw "Indexing benchmark timed out after $TimeoutSeconds seconds."
        }
        Start-Sleep -Milliseconds ([Math]::Min(500, $remainingMilliseconds))
    }
}

$timer.Stop()
$completedAt = (Get-Date).ToUniversalTime()
$artifact = [ordered]@{
    schema_version = '1.0.0'
    measured_at = $completedAt.ToString('o')
    base_url = $apiOrigin
    fixture_manifest_sha256 = (Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant()
    started_at = $startedAt.ToString('o')
    uploads_completed_at = $uploadsCompletedAt.ToString('o')
    completed_at = $completedAt.ToString('o')
    duration_ms = [Math]::Round($timer.Elapsed.TotalMilliseconds, 2)
    fixture_count = $fixtureRows.Count
    ready_count = @($observations | Where-Object { $_.state -eq 'ready' }).Count
    duplicate_count = 0
    failure_count = 0
    documents = $observations
}
$temporaryOutput = Join-Path $outputDirectory (
    ".{0}.{1}.{2}.tmp" -f (Split-Path -Leaf $OutputPath), $PID, [guid]::NewGuid().ToString('N')
)
try {
    $artifact | ConvertTo-Json -Depth 8 |
        Set-Content -LiteralPath $temporaryOutput -Encoding utf8
    Move-Item -LiteralPath $temporaryOutput -Destination $OutputPath
}
finally {
    if (Test-Path -LiteralPath $temporaryOutput) {
        Remove-Item -LiteralPath $temporaryOutput -Force
    }
}

Write-Host "Indexed $($artifact.ready_count)/$($artifact.fixture_count) fixtures in $($artifact.duration_ms) ms."
Write-Host "Benchmark artifact: $OutputPath"
}
finally {
    $reviewerPassword = $null
    $loginBody = $null
    if ($csrfToken) {
        try {
            Invoke-RestMethod `
                -Uri "$apiOrigin/auth/logout" `
                -Method Post `
                -Headers @{ 'X-CSRF-Token' = $csrfToken } `
                -WebSession $session `
                -MaximumRedirection 0 `
                -TimeoutSec $RequestTimeoutSeconds | Out-Null
        }
        catch {
            Write-Warning 'The benchmark session did not log out cleanly; it will expire server-side.'
        }
    }
    if ($httpClient) {
        $httpClient.Dispose()
    }
}

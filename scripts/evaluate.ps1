param(
    [ValidateSet('fake', 'ollama')][string]$Provider = 'fake',
    [switch]$CaptureRawResponses
)

. (Join-Path $PSScriptRoot 'common.ps1')

function Invoke-EvaluationDocker {
    param([Parameter(Mandatory)][string[]]$DockerArguments)

    & docker @DockerArguments
    if ($LASTEXITCODE -ne 0) {
        throw "docker failed with exit code ${LASTEXITCODE}: docker $($DockerArguments -join ' ')"
    }
}

function Get-EvaluationDockerOutput {
    param([Parameter(Mandatory)][string[]]$DockerArguments)

    $output = @(& docker @DockerArguments)
    if ($LASTEXITCODE -ne 0) {
        throw "docker failed with exit code ${LASTEXITCODE}: docker $($DockerArguments -join ' ')"
    }
    return ($output -join "`n").Trim()
}

function Invoke-EvaluationCompose {
    param(
        [Parameter(Mandatory)][string]$ProjectName,
        [Parameter(Mandatory)][string[]]$ComposeArguments
    )

    Push-Location $script:ProjectRoot
    try {
        Invoke-EvaluationDocker -DockerArguments (
            @('compose', '-p', $ProjectName) + $ComposeArguments
        )
    }
    finally {
        Pop-Location
    }
}

function Get-DefaultComposeOutput {
    param([Parameter(Mandatory)][string[]]$ComposeArguments)

    Push-Location $script:ProjectRoot
    try {
        return Get-EvaluationDockerOutput -DockerArguments (@('compose') + $ComposeArguments)
    }
    finally {
        Pop-Location
    }
}

function Get-ContainerIdentity {
    param([Parameter(Mandatory)][string]$ContainerReference)

    $output = @(& docker container inspect --format '{{.Id}}' $ContainerReference 2>$null)
    if ($LASTEXITCODE -ne 0) {
        return $null
    }
    $identity = ($output -join '').Trim()
    if ($identity -notmatch '^[0-9a-f]{64}$') {
        throw "Docker returned an invalid container identity for '$ContainerReference'."
    }
    return $identity
}

function Get-ContainerInspection {
    param([Parameter(Mandatory)][string]$ContainerReference)

    $payload = Get-EvaluationDockerOutput -DockerArguments @(
        'container', 'inspect', $ContainerReference
    )
    $items = @($payload | ConvertFrom-Json)
    if ($items.Count -ne 1) {
        throw "Expected exactly one inspected container for '$ContainerReference'."
    }
    return $items[0]
}

function Get-NetworkInspection {
    param([Parameter(Mandatory)][string]$NetworkReference)

    $payload = Get-EvaluationDockerOutput -DockerArguments @('network', 'inspect', $NetworkReference)
    $items = @($payload | ConvertFrom-Json)
    if ($items.Count -ne 1) {
        throw "Expected exactly one inspected network for '$NetworkReference'."
    }
    return $items[0]
}

function Get-VolumeInspection {
    param([Parameter(Mandatory)][string]$VolumeReference)

    $payload = Get-EvaluationDockerOutput -DockerArguments @('volume', 'inspect', $VolumeReference)
    $items = @($payload | ConvertFrom-Json)
    if ($items.Count -ne 1) {
        throw "Expected exactly one inspected volume for '$VolumeReference'."
    }
    return $items[0]
}

function Test-DockerObjectExists {
    param(
        [Parameter(Mandatory)][ValidateSet('container', 'network', 'volume')][string]$Kind,
        [Parameter(Mandatory)][string]$Reference
    )

    & docker $Kind inspect $Reference *> $null
    return $LASTEXITCODE -eq 0
}

function Assert-EvaluationProjectUnused {
    param([Parameter(Mandatory)][string]$ProjectName)

    $queries = @(
        [pscustomobject]@{
            Kind = 'container'
            Arguments = @(
                'container', 'ls', '--all', '--quiet', '--filter',
                "label=com.docker.compose.project=$ProjectName"
            )
        },
        [pscustomobject]@{
            Kind = 'network'
            Arguments = @(
                'network', 'ls', '--quiet', '--filter',
                "label=com.docker.compose.project=$ProjectName"
            )
        },
        [pscustomobject]@{
            Kind = 'volume'
            Arguments = @(
                'volume', 'ls', '--quiet', '--filter',
                "label=com.docker.compose.project=$ProjectName"
            )
        }
    )
    foreach ($query in $queries) {
        if (-not [string]::IsNullOrWhiteSpace(
            (Get-EvaluationDockerOutput -DockerArguments $query.Arguments)
        )) {
            throw "Generated evaluation project '$ProjectName' already owns Docker $($query.Kind) resources."
        }
    }
}

function Add-CleanupFailure {
    param(
        [Parameter(Mandatory)][AllowEmptyCollection()]
        [System.Collections.Generic.List[string]]$Failures,
        [Parameter(Mandatory)][string]$Description,
        [Parameter(Mandatory)][scriptblock]$Action
    )

    try {
        & $Action
    }
    catch {
        $Failures.Add("${Description}: $($_.Exception.Message)")
    }
}

function Assert-EvaluationApiContainer {
    param(
        [Parameter(Mandatory)]$Inspection,
        [Parameter(Mandatory)][string]$ProjectName,
        [Parameter(Mandatory)][string]$ArtifactsVolume,
        [Parameter(Mandatory)][string]$ExpectedResultsPath
    )

    if ($Inspection.Config.Labels.'com.docker.compose.project' -ne $ProjectName) {
        throw 'Evaluation API container has the wrong Compose project label.'
    }
    if ($Inspection.Config.Labels.'com.docker.compose.service' -ne 'api') {
        throw 'Evaluation API container has the wrong Compose service label.'
    }

    $mounts = @($Inspection.Mounts)
    $resultsMount = @($mounts | Where-Object Destination -eq '/workspace/evals/results')
    $artifactsMount = @($mounts | Where-Object Destination -eq '/workspace/artifacts')
    $uploadsMount = @($mounts | Where-Object Destination -eq '/var/lib/localguard/uploads')
    if ($resultsMount.Count -ne 1 -or $resultsMount[0].Type -ne 'bind' -or -not $resultsMount[0].RW) {
        throw 'Evaluation results are not mounted as one writable bind.'
    }
    if ($artifactsMount.Count -ne 1 -or $artifactsMount[0].Type -ne 'volume' -or $artifactsMount[0].Name -ne $ArtifactsVolume) {
        throw 'Evaluation artifacts did not resolve to the isolated volume.'
    }
    if ($uploadsMount.Count -ne 1 -or $uploadsMount[0].Type -ne 'volume') {
        throw 'Evaluation uploads did not resolve to an isolated volume.'
    }
    $unexpectedBinds = @(
        $mounts | Where-Object { $_.Type -eq 'bind' -and $_.Destination -ne '/workspace/evals/results' }
    )
    if ($unexpectedBinds.Count -ne 0) {
        throw 'Evaluation API container exposes an unexpected host bind mount.'
    }

    $normalizedSource = ([string]$resultsMount[0].Source).Replace('\', '/').ToLowerInvariant()
    $normalizedExpected = $ExpectedResultsPath.Replace('\', '/').ToLowerInvariant()
    $dockerDesktopExpected = $normalizedExpected
    if ($normalizedExpected -match '^(?<drive>[a-z]):/(?<tail>.*)$') {
        $dockerDesktopExpected = "/run/desktop/mnt/host/$($Matches.drive)/$($Matches.tail)"
    }
    if ($normalizedSource -ne $normalizedExpected -and $normalizedSource -ne $dockerDesktopExpected) {
        throw 'Evaluation results bind does not resolve to the exact repository results directory.'
    }
}

Assert-DockerEngine
$environment = if ($Provider -eq 'fake') { 'test' } else { 'development' }
$runtimeProvider = if ($Provider -eq 'fake') { 'deterministic' } else { 'ollama' }
$scopeSuffix = [Guid]::NewGuid().ToString('N').Substring(0, 12)
$evaluationProject = "localguard-eval-$scopeSuffix"
$evaluationContainerName = "$evaluationProject-api"
$evaluationArtifactsVolume = "$evaluationProject-artifacts"
$modelBridgeName = "$evaluationProject-model"
if ($evaluationProject -notmatch '^localguard-eval-[0-9a-f]{12}$') {
    throw 'Generated evaluation project name is outside the bounded naming contract.'
}

$expectedResultsPath = Resolve-LocalGuardEvaluationResultsPath -ProjectRoot $script:ProjectRoot
$primaryFailure = $null
$cleanupFailures = [System.Collections.Generic.List[string]]::new()
$evaluationContainerId = $null
$mainOllamaContainerId = $null
$mainOllamaOriginalNetworks = @()
$mainOllamaNetworksCaptured = $false
$modelBridgeCreated = $false
$mainOllamaAttached = $false
$artifactsVolumeCreated = $false

try {
    Invoke-LocalGuardCompose -Arguments @('build', 'api')
    Initialize-LocalGuardEvaluationResults

    if (Test-DockerObjectExists -Kind 'container' -Reference $evaluationContainerName) {
        throw 'Generated evaluation container name already exists.'
    }
    if (Test-DockerObjectExists -Kind 'network' -Reference $modelBridgeName) {
        throw 'Generated evaluation model network already exists.'
    }
    if (Test-DockerObjectExists -Kind 'volume' -Reference $evaluationArtifactsVolume) {
        throw 'Generated evaluation artifacts volume already exists.'
    }
    Assert-EvaluationProjectUnused -ProjectName $evaluationProject

    $createdVolume = Get-EvaluationDockerOutput -DockerArguments @(
        'volume', 'create', '--label', "com.localguard.evaluation-project=$evaluationProject",
        $evaluationArtifactsVolume
    )
    $artifactsVolumeCreated = $true
    if ($createdVolume -ne $evaluationArtifactsVolume) {
        throw 'Docker created an unexpected evaluation artifacts volume.'
    }

    Invoke-EvaluationCompose -ProjectName $evaluationProject -ComposeArguments @(
        'up', '-d', '--wait', 'db', 'redis'
    )
    $artifactsMount = "${evaluationArtifactsVolume}:/workspace/artifacts"
    Invoke-EvaluationCompose -ProjectName $evaluationProject -ComposeArguments @(
        'run', '--rm', '--no-deps', '-v', $artifactsMount,
        'api', 'alembic', 'upgrade', 'head'
    )
    Invoke-EvaluationCompose -ProjectName $evaluationProject -ComposeArguments @(
        'run', '--rm', '--no-deps', '-v', $artifactsMount,
        'api', 'python', '-m', 'localguard_api.cli', 'setup-checkpoints'
    )

    Invoke-EvaluationCompose -ProjectName $evaluationProject -ComposeArguments @(
        'run', '-d', '--no-deps', '--name', $evaluationContainerName,
        '-v', $artifactsMount, '--entrypoint', 'python', 'api',
        '-c', 'import time; time.sleep(86400)'
    )
    $evaluationContainerId = Get-ContainerIdentity -ContainerReference $evaluationContainerName
    if ($null -eq $evaluationContainerId) {
        throw 'Evaluation API container was not created.'
    }
    $evaluationInspection = Get-ContainerInspection -ContainerReference $evaluationContainerId
    Assert-EvaluationApiContainer -Inspection $evaluationInspection -ProjectName $evaluationProject `
        -ArtifactsVolume $evaluationArtifactsVolume -ExpectedResultsPath $expectedResultsPath

    if ($Provider -eq 'ollama') {
        Invoke-LocalGuardCompose -Arguments @('--profile', 'app', 'up', '-d', '--wait', 'ollama')
        $ollamaIds = @(
            (Get-DefaultComposeOutput -ComposeArguments @('ps', '-q', 'ollama')) -split "`n" |
                Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
        )
        if ($ollamaIds.Count -ne 1) {
            throw 'Expected exactly one running main Ollama container.'
        }
        $mainOllamaContainerId = Get-ContainerIdentity -ContainerReference $ollamaIds[0].Trim()
        if ($null -eq $mainOllamaContainerId) {
            throw 'Main Ollama container identity could not be resolved.'
        }
        $ollamaInspection = Get-ContainerInspection -ContainerReference $mainOllamaContainerId
        if ($ollamaInspection.Config.Labels.'com.docker.compose.project' -ne 'localguard' -or
            $ollamaInspection.Config.Labels.'com.docker.compose.service' -ne 'ollama') {
            throw 'Resolved Ollama container is not the pinned main LocalGuard service.'
        }
        if (-not $ollamaInspection.State.Running -or $ollamaInspection.State.Health.Status -ne 'healthy') {
            throw 'Main LocalGuard Ollama container is not healthy.'
        }
        $mainOllamaOriginalNetworks = @(
            $ollamaInspection.NetworkSettings.Networks.PSObject.Properties.Name | Sort-Object
        )
        $mainOllamaNetworksCaptured = $true
        $composeConfig = Get-DefaultComposeOutput -ComposeArguments @(
            '--profile', 'app', 'config', '--format', 'json'
        ) | ConvertFrom-Json
        $expectedOllamaImage = [string]$composeConfig.services.ollama.image
        if ([string]$ollamaInspection.Config.Image -ne $expectedOllamaImage) {
            throw 'Main Ollama container is not configured with the Compose-pinned image.'
        }
        $expectedOllamaImageId = (
            Get-EvaluationDockerOutput -DockerArguments @(
                'image', 'inspect', '--format', '{{.Id}}', $expectedOllamaImage
            )
        ).Replace('sha256:', '')
        if ([string]$ollamaInspection.Image -ne "sha256:$expectedOllamaImageId") {
            throw 'Main Ollama container rootfs does not match the pinned image identity.'
        }
        $modelNetworkId = Get-EvaluationDockerOutput -DockerArguments @(
            'network', 'create', '--driver', 'bridge', '--internal',
            '--label', "com.localguard.evaluation-project=$evaluationProject", $modelBridgeName
        )
        $modelBridgeCreated = $true
        if ($modelNetworkId -notmatch '^[0-9a-f]{64}$') {
            throw 'Docker returned an invalid evaluation model network identity.'
        }
        $bridgeInspection = Get-NetworkInspection -NetworkReference $modelBridgeName
        if (-not $bridgeInspection.Internal -or
            $bridgeInspection.Labels.'com.localguard.evaluation-project' -ne $evaluationProject) {
            throw 'Evaluation model bridge does not satisfy the isolated network contract.'
        }

        Invoke-EvaluationDocker -DockerArguments @(
            'network', 'connect', $modelBridgeName, $evaluationContainerId
        )
        Invoke-EvaluationDocker -DockerArguments @(
            'network', 'connect', '--alias', 'ollama', $modelBridgeName, $mainOllamaContainerId
        )
        $mainOllamaAttached = $true
        $bridgeInspection = Get-NetworkInspection -NetworkReference $modelBridgeName
        $attachedIds = @($bridgeInspection.Containers.PSObject.Properties.Name | Sort-Object)
        $expectedAttachedIds = @($evaluationContainerId, $mainOllamaContainerId) | Sort-Object
        if (($attachedIds -join ',') -ne ($expectedAttachedIds -join ',')) {
            throw 'Evaluation model bridge has an unexpected container attachment.'
        }
        $ollamaInspection = Get-ContainerInspection -ContainerReference $mainOllamaContainerId
        $modelAliases = @(
            $ollamaInspection.NetworkSettings.Networks.$modelBridgeName.Aliases
        )
        if ('ollama' -notin $modelAliases) {
            throw 'Main Ollama container does not have the required evaluation-only DNS alias.'
        }
    }

    $captureRawEnvironment = if ($CaptureRawResponses) {
        'LOCALGUARD_EVAL_CAPTURE_RAW_RESPONSES=1'
    }
    else {
        'LOCALGUARD_EVAL_CAPTURE_RAW_RESPONSES=0'
    }
    $execArguments = @(
        'exec',
        '-e', "APP_ENV=$environment",
        '-e', "AI_PROVIDER=$runtimeProvider",
        '-e', "EMBEDDING_PROVIDER=$runtimeProvider",
        '-e', "ALLOW_TEST_PROVIDERS=$($Provider -eq 'fake')",
        '-e', $captureRawEnvironment,
        $evaluationContainerId,
        'python', '-m', 'localguard_api.evaluation.cli', 'run', '--provider', $Provider
    )
    Invoke-EvaluationDocker -DockerArguments $execArguments
}
catch {
    $primaryFailure = $_
}
finally {
    if ($mainOllamaAttached -and $null -ne $mainOllamaContainerId) {
        Add-CleanupFailure -Failures $cleanupFailures -Description 'disconnect main Ollama from evaluation bridge' -Action {
            Invoke-EvaluationDocker -DockerArguments @(
                'network', 'disconnect', '--force', $modelBridgeName, $mainOllamaContainerId
            )
        }
    }
    if ($null -ne $evaluationContainerId) {
        Add-CleanupFailure -Failures $cleanupFailures -Description 'remove evaluation API container' -Action {
            $currentIdentity = Get-ContainerIdentity -ContainerReference $evaluationContainerName
            if ($null -ne $currentIdentity) {
                if ($currentIdentity -ne $evaluationContainerId) {
                    throw 'Evaluation container name resolves to a different identity.'
                }
                Invoke-EvaluationDocker -DockerArguments @('container', 'rm', '--force', $evaluationContainerId)
            }
        }
    }
    Add-CleanupFailure -Failures $cleanupFailures -Description 'remove isolated Compose project' -Action {
        Invoke-EvaluationCompose -ProjectName $evaluationProject -ComposeArguments @(
            'down', '--volumes', '--remove-orphans'
        )
    }
    if ($modelBridgeCreated) {
        Add-CleanupFailure -Failures $cleanupFailures -Description 'remove evaluation model bridge' -Action {
            if (Test-DockerObjectExists -Kind 'network' -Reference $modelBridgeName) {
                $inspection = Get-NetworkInspection -NetworkReference $modelBridgeName
                if ($inspection.Labels.'com.localguard.evaluation-project' -ne $evaluationProject) {
                    throw 'Refusing to remove an evaluation bridge with the wrong ownership label.'
                }
                Invoke-EvaluationDocker -DockerArguments @('network', 'rm', $modelBridgeName)
            }
        }
    }
    if ($artifactsVolumeCreated) {
        Add-CleanupFailure -Failures $cleanupFailures -Description 'remove isolated artifacts volume' -Action {
            if (Test-DockerObjectExists -Kind 'volume' -Reference $evaluationArtifactsVolume) {
                $inspection = Get-VolumeInspection -VolumeReference $evaluationArtifactsVolume
                if ($inspection.Labels.'com.localguard.evaluation-project' -ne $evaluationProject) {
                    throw 'Refusing to remove an evaluation volume with the wrong ownership label.'
                }
                Invoke-EvaluationDocker -DockerArguments @('volume', 'rm', $evaluationArtifactsVolume)
            }
        }
    }
    Add-CleanupFailure -Failures $cleanupFailures -Description 'verify isolated Docker scope removal' -Action {
        Assert-EvaluationProjectUnused -ProjectName $evaluationProject
        foreach ($ownedObject in @(
            [pscustomobject]@{ Kind = 'network'; Reference = $modelBridgeName },
            [pscustomobject]@{ Kind = 'volume'; Reference = $evaluationArtifactsVolume },
            [pscustomobject]@{ Kind = 'container'; Reference = $evaluationContainerName }
        )) {
            if (Test-DockerObjectExists -Kind $ownedObject.Kind -Reference $ownedObject.Reference) {
                throw "Evaluation-owned Docker object remains after cleanup: $($ownedObject.Reference)"
            }
        }
    }
    if ($null -ne $mainOllamaContainerId -and $mainOllamaNetworksCaptured) {
        Add-CleanupFailure -Failures $cleanupFailures -Description 'verify main Ollama network restoration' -Action {
            $inspection = Get-ContainerInspection -ContainerReference $mainOllamaContainerId
            $currentNetworks = @(
                $inspection.NetworkSettings.Networks.PSObject.Properties.Name | Sort-Object
            )
            if (($currentNetworks -join ',') -ne ($mainOllamaOriginalNetworks -join ',')) {
                throw "Main Ollama networks were not restored exactly after evaluation. Expected '$($mainOllamaOriginalNetworks -join ',')'; got '$($currentNetworks -join ',')'."
            }
        }
    }
}

if ($null -ne $primaryFailure) {
    if ($cleanupFailures.Count -ne 0) {
        Write-Warning "Evaluation cleanup also failed: $($cleanupFailures -join '; ')"
    }
    throw $primaryFailure
}
if ($cleanupFailures.Count -ne 0) {
    throw "Evaluation completed, but isolated-scope cleanup failed: $($cleanupFailures -join '; ')"
}

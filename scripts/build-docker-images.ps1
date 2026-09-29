# Construye las imagenes Docker principales del proyecto en el orden requerido.
param(
    [switch]$NoCache,
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Test-CommandExists {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CommandName
    )

    return $null -ne (Get-Command $CommandName -ErrorAction SilentlyContinue)
}

function Invoke-DockerBuild {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Image,
        [Parameter(Mandatory = $true)]
        [string]$Context
    )

    $args = @("build", "-t", $Image)
    if ($NoCache) {
        $args += "--no-cache"
    }
    $args += $Context

    Write-Host ""
    Write-Host "Building $Image from $Context"

    if ($DryRun) {
        Write-Host "docker $($args -join ' ')"
        return
    }

    & docker @args
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

if (-not $DryRun -and -not (Test-CommandExists "docker")) {
    throw "docker is not available in PATH. Start Docker Desktop or install Docker first."
}

$images = @(
    @{ Image = "soca-heavy:latest"; Context = "containers\soca_container" },
    @{ Image = "rsfc-heavy:latest"; Context = "containers\rsfc_container" },
    @{ Image = "resqui-heavy:latest"; Context = "containers\resqui_container" },
    @{ Image = "rsmetacheck-bot:latest"; Context = "integrations\rsmetacheck-bot-0.6.0" },
    @{ Image = "rsmetacheck-bot-conf:latest"; Context = "containers\rsmetacheck-bot_container" }
)

foreach ($item in $images) {
    Invoke-DockerBuild -Image $item["Image"] -Context $item["Context"]
}

Write-Host ""
Write-Host "Docker image build sequence completed."
Write-Host "DashVERSE backend/frontend images are built separately by 'just deploy' from integrations/DashVERSE."

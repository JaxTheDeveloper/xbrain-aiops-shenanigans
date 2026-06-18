# scale_replicas.ps1 - scale a Compose service to N replicas
# Usage: .\scale_replicas.ps1 -Service <name> [-Replicas <N>] [-DryRun]
# Exit: 0=success, 1=failure

param(
    [Parameter(Mandatory=$true)][string]$Service,
    [int]$Replicas = 2,
    [switch]$DryRun
)

$ComposeFile = Join-Path $PSScriptRoot "..\..\configs\docker-compose.yml"

if ($DryRun) {
    Write-Host "[DRY-RUN] would execute: docker compose scale ${Service}=${Replicas}"
    exit 0
}

Write-Host "[scale_replicas] Scaling $Service to $Replicas replicas..."
docker compose -f $ComposeFile up -d --scale "${Service}=${Replicas}" --no-recreate

if ($LASTEXITCODE -eq 0) {
    Write-Host "[scale_replicas] Done - $Service scaled to $Replicas."
    exit 0
} else {
    Write-Host "[scale_replicas] ERROR: scale command failed."
    exit 1
}

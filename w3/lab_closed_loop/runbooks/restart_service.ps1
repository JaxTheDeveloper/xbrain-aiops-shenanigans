# restart_service.ps1 - restart a Docker Compose service container
# Usage: .\restart_service.ps1 -Service <name> [-DryRun]
# Exit: 0=success, 1=failure

param(
    [Parameter(Mandatory=$true)][string]$Service,
    [switch]$DryRun
)

$Container = "ronki-$Service"

if ($DryRun) {
    Write-Host "[DRY-RUN] would execute: docker restart $Container"
    exit 0
}

Write-Host "[restart_service] Restarting $Container..."

$null = docker inspect $Container 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[restart_service] Container not found - attempting docker start..."
    docker start $Container
} else {
    docker restart $Container
}

Start-Sleep -Seconds 5

$status = docker inspect --format "{{.State.Status}}" $Container 2>$null
if ($status -eq "running") {
    Write-Host "[restart_service] $Container is running."
    exit 0
} else {
    Write-Host ("[restart_service] ERROR: $Container status=" + $status + " after restart.")
    exit 1
}

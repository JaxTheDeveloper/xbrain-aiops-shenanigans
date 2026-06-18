# clear_cache.ps1 - flush service cache via restart (SIGHUP not available on Windows Docker)
# Usage: .\clear_cache.ps1 -Service <name> [-DryRun]
# Exit: 0=success, 1=failure

param(
    [Parameter(Mandatory=$true)][string]$Service,
    [switch]$DryRun
)

$Container = "ronki-$Service"

if ($DryRun) {
    Write-Host "[DRY-RUN] would execute: docker restart $Container (cache flush)"
    exit 0
}

$null = docker inspect $Container 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[clear_cache] ERROR: container $Container not found."
    exit 1
}

Write-Host "[clear_cache] Restarting $Container to flush cache..."
docker restart $Container
Write-Host "[clear_cache] Cache flush complete on $Container."
exit 0

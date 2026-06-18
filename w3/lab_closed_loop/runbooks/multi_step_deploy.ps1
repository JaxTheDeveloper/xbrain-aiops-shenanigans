# multi_step_deploy.ps1 - 3-step transactional deploy
# Usage: .\multi_step_deploy.ps1 -Service <name> -Step <A|B|C|RB|RA> [-DryRun]
# Exit: 0=success, 1=failure

param(
    [Parameter(Mandatory=$true)][string]$Service,
    [Parameter(Mandatory=$true)][ValidateSet("A","B","C","RA","RB")][string]$Step,
    [switch]$DryRun
)

$Container = "ronki-$Service"

if ($DryRun) {
    Write-Host "[DRY-RUN] would execute: multi_step_deploy step=$Step on $Container"
    exit 0
}

switch ($Step) {
    "A" {
        Write-Host "[multi_step_deploy] step-A: draining $Container..."
        docker stop $Container 2>$null
        Write-Host "[multi_step_deploy] step-A done."
    }
    "B" {
        Write-Host "[multi_step_deploy] step-B: applying config to $Container..."
        docker restart $Container 2>$null
        if ($LASTEXITCODE -ne 0) { docker start $Container }
        Start-Sleep -Seconds 3
        $status = docker inspect --format "{{.State.Status}}" $Container 2>$null
        if ($status -ne "running") {
            Write-Host ("[multi_step_deploy] ERROR: step-B failed - status=" + $status)
            exit 1
        }
        Write-Host "[multi_step_deploy] step-B done."
    }
    "C" {
        Write-Host "[multi_step_deploy] step-C: re-enabling traffic for $Container..."
        # Check if container exists and is startable
        $null = docker inspect $Container 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Host ("[multi_step_deploy] ERROR: step-C failed - container $Container not found")
            exit 1
        }
        docker start $Container 2>$null
        Start-Sleep -Seconds 2
        $status = docker inspect --format "{{.State.Status}}" $Container 2>$null
        if ($status -ne "running") {
            Write-Host ("[multi_step_deploy] ERROR: step-C failed - status=" + $status)
            exit 1
        }
        Write-Host "[multi_step_deploy] step-C done."
    }
    "RB" {
        Write-Host "[multi_step_deploy] rollback-B: reverting config on $Container..."
        docker restart $Container 2>$null
        if ($LASTEXITCODE -ne 0) { docker start $Container }
        Start-Sleep -Seconds 3
        Write-Host "[multi_step_deploy] rollback-B done."
    }
    "RA" {
        Write-Host "[multi_step_deploy] rollback-A: restoring traffic to $Container..."
        docker start $Container 2>$null
        Start-Sleep -Seconds 2
        Write-Host "[multi_step_deploy] rollback-A done."
    }
}

exit 0

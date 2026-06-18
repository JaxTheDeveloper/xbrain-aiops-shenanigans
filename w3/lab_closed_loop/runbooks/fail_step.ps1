# fail_step.ps1 - always exits 1, used to force step failure in scenario 4 testing
# Usage: .\fail_step.ps1 -Service <name> [-DryRun]

param(
    [Parameter(Mandatory=$true)][string]$Service,
    [switch]$DryRun
)

if ($DryRun) {
    Write-Host "[DRY-RUN] would execute: fail_step (forced failure for testing)"
    exit 0
}

Write-Host "[fail_step] Simulating step-C failure on $Service"
exit 1

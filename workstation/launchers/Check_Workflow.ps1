# Verify this workstation; optional fresh room and broader feature regressions.
param(
    [switch]$Legacy,
    [switch]$RunComparison,
    [switch]$FeatureChecks,
    [switch]$ParameterChecks,
    [string]$Blender = 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe'
)
$ErrorActionPreference = 'Stop'
if ($Legacy -or $FeatureChecks -or $ParameterChecks) { throw 'RT 2.1 launchers are retired. Use the shared RT 2.2 workflow or restore the isolated recovery package; see RT21_RETIREMENT.txt.' }


    $sharedArgs = @('--workspace',$PSScriptRoot,'--blender',$Blender)
    if ($RunComparison) { $sharedArgs += '--run-comparison' }
    & (Join-Path $PSScriptRoot 'work/runtime/Scripts/python.exe') -B (Join-Path $PSScriptRoot 'work/github-update/differt-bridge/scripts/check_shared_workflow.py') @sharedArgs
    if ($LASTEXITCODE -ne 0) { throw 'Shared native workflow check failed; see its new work/rt22-check-* receipt.' }
    return

# Verify this workstation; optional fresh room and broader feature regressions.
param(
    [switch]$Legacy,
    [switch]$RunComparison,
    [switch]$FeatureChecks,
    [switch]$ParameterChecks,
    [string]$Blender = 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe'
)
$ErrorActionPreference = 'Stop'
if (-not $Legacy) {
    if ($FeatureChecks -or $ParameterChecks) { throw 'These historical alignment checks require -Legacy. Shared native checks: Check_Workflow.ps1 -RunComparison.' }
    $sharedArgs = @('--workspace',$PSScriptRoot,'--blender',$Blender)
    if ($RunComparison) { $sharedArgs += '--run-comparison' }
    & (Join-Path $PSScriptRoot 'work/runtime/Scripts/python.exe') -B (Join-Path $PSScriptRoot 'work/github-update/differt-bridge/scripts/check_shared_workflow.py') @sharedArgs
    if ($LASTEXITCODE -ne 0) { throw 'Shared native workflow check failed; see its new work/rt22-check-* receipt.' }
    return
}
$projectRoot = [IO.Path]::GetFullPath($PSScriptRoot)
$workRoot = Join-Path $projectRoot 'work'
# Keep the generated scene-export path below the bridges' Windows path budget.
$scratch = Join-Path $workRoot ('hc-' + [guid]::NewGuid().ToString('N').Substring(0, 12))
$python = Join-Path $workRoot 'runtime/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw "DiffeRT runtime missing: $python" }
New-Item -ItemType Directory -Path $scratch | Out-Null
$resultCode = 1
try {
    $extraArgs = @()
    if ($RunComparison) { $extraArgs += '--run-comparison' }
    if ($FeatureChecks) { $extraArgs += '--feature-checks' }
    if ($ParameterChecks) { $extraArgs += '--parameter-checks' }
    & $python -B (Join-Path $projectRoot 'outputs/differt-bridge/scripts/check_workspace.py') --workspace $projectRoot --scratch $scratch --blender $Blender @extraArgs
    $resultCode = $LASTEXITCODE
} finally {
    # This invocation owns only its unique scratch folder; never delete a link target.
    $resolved = [IO.Path]::GetFullPath($scratch)
    $boundary = [IO.Path]::GetFullPath($workRoot).TrimEnd('\') + '\'
    if (-not $resolved.StartsWith($boundary, [StringComparison]::OrdinalIgnoreCase)) { throw 'Scratch is outside the project work folder' }
    foreach ($ancestor in @($projectRoot, $workRoot, $resolved)) {
        if ([IO.File]::GetAttributes($ancestor) -band [IO.FileAttributes]::ReparsePoint) { throw "Refusing linked scratch path: $ancestor" }
    }
    $linked = Get-ChildItem -LiteralPath $resolved -Force -Recurse | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }
    if ($linked) { throw 'Scratch contains a reparse point; retained for inspection' }
    Remove-Item -LiteralPath $resolved -Recurse -Force
}
if ($resultCode -ne 0) { throw 'Workflow check failed; see outputs/differt-bridge/validation/workflow_health.json' }

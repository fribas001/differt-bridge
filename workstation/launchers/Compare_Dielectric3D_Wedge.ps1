param(
    [string]$Manifest,
    [switch]$Legacy,
    [string]$Output,
    [string]$CheckpointFolder,
    [string]$CoarseCheckpointFolder,
    [ValidateSet('standard','converged')][string]$Accuracy = 'converged',
    [ValidateSet(16,24,32,48)][int]$Panels = 32
)
$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
if (-not $Manifest) { $Manifest = Join-Path $taskRoot 'work/d3shadow/concrete_cases.json' }
if (-not $Output) { $Output = Join-Path $taskRoot ("work/dielectric3d_comparison/" + $(if ($Legacy) { $Accuracy } else { "rt22-$Accuracy" })) }
$runtimeArgs = @()
if (-not $Legacy) {
    if (Test-Path -LiteralPath $Output) { throw "Choose a fresh output directory: $Output" }
    $rays = Join-Path $Output 'rays'
    & (Join-Path $taskRoot 'Run_Reciprocal_Rays.ps1') -Manifest $Manifest -Output $rays
    $runtimeArgs = @('--reuse-rays',$rays)
}
$taskArgs = @('-u','-B',(Join-Path $taskRoot 'work/github-update/differt-bridge/scripts/compare_dielectric3d.py'),$taskRoot,'--manifest',$Manifest,'--output',$Output,'--panels',"$Panels",'--accuracy',$Accuracy)
$taskArgs += $runtimeArgs
if ($CheckpointFolder) { $taskArgs += @('--checkpoint-folder',$CheckpointFolder) }
if ($CoarseCheckpointFolder) { $taskArgs += @('--coarse-checkpoint-folder',$CoarseCheckpointFolder) }
$previousThreads = $env:OPENBLAS_NUM_THREADS
try {
    $env:OPENBLAS_NUM_THREADS = '1'
    & (Join-Path $taskRoot 'work/runtime/Scripts/python.exe') @taskArgs
    if ($LASTEXITCODE -ne 0) { throw 'Dielectric 3D comparison failed; see the explicit geometry or solver diagnostic.' }
} finally { $env:OPENBLAS_NUM_THREADS = $previousThreads }

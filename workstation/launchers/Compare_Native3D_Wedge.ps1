param([string]$Manifest, [string]$Output, [switch]$Legacy)
$ErrorActionPreference = 'Stop'
if ($Legacy) { throw 'RT 2.1 launchers are retired. Use the shared RT 2.2 workflow or restore the isolated recovery package; see RT21_RETIREMENT.txt.' }
$taskRoot = $PSScriptRoot
if (-not $Manifest) { $Manifest = Join-Path $taskRoot 'work/native3d/workflow_cases.json' }
if (-not $Output) { $Output = Join-Path $taskRoot 'work/native3d-comparison-rt22' }
$runtimeArgs = @()
    if (Test-Path -LiteralPath $Output) { throw "Choose a fresh output directory: $Output" }
    $rays = Join-Path $Output 'rays'
    & (Join-Path $taskRoot 'Run_Reciprocal_Rays.ps1') -Manifest $Manifest -Output $rays
    $runtimeArgs = @('--reuse-rays',$rays)
$taskPreviousThreads = $env:OPENBLAS_NUM_THREADS
try {
    $env:OPENBLAS_NUM_THREADS = '1'
    & (Join-Path $taskRoot 'work/runtime/Scripts/python.exe') -B (Join-Path $taskRoot 'work/github-update/differt-bridge/scripts/compare_native3d.py') $taskRoot --manifest $Manifest --output $Output @runtimeArgs
    if ($LASTEXITCODE -ne 0) { throw 'Native 3D comparison failed; see diagnostics' }
} finally { $env:OPENBLAS_NUM_THREADS = $taskPreviousThreads }
Write-Output "Actual engine CIR exports and separate 3D PEC correction: $Output"

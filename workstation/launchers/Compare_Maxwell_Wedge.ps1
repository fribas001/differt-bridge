param([string]$Manifest, [string]$Output, [switch]$Legacy)
$ErrorActionPreference = 'Stop'
if ($Legacy) { throw 'RT 2.1 launchers are retired. Use the shared RT 2.2 workflow or restore the isolated recovery package; see RT21_RETIREMENT.txt.' }
$taskRoot = $PSScriptRoot
if (-not $Manifest) { $Manifest = Join-Path $taskRoot 'work/maxwell-refinement/cases.json' }
if (-not $Output) { $Output = Join-Path $taskRoot 'work/canonical-maxwell-comparison-rt22' }
$runtimeArgs = @()
    if (Test-Path -LiteralPath $Output) { throw "Choose a fresh output directory: $Output" }
    $rays = Join-Path $Output 'rays'
    & (Join-Path $taskRoot 'Run_Reciprocal_Rays.ps1') -Manifest $Manifest -Output $rays
    $runtimeArgs = @('--reuse-rays',$rays)
$taskPython = Join-Path $taskRoot 'work/runtime/Scripts/python.exe'
$taskScript = Join-Path $taskRoot 'work/github-update/differt-bridge/scripts/compare_canonical_refinement.py'
$taskPreviousThreads = $env:OPENBLAS_NUM_THREADS
try {
    $env:OPENBLAS_NUM_THREADS = '1'
    & $taskPython -B $taskScript $taskRoot --manifest $Manifest --output $Output @runtimeArgs
    if ($LASTEXITCODE -ne 0) { throw 'Canonical comparison failed; see diagnostic output' }
} finally { $env:OPENBLAS_NUM_THREADS = $taskPreviousThreads }
Write-Output "Native ray exports and separate 2D full-wave fields: $Output"

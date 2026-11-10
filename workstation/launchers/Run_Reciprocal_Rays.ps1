# Fresh paired ray exports for unchanged Maxwell companion programs.
param([Parameter(Mandatory=$true)][string]$Manifest,
      [Parameter(Mandatory=$true)][string]$Output)
$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath $Output) { throw "Choose a fresh output directory: $Output" }
$python = Join-Path $PSScriptRoot 'work/runtime/Scripts/python.exe'
$shared = Join-Path $env:USERPROFILE 'Documents/Codex/shared-envs/sionna-rt-2.2-py312/Scripts/python.exe'
& $python -B (Join-Path $PSScriptRoot 'work/github-update/differt-bridge/scripts/run_dielectric.py') --differt-python $python --sionna-python $shared --manifest $Manifest --output $Output --profiles sionna-reciprocal,differt-reciprocal --precision float32
if ($LASTEXITCODE -ne 0) { throw 'Paired reciprocal exports failed; see receipt.json in the new output.' }

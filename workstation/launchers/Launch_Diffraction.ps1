# Launch the diffraction workbench in its compatible native interaction profile.
param([string]$Blender = 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe',
      [ValidateSet('native','reciprocal')][string]$DielectricProfile = 'native',
      [switch]$Legacy)
$ErrorActionPreference = 'Stop'
if ($Legacy) { throw 'RT 2.1 launchers are retired. Use the shared RT 2.2 workflow or restore the isolated recovery package; see RT21_RETIREMENT.txt.' }
$scenePath = Join-Path $PSScriptRoot 'outputs/differt-bridge/examples/diffraction_batch/Diffraction_Workbench.blend'
if (-not (Test-Path -LiteralPath $scenePath)) { throw "Workbench missing: $scenePath" }
& (Join-Path $PSScriptRoot 'Launch_Shared_RT.ps1') -Blender $Blender -Scene $scenePath -Profile $DielectricProfile

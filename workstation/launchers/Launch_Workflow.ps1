# Shared Sionna RT 2.2 + existing DiffeRT; explicit aligned research profile.
param(
    [switch]$Legacy,
    [ValidateSet('native','phase')][string]$Profile = 'native',
    [string]$Blender = 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe',
    [string]$Scene
)
$ErrorActionPreference = 'Stop'
if ($Legacy) { throw 'RT 2.1 launchers are retired. Use the shared RT 2.2 workflow or restore the isolated recovery package; see RT21_RETIREMENT.txt.' }
if (-not $Scene) {
    $file = if ($Profile -eq 'phase') { 'Shared_Segment_Length_Workbench.blend' } else { 'Native_Float32_Workbench.blend' }
    $Scene = Join-Path $PSScriptRoot "outputs/differt-bridge/examples/segment_length_aligned/$file"
}
& (Join-Path $PSScriptRoot 'Launch_Shared_RT.ps1') -Blender $Blender -Scene $Scene -Profile $Profile

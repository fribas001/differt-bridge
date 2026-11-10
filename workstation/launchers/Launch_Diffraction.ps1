# Launch the diffraction workbench in its compatible native interaction profile.
param([string]$Blender = 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe',
      [ValidateSet('native','reciprocal')][string]$DielectricProfile = 'native',
      [switch]$Legacy)
$ErrorActionPreference = 'Stop'
$scenePath = Join-Path $PSScriptRoot 'outputs/differt-bridge/examples/diffraction_batch/Diffraction_Workbench.blend'
if (-not (Test-Path -LiteralPath $scenePath)) { throw "Workbench missing: $scenePath" }
if (-not $Legacy) {
    & (Join-Path $PSScriptRoot 'Launch_Shared_RT.ps1') -Blender $Blender -Scene $scenePath -Profile $DielectricProfile
    return
}
Write-Host 'Historical Sionna 2.1 research runtime selected; shared packages are untouched.'
$names = @('RADIO_SEGMENT_PROFILE','SIONNA_GEOMETRY_PROFILE','DIFFERT_ARITHMETIC_PROFILE','DIFFERT_FIELD_PRECISION','DIFFERT_DIFFRACTION_GEOMETRY','RADIO_DIELECTRIC_PROFILE')
$previous = @{}
foreach ($name in $names) { $previous[$name] = [Environment]::GetEnvironmentVariable($name,'Process') }
try {
    $env:RADIO_SEGMENT_PROFILE = 'native'
    $env:SIONNA_GEOMETRY_PROFILE = 'native'
    $env:DIFFERT_ARITHMETIC_PROFILE = 'native'
    $env:DIFFERT_FIELD_PRECISION = 'float32'
    $env:DIFFERT_DIFFRACTION_GEOMETRY = 'validated'
    $env:RADIO_DIELECTRIC_PROFILE = $DielectricProfile
    & $Blender $scenePath
} finally {
    foreach ($name in $names) { [Environment]::SetEnvironmentVariable($name,$previous[$name],'Process') }
}

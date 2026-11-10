# Project-scoped launcher; all runtime imports happen in external workers.
param(
    [Parameter(Mandatory=$true)][string]$Scene,
    [ValidateSet('native','phase','reciprocal')][string]$Profile = 'native',
    [string]$Blender = 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe'
)
$ErrorActionPreference = 'Stop'
$rt = Join-Path $env:USERPROFILE 'Documents/Codex/shared-envs/sionna-rt-2.2-py312'
$python = Join-Path $rt 'Scripts/python.exe'
foreach ($file in @($python,$Blender,$Scene)) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "Required file missing: $file" }
}
$names = @('RADIO_RT22_PROFILE','RADIO_SEGMENT_PROFILE','SIONNA_GEOMETRY_PROFILE','DIFFERT_ARITHMETIC_PROFILE','DIFFERT_FIELD_PRECISION','DIFFERT_DIFFRACTION_GEOMETRY','RADIO_DIELECTRIC_PROFILE','DRJIT_LIBLLVM_PATH','PYTHONPATH','PYTHONHOME','PYTHONDONTWRITEBYTECODE')
$previous = @{}
foreach ($name in $names) { $previous[$name] = [Environment]::GetEnvironmentVariable($name,'Process') }
try {
    $env:RADIO_RT22_PROFILE=$Profile
    $env:RADIO_SEGMENT_PROFILE='native'
    $env:SIONNA_GEOMETRY_PROFILE='native'
    $env:DIFFERT_ARITHMETIC_PROFILE='native'
    $env:DIFFERT_FIELD_PRECISION='float32'
    $env:DIFFERT_DIFFRACTION_GEOMETRY='validated'
    $env:RADIO_DIELECTRIC_PROFILE='native'
    if ($Profile -eq 'phase') {
        $env:RADIO_SEGMENT_PROFILE='shared_1mm'
        $env:SIONNA_GEOMETRY_PROFILE='unshifted_float64'
        $env:DIFFERT_ARITHMETIC_PROFILE='sionna_order'
    } elseif ($Profile -eq 'reciprocal') {
        $env:RADIO_DIELECTRIC_PROFILE='reciprocal'
    }
    $env:PYTHONDONTWRITEBYTECODE='1'
    $env:PYTHONPATH=$null
    $env:PYTHONHOME=$null
    $env:DRJIT_LIBLLVM_PATH=$null
    & $python -I -B -m codex_sionna_runtime --check
    if ($LASTEXITCODE -ne 0) { throw 'Shared runtime verification failed; Blender was not started.' }
    & $Blender $Scene --python (Join-Path $PSScriptRoot 'work/github-update/differt-bridge/scripts/blender_shared_runtime.py')
    if ($LASTEXITCODE -ne 0) { throw 'Blender exited with an error.' }
} finally {
    foreach ($name in $names) { [Environment]::SetEnvironmentVariable($name,$previous[$name],'Process') }
}

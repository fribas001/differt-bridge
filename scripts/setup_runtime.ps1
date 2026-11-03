param([string]$Python = 'python', [string]$Environment = '.venv')
$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $PSScriptRoot
Push-Location $project
try {
    & $Python -m venv $Environment
    if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed' }
    $runtime = Join-Path $Environment 'Scripts/python.exe'
    & $runtime -m pip install -r requirements-external.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
    & $runtime -c 'import differt,jax; print("DiffeRT",differt.__version__,"JAX",jax.__version__,jax.devices())'
    if ($LASTEXITCODE -ne 0) { throw 'Runtime probe failed' }
    Write-Output ('Select this executable in Blender: ' + (Resolve-Path $runtime).Path)
} finally { Pop-Location }

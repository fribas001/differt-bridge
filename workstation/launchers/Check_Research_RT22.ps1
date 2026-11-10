# Check source guards, corner obstacles and optionally both Blender profiles.
param([switch]$RunComparison,
      [string]$Blender = 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe')
$ErrorActionPreference = 'Stop'
$checkArgs = @('--workspace',$PSScriptRoot,'--blender',$Blender)
if ($RunComparison) { $checkArgs += '--run-comparison' }
& (Join-Path $PSScriptRoot 'work/runtime/Scripts/python.exe') -B (Join-Path $PSScriptRoot 'work/github-update/differt-bridge/scripts/check_research_workflow.py') @checkArgs
if ($LASTEXITCODE -ne 0) { throw 'Research workflow verification failed; see the fresh r22-check receipt.' }

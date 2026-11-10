# Explicit phase-aligned research session; old runtime remains available.
param([string]$Blender = 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe', [switch]$Legacy)
& (Join-Path $PSScriptRoot 'Launch_Workflow.ps1') -Blender $Blender -Profile phase -Legacy:$Legacy

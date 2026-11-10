# Open the existing workbench with the independently assessed reciprocal profile.
param([string]$Blender = 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe', [switch]$Legacy)
& (Join-Path $PSScriptRoot 'Launch_Diffraction.ps1') -Blender $Blender -DielectricProfile reciprocal -Legacy:$Legacy

# Reciprocal dielectric diffraction profile

The `reciprocal` bridge profile corrects local polarization dyads, reciprocity,
Sionna's near-edge reflection acceptance, mixed reflection/diffraction geometry,
depth padding and the exact shadow/reflection-boundary contribution convention.
It is optional. Native engines remain the default; this is not an upstream release.

The measured report is `examples/dielectric_corrections/index.html` in the local
delivery. It contains the independent Maxwell results, raw data archive and
limitations. Current native Sionna 2.1.0 and DiffeRT 0.12.0 have worst tested
dielectric reciprocal gain gaps of 29.75 and 13.67 dB respectively. Corrected
gaps are below 0.00018 dB. Both corrected profiles pass 580/580 near-boundary
GO-presence checks and 50/50 non-null field-jump checks. All 54 dielectric exact
boundary cases meet the declared 0.1% free-space-normalized limit check.

## Independent accuracy assessment

`maxwell2d_reference.py` solves conservative 2D frequency-domain Maxwell equations
with a coordinate-stretched PML. It imports neither engine nor UTD formulas.
The 40/60/80 cells-per-wavelength campaign is checked against the signed Hankel
free-space Green function, an exact PEC wedge eigenfunction expansion, PML
thickness changes, linear residuals and discrete source/probe reciprocity.

Actual engine outputs are compared after a disclosed 3D point-source to 2D
line-source conversion. In the sampled solid lossy wedge, corrected total-field
RMS error is 2.8–5.7%; the remaining field after subtracting GO still has 19–49%
RMS error. Weak-channel gain errors remain substantial. These corrections improve
consistency and measured accuracy but do not make UTD an exact dielectric solver.
Thin finite slabs, arbitrary skew 3D accuracy and multiple-edge coincident limits
are not independently certified by the 2D solid-wedge reference.

## Workstation use

Run `Launch_Reciprocal_Diffraction.ps1`, or
`Launch_Diffraction.ps1 -DielectricProfile reciprocal`. The ordinary launcher
uses native behavior. Both open the existing saved Blender workbench and both
external runtimes. No engine source or installed extension file is overwritten.

`install_reciprocal_profile.py WORKSPACE` installs six helper modules plus one
`.pth` file per runtime. The installation manifest lists the exact owned files
and their SHA-256 hashes. Source/version guards reject an incompatible runtime.
The `.pth` hook imports no scientific packages in native mode.

Activation requires `RADIO_DIELECTRIC_PROFILE=reciprocal`. The Sionna hook runs
when `sionna.rt` imports. The DiffeRT hook runs when the bridge's `differt_backend`
imports; importing bare upstream `differt` alone does not activate this bridge
profile. Unset the variable to restore native behavior immediately.

The full dyad uses an ordinary Cartesian transpose, not complex conjugation.
The boundary kernel takes the shadow-side limit within 8e-7 radians and merges a
coincident GO companion only when an already-valid diffraction route matches it
within a 4e-7 radian geometric criterion. No obstacle exclusion radius is used.
The geometry adapter is CPU/detached; it does not supply geometry gradients.

## Reproduction

Use `run_dielectric.py` with explicit native/reciprocal profiles. It clears any
inherited reciprocal activation before starting each worker. `--manifest` selects
the Maxwell or mixed-path fixture sets. The evidence archive contains every
manifest and raw result used in the report. `run_maxwell_reference.py` produces
the independent main/PML campaigns; `run_maxwell_boundaries.py` produces the
boundary controls. `analyze_maxwell_engines.py` compares actual engine outputs.

The final Python regression run passes 267 tests with two documented strict
wavelength-policy assertions excluded. No tolerance was relaxed. The saved
Blender diffraction workbench is exercised through both installed extensions;
the native furnished-room check still matches 1,299 paths with zero exported
phase difference. See the JSON receipts for scope, versions and exact results.

# Optional 3D dielectric full-wave refinement

This document describes the original single-resolution companion. The current
launcher defaults to the validated [spatially converged mode](dielectric3d-weak.md).
Use `-Accuracy standard` to reproduce this document's original comparison.

This companion reduces the canonical dielectric shadow-field discrepancy by
solving the coupled Maxwell transmission problem beside the two native ray
exports. It is a shared numerical solver for both workflows, not a new native
UTD coefficient or an arbitrary-scene patch. It returns a single-frequency
complex point-dipole channel; it does not add ray delays, broadband CIR taps,
moving-object physics or an end-to-end automatic-differentiation graph.

`scripts/dielectric3d_refinement.py` wraps the coupled vector boundary-integral
kernel. Both propagating and evanescent longitudinal modes are sampled by
contour quadrature up to the declared cutoff of 24 (k0 = 2 pi);
transverse fields and coupling between electric/magnetic longitudinal
components are retained. The analytic free-space electric dyadic is added,
with the same short-dipole normalization used for the native comparison.
There is no FEM/reference lookup, fitted gain or phase, or completed-channel
reciprocity averaging in this product solver.

The default uses 32 panels per wavelength and 64 spectral nodes. A completed
48-panel concrete run provides a finer control. The original 48-panel plan
was amended for resource cost before the holdout reference results existed;
the equations and acceptance thresholds were unchanged. Both plans and
historical source are retained in the evidence archive. The 48-panel concrete
shadow discrepancy is 1.3594% against FEM64; the FEM48-to-FEM64 comparison
changes the shadow field by 0.6980%. These are independent numerical
comparisons, not certified pointwise error bounds.

The main report contains the authoritative primary and holdout tables for the
32-panel mode. The primary set has 3,888 vector channels. The 1,008-channel
holdout introduces permittivities 3.3−0.48i and 7.1−1.1i, new source azimuths,
radii and heights, a new receiver radius, and new transition samples. All
nine Cartesian dipole combinations are included. Acceptance requires
shadow RMS below 5% and at least a threefold improvement for each material
and aggregate, against independent finite-element references.

Simple unfitted finite-distance endpoint factors were also investigated.
They reduce the old aggregate shadow RMS from 33.08% to 26.33% but worsen
phase-tail errors. They were not installed. The coupled field includes
finite-distance, vector and internal-dielectric effects together; the study
does not uniquely attribute the old discrepancy to one of those terms.
The measured observable is the total field in geometric shadow, including
possible transmission through the solid dielectric. It is not an isolated
Maxwell diffraction coefficient; the native benchmark disables refraction.
The 33.08% therefore cannot be assigned entirely to a native UTD coding error.

## Supported domain

Every scene is validated before computation or output. A manifest must
explicitly declare an infinite solid dielectric quadrant and 3D electric point
sources. The accepted canonical mesh has two 160-wavelength faces and its
central z edge, wavelength 1 m, single x/y/z dipoles, source/receiver radii
1–2.5 wavelengths, exterior angles 5–265 degrees, and absolute heights and
height differences no greater than 3 wavelengths. Relative permittivity is
restricted to real part 2–8 and loss 0.25–1.5. The native 10-wavelength slab
proxy is distinct from the companion's explicitly declared solid volume.

These bounds restrict the computational domain; they do not guarantee one
accuracy bound over every combination. Finite edges, arbitrary bodies,
additional obstacles, changed faces, arrays, other orientations, thin slabs,
other interactions and materials outside the envelope are rejected. A test
with an added one-micron obstacle verifies whole-batch rejection before any
field solve. The usual Blender/native workflow remains available for general
scenes, with its existing full-mesh visibility checks.

## Run in the configured workspace

```powershell
.\Compare_Dielectric3D_Wedge.ps1

# Reuse only matching, checksummed numerical steps from this study:
.\Compare_Dielectric3D_Wedge.ps1 `
  -CheckpointFolder work/d3shadow/concrete_standard_product_modes
```

The launcher accepts `-Manifest`, `-Output`, `-Panels` and `-CheckpointFolder`.
It runs both configured reciprocal runtimes, preserves their native exports,
and writes `refinement.json` plus `comparison.json`. Reusing a checkpoint
requires matching physical inputs, numerical parameters and solver source
hashes. A mismatch fails explicitly. The full-wave calculation is much more
expensive than local ray coefficients; use limited concurrency on the tested
16 GB Windows workstation.

No upstream runtime, installed optional-profile helper or Blender extension
is replaced by this mode. The default native workflow and the existing
reciprocal workbench keep their previous behavior.

## Evidence and reproduction

The workstation report is
`outputs/differt-bridge/examples/dielectric3d_refinement/index.html`, beside
the animation, relative-path Blender timeline, numerical comparisons and
checksummed evidence archive. `Regenerate_Dielectric3D_Refined_Animation.ps1`
renders, encodes, decodes sample frames and reopens the saved timeline.

Generate manifests with `dielectric3d_shadow_cases.py`, run the independent
FEM holdouts with `run_dielectric3d_holdout_reference.py`, and use
`analyze_dielectric3d_refinement.py` for per-port, per-material and aggregate
metrics. `check_dielectric3d_shadow_reciprocity.py` checks separately solved
forward/reversed source locations. Source-level numerical-memory fixes in
the FEM implementation release unused assembly arrays and avoid copying
large LU factors solely for diagnostics; old/new fields are bit-identical.
Cache migrations and interrupted-run logs are retained.

For the standard product fields, the following commands use the campaign's
existing, source-checked checkpoints. Run them from the workspace root:

```powershell
$env:OPENBLAS_NUM_THREADS = '1'
$taskPython = 'work/runtime/Scripts/python.exe'
$taskScripts = 'work/github-update/differt-bridge/scripts'
& $taskPython -B "$taskScripts/dielectric3d_shadow_cases.py" work/d3shadow
foreach ($taskMaterial in @('concrete','lower','holdout_a','holdout_b','reciprocity')) {
    & $taskPython -u -B "$taskScripts/dielectric3d_refinement.py" `
        "work/d3shadow/${taskMaterial}_cases.json" `
        "work/d3shadow/${taskMaterial}_standard_product.json"
    if ($LASTEXITCODE -ne 0) { throw "Failed: $taskMaterial" }
}
& $taskPython -B "$taskScripts/analyze_dielectric3d_refinement.py" .
& $taskPython -B "$taskScripts/check_dielectric3d_shadow_reciprocity.py" .
& $taskPython -B "$taskScripts/check_dielectric3d_shadow_boundaries.py" .
```

The analysis uses the completed independent FEM runs and native exports in
the evidence. To rerun a holdout reference independently, use
`run_dielectric3d_holdout_reference.py <material_manifest> <fresh_output_folder>
--resolution 32` or `--resolution 48`. Primary references use
`dielectric3d_synthesis.py <fresh_output_folder> --method fem --resolution 64
--order 8` for concrete, or `--resolution 48 --epsilon 2.5 --loss 0.35
--order 8` for the second material. Exact source snapshots and configuration
JSON accompany every archived run. Keep the historical checkpoints intact;
source changes deliberately invalidate their reuse. Matrix-memory changes
were separately checked for bit-identical fields before cache migration.

The primary reference refinement changes both mesh and Fourier order
(6 to 8); the holdout reference comparisons vary mesh at fixed order 8.
Reported reference changes are empirical sensitivity measurements. Both
Maxwell implementations are project code independent of the ray tracers,
not external third-party certification. Weak fields and nulls require
particular care when interpreting relative phase and small residual errors.

# Weak-polarization spatial convergence

The preceding shared dielectric companion left 18.7104% complex RMS error
on `holdout_b_s1_yz_h0.7`, against FEM48. This is a weak total shadow field,
with substantial cancellation between its free-space and scattered spectral
terms. It is not a native Sionna/DiffeRT UTD coefficient error.

`dielectric3d_weak_diagnostics.py` audits the archived mode fields and finds
the discrepancy primarily in propagating modes. The four selected controls
compare panels 16/24/32/48/64, doubled panel quadrature, longer unstretched
boundary, longer absorbing tail, and independent FEM64. The dominant modes
show roughly first-order panel error. Boundary/quadrature changes are much
smaller. Higher-q modes do not show a uniform first-order rate; all controls
remain in the report and evidence.

The optional correction is fixed spatial Richardson extrapolation:

```text
F(h) = F(0) + c h + ...
F_corrected = 2 BIE32 - BIE16
```

`scripts/dielectric3d_converged.py` applies these same weights to every
material, position and polarization. It never reads a Maxwell reference,
fits a complex gain/phase, or averages forward/reverse completed channels.
The weights sum to one, preserving the analytic free-space term in exact
arithmetic. The original BIE implementation is unchanged. The field remains
a single-frequency shared full-wave companion, without native ray delays or
an automatic-differentiation graph.

Every case is validated before either resolution runs. All original scene,
material, orientation and obstacle guards remain active. The two component
fields must have identical physical inputs, spectral settings and source
hashes. The supported domain remains the explicitly declared infinite solid
dielectric quadrant; general Blender scenes continue to use the existing
native workflow. Added or changed obstacles are rejected, never removed.

## Validation

The candidate and fresh holdout manifest were frozen before new holdout FEM
results were available. The fresh set adds 324 channels with permittivities
4.4-0.65i and 6.4-0.9i, new source/receiver radii, source azimuth 64 degrees,
three receiver heights, all nine Cartesian dipole pairs and shadow-boundary
stencils. Earlier 3,888 primary and 1,008 holdout channels are retained.

The original weak ports receive FEM64 at spectral order 8 and FEM48 at order
12. These separate mesh and spectral sensitivity from the prior FEM48/order8
field. Independent enlarged-domain FEM controls check four representative
modes. The FEM implementation uses volume equations, with no BIE/UTD operator.
Source snapshots, configuration JSON and hashes document every numerical mode.

The fixed gates are recorded in `work/d3weak/study_plan.json`. Every
non-null polarization group, including any new worst case, is reported.
Material averages are not per-port guarantees. Reference refinement changes
are empirical numerical sensitivities, not certified physical error bounds;
both Maxwell solvers are project implementations, not third-party validation.

## Use the configured workspace

After validation, the comparison launcher defaults to the converged companion:

```powershell
.\Compare_Dielectric3D_Wedge.ps1
.\Compare_Dielectric3D_Wedge.ps1 -Accuracy standard
```

The original single-resolution mode accepts its existing `-Panels` values.
The converged mode uses the validated 16/32 pair. `-CheckpointFolder` supplies
the fine cache; `-CoarseCheckpointFolder` supplies the coarse cache. Both must
match current inputs and original BIE source hashes. The independent-reference
files are never needed by the product workflow.

```powershell
.\Compare_Dielectric3D_Wedge.ps1 -Accuracy converged `
  -CheckpointFolder work/d3shadow/concrete_standard_product_modes `
  -CoarseCheckpointFolder work/d3weak/concrete_converged_modes/coarse16
```

Fresh output defaults to `work/dielectric3d_comparison/<accuracy>` so historical
study outputs are retained. No installed runtime, optional-profile helper or
Blender extension is replaced. Both native and reciprocal Blender checks and
a fresh two-engine companion comparison are required before final packaging.

## Reproduce the research

Run from the configured workspace root with `OPENBLAS_NUM_THREADS=1`.
`dielectric3d_weak_cases.py work/d3weak` regenerates the fresh manifests.
For each prior material, run:

```powershell
$taskPython = 'work/runtime/Scripts/python.exe'
$taskScripts = 'work/github-update/differt-bridge/scripts'
$env:OPENBLAS_NUM_THREADS = '1'
& $taskPython -B "$taskScripts/dielectric3d_converged.py" `
  work/d3shadow/holdout_b_cases.json work/d3weak/holdout_b_converged.json `
  --fine-checkpoint work/d3shadow/holdout_b_standard_product_modes
```

For the new materials, pass `new_a_cases.json` or `new_b_cases.json` without
an old fine checkpoint. `run_dielectric3d_holdout_reference.py` independently
solves each fresh manifest at `--resolution 32` and `--resolution 48`.
`run_dielectric3d_weak_reference.py . --resolution 64 --order 8` and its
`--resolution 48 --order 12` counterpart reproduce the dedicated weak-port
reference refinements. `probe_dielectric3d_weak.py` supplies the four-mode
resolution, quadrature and domain controls.

`analyze_dielectric3d_weak.py .` checks every frozen acceptance gate.
`Regenerate_Dielectric3D_Weak_Animation.ps1` renders, encodes, decodes samples
and reopens the relative-path Blender timeline. The authoritative report is
`outputs/differt-bridge/examples/dielectric3d_weak/index.html`, with measured
fields, verification receipts and the compact checksummed evidence archive.
Historical source/data remain in the prior report and its evidence archive.

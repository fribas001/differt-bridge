# Further investigation of the 1.56% polarization residual

The production field is unchanged. Refining the independent Maxwell reference
from FEM96/64 to FEM128/64 changes the target discrepancy from 1.5616% to
1.2179%. The latest FEM112/64 to FEM128/64
increment is 0.1695%; this measured
sensitivity is not a certified continuum error bound. The target is still
`holdout_b_s0_zx_h0.7`, z-to-x polarization, epsilon approximately 7.1-1.1i.
All fourteen receiver ports, including eight strict-shadow ports, remain.

| Independent reference | Production BIE16/32 discrepancy | Research BIE32/64 discrepancy |
| --- | ---: | ---: |
| FEM32 | 8.8660% | 8.4491% |
| FEM48 | 4.3922% | 3.9444% |
| FEM64 | 2.7767% | 2.2971% |
| FEM80 q<7 / FEM64 tail | 2.0054% | 1.5005% |
| FEM96 q<7 / FEM64 tail | 1.5616% | 1.0290% |
| FEM112 q<7 / FEM64 tail | 1.3576% | 0.8130% |
| FEM128 q<7 / FEM64 tail | 1.2179% | 0.6612% |

The production median absolute phase residual is
0.2437 degrees, with p95
1.0656 degrees. The last reference increment
changes phase by median 0.0175 degrees
and p95 0.2770 degrees.

## Independent reference and recovery controls

The coupled volume FEM and boundary-integral companion are independently
implemented project codes. Both share the declared Fourier convention and
analytic free-space normalization. This is an infinite solid dielectric
quadrant and a single-frequency point-dipole field, not a general finite-object
or broadband Maxwell certification.

FEM112 and FEM128 resolve the first 32 Fourier nodes, real(q)<7. The other
32 nodes retain explicitly selected FEM64 fields with input hashes. Two fresh
FEM128 tail probes check that approximation. Prior spectral-order, domain and
PML studies are preserved. No material, geometry, source, PML or normalization
change is made. The FEM-only assumed second-order extrapolations are reported
as diagnostics, not selected references or guaranteed bounds.

Exact Fourier-z reweighting extends the same source-z modes to both existing
receiver heights, 0.7 and 2.2 wavelengths, and all three receive polarizations.
All 64 earlier modal selections match exactly, and the old full-height FEM64
synthesis is reproduced within
1.67e-16 relative error.
This gives six refined groups without claiming additional volume solves.
Tail sensitivity is checked separately at every refined height/polarization.

A cubic field-recovery stencil was tested on the same nodal solutions. Its
z-to-x result improved in the aligned planar controls while its full-vector
error worsened, so it was rejected as a general fix. The original sampler
remains authoritative. Fresh off-grid Fresnel controls test all nine dyadic
components at two receivers and two Fourier nodes over FEM64/96/128. Their
finest original vector errors are
0.0661%, 0.0533%.
These planar checks do not certify a corner-error bound.

## Separate boundary-integral candidate

The fixed, unfitted candidate is `2*BIE64-BIE32`; production remains
`2*BIE32-BIE16`. Every BIE64 Fourier node is recomputed for both holdout-b
sources, both heights and all nine polarizations. Four modal comparisons
against the preceding independently saved probes verify the complete-vector
sweep. It improves 32 of
36 non-null shadow groups against their declared
references. The report includes all regressions. Most groups still use FEM64,
so an apparent regression can include reference bias. One material is
insufficient evidence for replacing the production default.

Weighted coherent modal residuals separate reference increments from BIE
increments. They reconcile with the complete field residual; interval norms
do not add because fields interfere. No amplitude or phase fit, discarded
obstacle, removed port or reference-driven coefficient is used.

## Resource correction and preserved workflow

Large direct LU attempts hit memory limits. Exact interface Schur and static
pivot trials are retained as diagnostic experiments. The accepted research
adapter uses SuperLU's zero-drop path, basic rule only, zero tolerance,
initial fill allocation 3, diagonal-pivot threshold 0.01 and panel size 8.
It passes twelve direct-field comparisons at FEM64/96/128 and a FEM112
feasibility check. Every new solve also passes the residual gate in the
original assembled matrix. Installed SciPy is unchanged.

Early static-pivot memory profiles accidentally measured the Windows venv
launcher; their per-worker counters are invalid and are labelled accordingly.
The corrected guard measures the actual interpreter and stops its process
tree if available commit falls below 1 GiB or free disk below 5 GiB.

Both native engines, Blender extensions, scene guards and the default shared
companion are preserved. Fresh regression tests, paired campaigns and native
and reciprocal Blender checks accompany the report. The 60-second animation
separates the old reference, new reference and research candidate. The two
workflows share the explicitly labelled companion; equal companion fields
must not be interpreted as equal native UTD accuracy.

## Reproduce

From the workstation workspace:

```powershell
.\Refine_Dielectric3D_Residual.ps1
.\work\d3res\check_workflows.ps1
& .\work\runtime\Scripts\python.exe -B .\work\github-update\differt-bridge\scripts\build_dielectric3d_residual_report.py .
.\Regenerate_Dielectric3D_Residual_Animation.ps1
& .\work\runtime\Scripts\python.exe -B .\work\github-update\differt-bridge\scripts\publish_dielectric3d_residual_summary.py .
& .\work\runtime\Scripts\python.exe -B .\work\github-update\differt-bridge\scripts\package_dielectric3d_residual.py . --clean-frames
```

The report, animation, Blender timeline and checksummed evidence are in
`outputs/differt-bridge/examples/dielectric3d_residual`. The preceding study
and all its artifacts remain unchanged. `verification.json` records the
actual checks; partial and rejected trials are preserved in the archive.

[Previous reference audit](dielectric3d-polarization.md).
The [SciPy zero-drop solver interface](https://docs.scipy.org/doc/scipy/reference/generated/scipy.sparse.linalg.spilu.html)
documents numerical options; it is not physical validation.

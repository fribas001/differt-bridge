# Remaining polarization residual: reference-first investigation

The previous largest group, `holdout_b_s0_zx_h0.7`, differed from the
shared optional companion by 4.3922% against FEM48. The independent reference
itself changed by 4.8754% from FEM32 to FEM48. The present study holds the
production fields fixed while refining that reference. Against the directly
calculated FEM96 low-q / FEM64 tail reference, the discrepancy is 1.5616%,
with a median absolute phase difference of 0.3282 degrees. The last spatial
increment changes the reference by 0.5002%; that sensitivity is not a
certified error bound. These values revise the comparison's error attribution,
not the native diffraction model or the companion's output.

The target is z-to-x polarization, epsilon approximately 7.1-1.1i, source
angle phi=43.5 degrees at radius 1.25 wavelengths and z=-0.2, receiver radius
2.3 and z=0.7. All 14 angles are retained, including eight strict-shadow
samples and the three-point shadow-boundary stencil.
Angles use the wedge convention: phi is measured counterclockwise from +y,
so the Cartesian azimuth measured from +x is 90 degrees plus phi.

## Independent calculations

- Uniform FEM64, all modes and all nine polarizations, both source positions
  and both heights, for both previous holdout materials (1,008 channels).
- Target FEM80 and FEM96 below longitudinal wavenumber q=7. The high-q tail
  retains the separately solved FEM64 values with explicit source and input
  provenance. These are labelled mixed-resolution references throughout.
  The cutoff uses the real contour coordinate; q itself has an imaginary part.
- Fresh FEM96 checks at two tail nodes, plus the absolute magnitude sum of
  the complete computed FEM64 tail. This is not a certified continuum bound.
- Target FEM48/order12 versus FEM48/order8 to isolate spectral integration.
- Four-mode fixed-grid domain and absorbing-layer checks, plus doubled BIE
  panel quadrature and finer 32/64 BIE extrapolation as diagnostics.
- Fresh analytic planar-interface and vacuum controls, independent of BIE.

The reference uses coupled longitudinal vector finite-element volume
equations. The companion uses boundary integral equations. Both retain the
existing Fourier conventions and analytic free-space normalization, whose
independent tests are in the preceding evidence. Both are project codes;
agreement is not third-party certification.

A thinner absorbing layer was tested and rejected. The fine reference keeps
the original domain and PML. A process-local SuperLU pivot threshold of 0.01
reduces factor storage; six same-matrix FEM64 and seven FEM80 controls agree
with standard factorization within 1.4e-13. Every fine solve retains the residual gate. The
fresh analytic-interface controls also exercise this linear solver policy.
Installed SciPy and the original FEM equations are not modified.

The additional FEM-only order-2 extrapolations are diagnostics. They use no
production field to estimate their coefficients. The finest directly
calculated mixed-resolution reference is selected for the target. Per-group
tables retain reference resolutions, mesh sensitivities and any worsening
residuals. The rest of the benchmark is not silently relabelled FEM96.

## Measured outcomes

| Target reference | Unchanged companion shadow RMS discrepancy |
| --- | ---: |
| Uniform FEM32 | 8.8660% |
| Uniform FEM48 | 4.3922% |
| Uniform FEM64 | 2.7767% |
| FEM80 low-q / FEM64 tail | 2.0054% |
| FEM96 low-q / FEM64 tail | 1.5616% |

The target's median absolute phase residual changes from 0.7631 to 0.3282
degrees. Its final reference increment shifts phase by a median 0.1343
degrees, illustrating the reference sensitivity that remains. The second
material's illustrated z-to-x case measures 2.0334% against uniform FEM64.
The largest retained group is `new_b_zx_h0.45` at 2.8988%, using its earlier
FEM48/order8 reference, not the finer target reference.

Spectral, domain, PML, tail, planar-interface, vacuum and linear-solver
controls pass. The analytic planar-interface vector errors contract to
0.2300% and 0.2081% at FEM64; the corresponding z-to-x errors are 0.5015%
and 0.5211%. These are selected modal controls, not a bound on the wedge
solution. All 126 retained shadow-boundary stencils are finite; the largest
field RMS discrepancy there is 1.7055% and the largest normalized span
discrepancy is 0.01347%, excluding reference RMS at or below 1e-9.

## Product and workflow

The validated fixed `2*BIE32-BIE16` companion remains unchanged. Native engine
fields, installed runtimes, Blender extensions, obstacle guards, reciprocity
and ordinary scene handling are preserved. The evidence does not justify
fitting the product to a coarse reference. The companion still supports only
the explicitly declared infinite solid dielectric quadrant, at a single
frequency; it is not a native diffraction coefficient or a broadband CIR.

From the configured workspace root:

```powershell
.\Compare_Dielectric3D_Wedge.ps1
.\Refine_Dielectric3D_Polarization_Reference.ps1
.\work\d3pol\check_workflows.ps1
& .\work\runtime\Scripts\python.exe -B .\work\github-update\differt-bridge\scripts\build_dielectric3d_polarization_report.py .
.\Regenerate_Dielectric3D_Polarization_Animation.ps1
& .\work\runtime\Scripts\python.exe -B .\work\github-update\differt-bridge\scripts\package_dielectric3d_polarization.py . --clean-frames
```

Generate the report after the reference and workflow checks pass. The final
packaging step verifies the decoded video and saved Blender timeline before
removing only the hash-verified temporary frame sequence. It leaves the source
and decoded preview frames, numerical evidence and previous outputs intact.

Research data live in `work/d3pol`; native holdout fixtures in `work/d3pr`.
The reference launcher is sequential to limit peak memory. It resumes only
matching, checksummed checkpoints. The initial diagnostic plan and explicit
multiresolution addendum predate the fine-reference results.

The authoritative report is
`outputs/differt-bridge/examples/dielectric3d_polarization/index.html`.
Its evidence archive contains configurations, numerical fields, source
snapshots, tests, runtime checks, the report, and hashes of preserved previous
artifacts. The video includes the old and refined reference comparisons,
mesh convergence, boundary behavior and a second material. Native paths are
shown as geometric context, with the shared full-wave fields clearly labelled.

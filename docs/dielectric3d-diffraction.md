# Native 3D dielectric diffraction: Maxwell validation

The 8 November 2026 study adds a full-vector electric point-source benchmark
for an infinite solid dielectric right-angle wedge. It uses coupled Fourier-z
Maxwell transmission solves, independently discretized with boundary integrals
and Q1 finite elements. Propagating and evanescent modes, transverse electric
components, and cross-polarized ports are retained. This is a 3D field in a
z-invariant geometry, not a certification of arbitrary 3D solids or finite edges.

The campaign has 3,888 primary complex channels: two lossy dielectrics, two
source azimuths, nine dipole port combinations, three receiver heights and
36 receiver angles. Nine additional port pairs test reciprocity. Wavelength
is 1 m, source radius 1.5 wavelengths and receiver radius 2 wavelengths.
Native ray meshes extend 160 wavelengths, with the central edge selected,
10-wavelength local slabs and refraction disabled. The solid Maxwell wedge
also contains internal dielectric waves and coupling between its faces.

Reference checks include analytic dielectric-plane dyadics, analytic 3D
free-space Fourier synthesis, an independent exact PEC point-wedge solution,
grid/panel and quadrature refinement, enlarged computational domains, vacuum
controls and independent reversed-source solves. Both references are project
implementations independent of the ray tracers, not external certification.
Initial coarse vacuum/reciprocity failures are retained; refined controls
converge and pass. The full 3D reference reciprocity discrepancy is 0.0803%.

Fine BIE/FEM differences are 0.3304% and 0.2304% globally for the two materials;
the largest height-group difference is 1.0604%. Concrete FEM32-to-FEM48 changes
0.1096%, and Fourier quadrature refinement changes 0.0219%. These are empirical
convergence indicators, not pointwise error bounds or tiny-phase certification
near destructive-interference nulls.

| Field profile | Total-channel complex RMS | Common geometric-shadow RMS |
| --- | ---: | ---: |
| Sionna native | 34.5585% | 61.3025% |
| DiffeRT native | 33.3267% | 71.4863% |
| Sionna reciprocal | 32.9533% | 33.0830% |
| DiffeRT reciprocal | 32.9533% | 33.0830% |

These are total-channel differences, not isolated diffraction-coefficient
errors. An offline diagnostic replacing only existing visible LOS components
with the exact electric point-dipole field reduces corrected total RMS to
4.4380%; it does not change shadow results. Finite-distance source terms
therefore explain most of the global gap. Reflected-field asymptotics and
internal dielectric-wave physics remain mixed with diffraction. That diagnostic
is not installed, and no fitted dielectric correction is promoted.

The opt-in reciprocal profile now repairs cancellation in Sionna's material
complex square root. A scaled norm and division for its smaller component
preserve weak loss. This source-guarded fix affects material Fresnel/slab
calculations and preserves derivatives and the previous opaque-slab guard.
DiffeRT's native material square root and both engines' geometry are unchanged.
It has negligible effect on the two moderately lossy benchmark materials.

Against independent float64 Maxwell slab coefficients, 864 cases reduce worst
absolute error from 0.02673648 to 0.00017072, and RMS from 0.00122791 to
0.00001146. Forty-eight extreme root checks and three derivative checks pass.
The domain includes epsilon-real 2.5, 5.24 and 8; it does not establish a fix
for every matched-index grazing-interface radicand.

All 1,328 engine fixture executions, 47 targeted tests and the fresh native
and reciprocal Blender checks pass. All 252 before/after case path geometries
match exactly. The standard furnished-room check matches 1,299 paths with
zero exported phase difference; the reciprocal workbench matches three with
maximum phase difference 1.73e-6 rad. Default behavior remains native. Use
`Launch_Reciprocal_Diffraction.ps1` for the opt-in corrected workflow; unset
`RADIO_DIELECTRIC_PROFILE` to return to native behavior.

The workstation report and evidence live under
`outputs/differt-bridge/examples/dielectric3d_diffraction/`. The 60-second
`Sionna_vs_DiffeRT_Dielectric3D.mp4` and `Dielectric3D_Comparison.blend` show
native, corrected, crossed-dipole, second-material and shadow-boundary cases.
`Regenerate_Dielectric3D_Animation.ps1` renders, encodes, independently decodes
sample frames, and verifies the reopened relative-path Blender timeline.

Reproduction code is in `scripts/dielectric3d_*.py`,
`scripts/validate_dielectric3d_*.py`, `scripts/validate_dielectric_sqrt.py`,
`scripts/analyze_dielectric3d.py`, `scripts/render_dielectric3d_animation.py`
and `scripts/build_dielectric3d_report.py`. The report provides exact run
parameters, raw fields, failed coarse checks, current and historical source
hashes, profile installation receipts, and a checksummed evidence archive.

Finite edges, arbitrary 3D bodies, higher-order interactions, more low-loss
materials and independent external full-wave software or measurements remain
necessary before claiming general dielectric diffraction accuracy.

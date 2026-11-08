# Native 3D diffraction against an independent Maxwell reference

The 7 November 2026 campaign uses actual short electric point dipoles and
native CIR fields, including carrier phase. No line-source spreading closure
is used. The independent exact PEC wedge reference is the Sommerfeld/Carslaw
point Green function followed by the vector electric Hertz operator. It is
checked against independently synthesized Fourier-Bessel modes, PEC-plane
images, boundary conditions, real-frequency contour and derivative refinement,
reciprocity, and the differential Maxwell equations.

Two changes are deliberately separate:

* The installed **reciprocal** profile guards Sionna's opaque slab exponential
  against evaluating an irrelevant huge phase into NaN. Below exp(-80)
  attenuation its one-way and two-way factors are zeroed. Conductivity and
  geometry are unchanged. The default native profile is untouched.
* `hertz_pec3d.py` supplies a **separate optional 3D PEC Hertz-UTD field**.
  Differentiating the full uniform potential includes finite-distance vector
  terms while preserving transition cancellation. This is an asymptotic
  correction, not the independent Maxwell reference or an engine replacement.

The optional domain is a canonical infinite PEC right-angle wedge, a source
electric dipole parallel to its z edge, and x/y/z receiver dipoles, wavelength
1 m. Inputs are strictly guarded; changed/extra obstacles and dielectric
materials are rejected. Native geometry is retained; finite 80/160-wavelength
meshes approximate the infinite wedge with only its central edge active.
This is not a full-wave model of finite faces, vertices or arbitrary 3D objects.

The primary non-null correction errors span 0.011–0.766% complex RMS. Twelve
fresh holdouts span 0.035–0.326%. Every non-null group improves against both
reciprocal engine baselines. At one representative skew group: native Sionna
47.684%, native DiffeRT 19.950%, reciprocal profiles 9.131%, optional 3D field
0.326%. These are group RMS errors, not a worst-link bound. Null-channel
relative errors and phase are undefined and reported accordingly.

Those headline metrics concern the total field. A separate error budget
subtracts exact Maxwell GO images and excludes samples within 1e-4 rad of
transitions. Representative diffraction-only RMS errors change from 2.135%
to 0.920% (skew z/z ports), and 11.513% to 0.992% (skew z/y ports).
The native free-space fields agree with the analytical far-field formula
within 3.42e-6 RMS but omit finite-distance Maxwell terms. The report does
not attribute this free-space/GO contribution to diffraction itself.

The exact reference is independent of UTD and both engines. Its Fourier-Bessel
cross-check uses a small uniform absorption to avoid the branch-point
quadrature singularity; the actual campaign uses real vacuum wavenumber and
separate real-frequency numerical controls. Both reference implementations
are project code, not external third-party certification.

From the workspace root, `Compare_Native3D_Wedge.ps1` runs the two configured
runtimes and writes their CIR exports beside the shared optional correction.
It accepts `-Manifest` and `-Output`. It does not alter original ray outputs,
consume reference fields, or add a Blender panel. The existing Blender
workbench and `Launch_Reciprocal_Diffraction.ps1` continue to work.
`Regenerate_Native3D_Animation.ps1` redraws, encodes, decodes and reopens the
60-second film and relative-path Blender timeline.

Reproduction scripts, in execution order:

1. `native3d_cases.py`, `validate_maxwell3d_reference.py`, `run_dielectric.py`
   (four original profiles), `analyze_native3d.py`.
2. `probe_hertz_utd.py`, `native3d_holdout.py`, `validate_opaque_slab.py`
   (the last runs in Sionna Python with native profile).
3. `run_dielectric.py` for both updated profiles, holdouts, and the complete
   286-case dielectric regression. The historical pre-fix source is archived.
4. `finalize_native3d.py`, `compare_native3d.py`, relevant pytest suites.
5. `install_reciprocal_profile.py`, native and reciprocal Blender health checks.
6. `render_native3d_animation.py`, `model_error_video_blender.py`,
   `build_native3d_report.py`, `package_native3d_evidence.py`.

Set OPENBLAS_NUM_THREADS=1, use the workspace runtimes and the configured LLVM
library, and choose fresh output directories for new engine runs. Source guards
reject unsupported engine versions. See the archived receipts and manifests
for exact commands, profiles, source hashes and runtime versions. The original
pre-patch results must not be overwritten when reproducing a patched run.

Remaining scope: native **3D dielectric** wedge accuracy still needs an
independent coupled-vector reference. The 2D dielectric refinement and the new
3D PEC correction must not be used as evidence for that untested claim.

Primary sources:

* https://nvlpubs.nist.gov/nistpubs/jres/61/jresv61n5p343_A1b.pdf
* https://bura.brunel.ac.uk/handle/2438/3844

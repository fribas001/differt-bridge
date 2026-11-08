# Optional full-wave 2D wedge refinement

The new mode reduces the remaining canonical comparison error by solving the
coupled dielectric transmission problem, not by changing a native UTD coefficient.
Its results are separate **2D line-source total fields**. Native 3D ray paths,
coefficients, CIRs, source files and installed extensions remain unchanged.

On the new convergence-compatible port set, the reciprocal ray models retain
2.4–4.5% total-field complex RMS error. The 24-panel full-wave mode measures
0.018–0.050% against a separate FDFD Maxwell calculation. Ez and Hz boundary
controls measure 0.033% and 0.054%. These are tested-domain results, not a claim of
general 3D accuracy or an upstream engine improvement.

## Model and independent validation

`canonical_maxwell_refinement.py` uses the previously verified transmission BIE
implementation as a computational model. It now is the model under test, and
**is not used as its own accuracy reference**. Independent validation uses the
unchanged differential-operator solver `maxwell2d_reference.py`, at 40, 60 and
80 cells per wavelength, with Richardson estimates and two enlarged-PML checks.
The 26 new FDFD operator solves cover four materials, both polarizations, five
sources and 53 receiver positions. Ports are rounded to a common 0.05-wavelength
lattice so interpolation weights are consistent across the refinement sequence.

The maximum successive extrapolation change is 0.014%; this is an empirical
reference uncertainty indicator, not a rigorous per-channel bound. Prior
free-space and exact-PEC controls remain applicable because the FDFD source hash
is unchanged. BIE 16-to-24 panel changes remain below 0.063%.

Constant-panel collocation has a small reciprocity bias. The full-wave mode
evaluates both source/probe directions and takes their ordinary transpose average,
using Lorentz symmetry without conjugation. Raw forward and reverse fields and
their discrepancy are retained. Both raw fields are independently checked against
FDFD; no reference coefficient, angle fit or learned field enters the solver.

An uncoupled local-Fresnel physical-optics current model is also measured. It
improves some groups but regresses others and is not promoted. This diagnostic is
not a transcription of a published UAPO/EPO formula. The adopted full-wave solve
enforces coupled field/flux transmission conditions on both wedge faces.

## Use

From the workstation root, run `Compare_Maxwell_Wedge.ps1`. It invokes both
configured ray-tracer runtimes and writes their unmodified ray results plus
`refinement.json` and `comparison.json` to `work/canonical-maxwell-comparison`.
Use `-Manifest PATH -Output PATH` for another explicitly supported canonical case.
The script is not an automatic correction to arbitrary Blender scenes.

The report is `examples/maxwell_refinement/index.html`. The saved
`Maxwell_Refinement_Animation.blend` is a portable video timeline, not a simulation
scene. The existing paired diffraction simulation workbench and native/reciprocal
Blender launchers remain available. `Regenerate_Refinement_Animation.ps1` regenerates
the film from validated measured data; `-Previews` generates chapter stills and
`-VerifyOnly` decodes and reopens the timeline.

The full-wave mode rejects extra obstacles, altered triangles, skew or point-source
domains, arrays, finite slabs, cross polarization and multiple interactions before
any solve. It requires an explicit `maxwell_domain` declaration. No unsupported
obstacle is dropped and no unsupported scene is silently relabelled as refined.
Native 3D tracing remains the appropriate workflow for those scenes.

## Numerical reproduction

Set `OPENBLAS_NUM_THREADS=1` before starting Python. In the commands below `PY`
means `work/runtime/Scripts/python.exe` and `S` means
`work/github-update/differt-bridge/scripts`, relative to the workstation root.

```text
PY -B S/refinement_cases.py work/maxwell-refinement/cases.json
PY -B S/run_refinement_fdfd.py work/maxwell-refinement/fdfd --grids 40,60,80
PY -B S/run_refinement_fdfd.py work/maxwell-refinement/fdfd_pml --grids 60 --pml 2.5 --only holdout_low_Hz,holdout_high_Hz
PY -B S/canonical_maxwell_refinement.py work/maxwell-refinement/cases.json work/maxwell-refinement/final16.json --panels 16
PY -B S/canonical_maxwell_refinement.py work/maxwell-refinement/cases.json work/maxwell-refinement/final24.json --panels 24
PY -B S/probe_surface_currents.py work/maxwell-refinement/physical_optics.json
PY -B S/refinement_boundary_controls.py .
PY -B S/run_dielectric.py --differt-python work/runtime/Scripts/python.exe --sionna-python work/sionna-runtime/Scripts/python.exe --llvm-library "C:/Program Files/LLVM/bin/LLVM-C.dll" --output work/mre --profiles sionna-native,differt-native,sionna-reciprocal,differt-reciprocal --precision float32 --manifest work/maxwell-refinement/cases.json
PY -B S/analyze_refinement.py .
PY -B S/build_refinement_report.py .
```

FDFD drivers resume existing records. Use a fresh directory when forcing a new
solve after source changes. Raw records, source hashes, numerical tests, guard
tests, native/reciprocal workflow receipts and video checks are in the report's
evidence archive. No environments, caches or duplicate videos are bundled.

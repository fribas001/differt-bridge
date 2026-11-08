# Diffraction-model error against two Maxwell formulations

The 7 November 2026 addendum is delivered in
`examples/diffraction_model_errors/index.html`. It contains a new 60-second
side-by-side animation, raw numerical evidence and a portable Blender video
timeline. Existing simulation scenes, native runtimes and the optional reciprocal
profile are retained. No new electromagnetic runtime patch is installed.

The new boundary-integral reference independently corroborates the earlier FDFD
reference: dielectric control fields agree within 0.0071–0.0156% complex RMS.
The fresh angular sweep has 2,120 channels per engine/profile (8,480 comparisons).
Reciprocal profiles have 2.4–4.5% total-field RMS error; native profiles have
7.7–16.9%. The corrected engines agree within 0.00071% RMS with each other.
This agreement is not a Maxwell accuracy guarantee.

The remaining error decreases with electrical distance. An exact-plane reflection
control shows that part of the residual after subtracting ray GO is GO error;
the residual must not be described as pure diffraction error. Alternative
parameter-free Fresnel arguments help some new cases but regress on original
Maxwell controls, so they remain diagnostic candidates.

The comparison now uses a reciprocal cylindrical propagation closure,
`D * G(s+s') * sqrt((s+s')/(s*s'))`. It has the same high-frequency limit as the
old one-sided closure and the same coincident-ray Green function as GO. This
removes an artificial source/receiver asymmetry from the 2D comparison, not the
physical error in the 3D engine. Legacy metrics are retained. The new Sommerfeld
reference explicitly selects the decaying evanescent square-root branch.

## Reproduction on the configured workstation

Set `OPENBLAS_NUM_THREADS=1` before starting Python. The BIE requires NumPy/SciPy;
plots additionally require matplotlib and Pillow. Engine runs use the existing
version-guarded runtimes. From the workspace root, with `PY` denoting
`work/runtime/Scripts/python.exe` and `SCRIPTS` denoting
`work/github-update/differt-bridge/scripts`:

```text
PY -B SCRIPTS/run_model_error_reference.py work/diffraction-model-errors/bem_controls --campaign controls --panels 24,48
PY -B SCRIPTS/run_model_error_reference.py work/diffraction-model-errors/bem_sweep --campaign sweep --panels 16,24,36
PY -B SCRIPTS/run_model_error_reference.py work/diffraction-model-errors/bem_distance --campaign distance --panels 16,24
PY -B SCRIPTS/model_error_controls.py work/diffraction-model-errors/bem_extra
PY -B SCRIPTS/run_dielectric.py --differt-python work/runtime/Scripts/python.exe --sionna-python work/sionna-runtime/Scripts/python.exe --llvm-library "C:/Program Files/LLVM/bin/LLVM-C.dll" --output work/mer --profiles sionna-native,differt-native,sionna-reciprocal,differt-reciprocal --precision float32 --manifest work/diffraction-model-errors/sweep_cases.json
PY -B SCRIPTS/analyze_model_errors.py .
PY -B SCRIPTS/probe_halfspace.py .
PY -B SCRIPTS/build_model_error_report.py .
```

The reference driver resumes existing files; choose a fresh destination for a
fresh solve after source changes. Source hashes are embedded in every reference
record. The analysis uses the measured 36-panel sweep, not an extrapolated or
fitted target. The older FDFD analysis and policy probes are included in evidence.
`Regenerate_Maxwell_Animation.ps1` redraws and encodes measured results; it does
not rerun physics. Use `-Previews` for six chapter stills, or `-VerifyOnly` to decode
and reopen the saved timeline. File hashes must be regenerated when changing
delivered content; `package_model_error_evidence.py WORKSPACE` performs that step.

Run `pytest tests/test_model_error_reference.py tests/test_dielectric_model.py` in
the research checkout with writable TEMP/TMP. The analytic tests check PEC image
reflection, zero-contrast air, Sommerfeld reciprocity, BIE air/PEC controls,
reciprocal normalization, boundary half-jumps and the high-frequency limit.

## Limits

This reference covers a solid homogeneous lossy right-angle wedge at broadside.
The BIE, FDFD and exact PEC/free-space controls use separate formulations, but
are project implementations, not external certification. Convergence changes
are empirical indicators, not rigorous per-channel error bounds. The 5-degree
angular sweep does not replace the preceding exact-boundary and obstacle tests.
Thin slabs, arbitrary skew 3D incidence, multiple-edge material interactions and
geometry gradients remain outside the independent Maxwell validation.

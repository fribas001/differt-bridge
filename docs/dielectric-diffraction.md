# Dielectric diffraction investigation

The November 3, 2026 addendum isolates reciprocity, reflection/incident boundaries,
polarization transport and face enumeration on matched geometry. It extends the
[previous diffraction findings](diffraction.md); it does not install a physics patch.

## Measured results

The configured Windows CPU runtimes are DiffeRT 0.12.0 and Sionna RT 2.1.0.
There are 286 fixtures per profile, six profiles (1,716 executions), and 52 extra
executions using the existing DiffeRT float64 field profile. All nine worker
processes exited successfully. A boundary fixture contains eleven receivers.
These counts are fixture executions, not independent scenes or accuracy successes.

| Diagnostic | Sionna native | DiffeRT native |
| --- | ---: | ---: |
| Largest sampled dielectric TX/RX reversal gain gap | 29.754 dB | 13.670 dB |
| Eligible boundary checks within 1% at ±0.001 degrees | 14/50 | 14/50 |
| Largest gain change after face triangle blocks are reordered | 0 dB | 11.762 dB |

The strongest Sionna reciprocity example uses a 1 mm slab. The strongest DiffeRT
example uses a 1 m slab. These are maxima over this sample, not universal bounds.
Null channels are excluded from gain and phase ratios. Native means native field
formulas in the existing configured runtime; it does not mean an unmodified
upstream installation. Float32 field computation and complex128 export storage
are recorded separately. Float64 controls retain the same physical geometry.
They also retain the existing float32-rounded common scalar operands (wavelength,
angular frequency and vacuum-permittivity operand). The independent formula
transcription uses unrounded physical constants and reproduces the large gaps.

The findings are:

- DiffeRT's native dielectric Fresnel weights/signs disagree with its specular
  reflection at broadside. The PEC limit masks the issue. An isolated swap/sign
  correction raises the boundary pass count to 34/50 but can worsen reciprocity.
- DiffeRT's diagonal edge matrix cannot supply the cross-polarized reflection
  jump at skew incidence. Scalar material-angle changes cannot repair it.
- Sionna's existing isolated KP assembly/distance candidate passes all 50 sampled
  boundary checks, but its dielectric reciprocity gap still reaches 17.931 dB.
- Incident/outgoing angle heuristics explain reciprocity failures. DiffeRT also
  assigns these angles according to face labels, causing a physical coefficient
  change when unchanged triangles are enumerated in a different order.
- A symmetric-cosine hypothesis reaches a 6.41e-14 reciprocity residual in the
  float64 controls but still fails skew boundary checks. Reciprocity imposed by
  averaging forward/reverse coefficients is a constraint, not accuracy evidence.
- A separate GO-presence audit passes 580/580 receiver checks per DiffeRT profile.
  Both Sionna profiles fail the same 40 checks at +0.0001 degrees: 20 extra
  reflection0 rays and 20 missing valid reflectionn rays. The original prose
  incorrectly described all 40 as extra rays; the raw expected/observed flags
  were correct. See [the correction addendum](dielectric-corrections.md) for
  full-mesh reconstruction and independent Maxwell validation.

All 24 obstacle controls pass, including an obstruction 1 mm from the edge.
All 1,120 non-air candidate/native comparisons preserve exact physical path
records and delays. Two Sionna air-material cases gain diffracted paths under the
candidate, revealing the opaque heuristic's incomplete zero-contrast limit.

The NumPy/SciPy model is a transcription used to explain the implementations.
It is not an independent dielectric accuracy reference. No candidate is approved
for installation. Independent impedance-wedge or converged full-wave results
for a specified common boundary-value problem are still required.

The four new analytic tests pass. The broader configured-runtime suite has
260 passes and two failures: unchanged free-space amplitude assertions expect
an unrounded wavelength to 1e-10 relative tolerance, while this workstation's
intentional common-scalar policy produces a 7.67e-8 relative wavelength offset.
Both assertions pass in an isolated diagnostic using unrounded constants.
No installed policy or test tolerance was changed; the original failures remain
in the evidence logs.

## Reproduction

Use separate engine environments configured as described in [installation](install.md).
The analysis environment additionally needs `requirements-analysis.txt`.

```powershell
python scripts/run_dielectric.py --differt-python PATH_TO_DIFFERT_PYTHON --sionna-python PATH_TO_SIONNA_PYTHON --llvm-library PATH_TO_LLVM_DLL --output runs/dielectric
python scripts/analyze_dielectric.py runs/dielectric runs/dielectric/analysis.json
python scripts/audit_dielectric_boundaries.py runs/dielectric runs/dielectric/boundary_geometry.json
python -m pytest tests/test_dielectric_model.py
```

The default runs only the two native formulas with the runtime's default field
precision. For the measured six-profile investigation, explicitly select:

```text
--precision float32 --profiles differt-native,sionna-native,differt-polarization,sionna-kp_depth,differt-incident,differt-symmetric_cosine
```

Explicit float32/float64 modes require the existing research precision hook.
Stock DiffeRT should use `--precision native`; the script fails clearly if an
explicit policy is unavailable. Experimental coefficients are replaced only
within their child process. Installed files, visibility and search are unchanged.

Use `--only` with a comma-separated list of names from the archived `cases.json`
to repeat a subset. The evidence archive contains the exact manifests for the
main study and both float64 subsets, raw coefficients, input hashes, successful
process receipts, source snapshots and analysis. Preserve the distinction between
nominal exact-boundary samples and measured one-sided limits.

## Context

[Tami et al. (2018)](https://onlinelibrary.wiley.com/doi/10.1155/2018/3029152)
discuss reciprocity limitations of lossy-wedge heuristics and canonical references.
The diagnostic symmetric-cosine construction here is not one of their named models.
The related [Sionna coefficient issue](https://github.com/NVlabs/sionna-rt/issues/85)
does not imply acceptance of these local candidates.

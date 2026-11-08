# Diffraction findings

The [dielectric follow-up](dielectric-diffraction.md) extends this baseline with
1,768 completed fixture executions focused on reciprocity, skew polarization,
boundary behavior and face enumeration. The earlier numbers below remain the
historical sample; no experimental field correction is installed.

The [field-diagnostics archive](https://github.com/fribas001/differt-bridge/releases/download/v0.6.3/diffraction-reports.zip) contains the measured report, figures and numerical evidence. The [side-by-side video](https://github.com/fribas001/differt-bridge/releases/download/v0.6.3/Sionna_vs_DiffeRT_Diffraction.mp4) shows the installed native-field baseline, not the experimental corrections.

## Findings

- Native DiffeRT passes all 40 tested nonzero signed PEC-limit checks. The installed Sionna assembly does not; the isolated assembly correction passes all 40.
- Sionna's native reflection-boundary coefficient approaches the wrong cancellation sign in the tested PEC cases. The candidate corrects it without changing path geometry.
- An additional Sionna distance-accumulation correction removes a 1.295 dB dependence on unused maximum depth for a fixed diffraction→reflection route.
- Dielectric reciprocity remains unresolved in both models. In the sampled concrete cases, maximum gain mismatch under TX/RX reversal is about 11.76 dB for DiffeRT and 11.65 dB for the Sionna assembly candidate.
- At the sampled concrete H-polarized reflection boundary, DiffeRT's normalized jump is approximately `1.29541 + 0.00823j`, while continuity requires a limiting value of `+1`. The candidate gives `0.999877 - 0.000111j` at the same finite receiver offset.

These are sampled cases and model-specific checks, not universal error bounds. The independent PEC reference is an asymptotic straight-edge theory, not a full-wave solution for a finite dielectric scene. Near-zero reference channels use absolute error; their phase is undefined.

The numerical decomposition reproduces the original concrete gain/phase gaps from different angular-term assembly, polarization weighting and material incidence-angle choices. More export rounding or forcing the engines to agree does not resolve these physical-model differences.

## Experimental code

`scripts/diffraction_physics_worker.py` can replace the relevant Sionna methods **inside one diagnostic process**. The default run is native. The `kp_assembly` and `kp_depth` profiles are not installed, imported by Blender, or silently selected by the bridge. `scripts/run_diffraction.py` requires an explicit `--experimental-sionna` option and retains the native baseline.

The proposed Sionna corrections correspond to open upstream [#84](https://github.com/NVlabs/sionna-rt/issues/84), [#85](https://github.com/NVlabs/sionna-rt/issues/85) and [#87](https://github.com/NVlabs/sionna-rt/issues/87), independently reproduced on the local stack. Upstream acceptance is not implied. The runtime LLVM adapter is a different change and does not alter these field formulas.

The next physics target is a specified reciprocal lossy-wedge model tested against an independent canonical or full-wave reference, including skew polarization and both reflection boundaries. Material heuristics can violate reciprocity; see [Tami et al. (2018)](https://onlinelibrary.wiley.com/doi/10.1155/2018/3029152). The PEC reference follows [Kouyoumjian and Pathak (1974)](https://ntrs.nasa.gov/citations/19750029381).

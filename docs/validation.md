# Validation and release scope

The source in this repository is the 0.6.3 bridge. The public package uses a clean, unmodified upstream DiffeRT environment. Installation and source/package checks are recorded in `release-verification.json` alongside the release assets.

## Workstation evidence

| Study | Measured result | Scope |
| --- | --- | --- |
| Native batch runtime repair | 306 pre-install Sionna stress executions; 408 installed Sionna plus 102 DiffeRT executions | Exact tested Windows CPU compiler/runtime binaries; solver physics unchanged |
| Diffraction field diagnostics | 496 requests, 486 numerical completions, 10 configured candidate-budget rejections | Four profiles, 108 main and 16 depth fixtures; repeats are disclosed |
| PEC-limit reference | Native DiffeRT and each Sionna candidate pass 40/40 nonzero signed checks at 0.1% tolerance | Finite conductivity approaching PEC; independent KP asymptotic reference, not a full-wave measurement |
| Sionna assembly candidate | Maximum relative complex error 8.39e-6; native DiffeRT 2.24e-5 | Candidates run in isolated processes; not installed |
| Depth dependence | Native Sionna changes a fixed diffraction→reflection route by about −1.295 dB; combined candidate has zero change in 24 comparisons | DiffeRT depth 2→3 unchanged; deeper searches hit configured limits |
| Obstacle preservation | 12 clear/blocked controls pass; candidate routes/delays unchanged in 216 case comparisons after path-slot matching | No obstacle removal or larger visibility tolerance |
| Existing paired Blender control | 1,299 matched paths; zero exported phase difference | Workstation's opt-in shared LoS/specular research profile, not the clean native default |

The [diffraction report](diffraction.md) records remaining dielectric discrepancies. Original reports and media remain historical observations; changes to package metadata do not turn them into measurements of a new native dependency build.

## Fresh installation

The November 3 publication check passed 258 DiffeRT bridge tests, 45 inherited portable tests, report JavaScript checks, and the Linux GitHub CI job. A fresh public clone rebuilt the exact extension ZIP tested in Blender 5.2.3. The extracted ZIP passed the full workflow below and four paired scenes: free space, ground reflection, blocked LoS and receiver motion.

Both clean runtimes completed seven pilot fixtures. The extended run completed 322 of 324 requested executions across native DiffeRT, native Sionna and the isolated Sionna `kp_depth` candidate. Two DiffeRT depth-5 searches reached the configured candidate limit. Native DiffeRT used complex128 coefficients, while Sionna used complex64. DiffeRT and the candidate each passed 40/40 nonzero signed PEC checks; native Sionna passed 0/40. Maximum relative complex errors were respectively `1.83679e-5`, `8.39323e-6` and `7.67029`. These fresh measurements are separate from the historical table above.

The optional CPU adapter rebuilt to its exact expected binary hash, ran both Sionna profiles in the new environment, and restored the original Dr.Jit initializer byte-for-byte afterward. `fresh-install-evidence.zip` and `release-verification.json` in the release contain the generated measurements, actual dtypes, dependency versions and checksums.

Release verification uses a new Python environment with `include-system-site-packages = false`, package installation from the pinned requirements, tests in the staged source checkout, deterministic ZIP rebuilding, and Blender background registration/workflow checks with factory startup. The user's saved Blender preferences and existing two runtimes are not modified.

Run the commands in the root README. `scripts/blender_workflow_check.py` exercises public run operators, paths, 2D/3D coverage, HDF5, arrays, motion, cancellation and save/reopen:

```powershell
blender --background --factory-startup --python-exit-code 1 --python scripts/blender_workflow_check.py -- C:/temp/differt-check C:/path/to/differt/python.exe
```

Inspect actual process exits and receipts. Zero physical paths are valid measurements; failed workers or budget rejections are not zero-gain observations.

## Limits

No universal ray-tracer equivalence, GPU parity, full-wave accuracy, dielectric reciprocity or end-to-end geometry differentiation is established. Source/runtime hashes and configuration belong with any reported comparison. Historical artifacts are distributed as release assets, with local path strings redacted and original/redistributed checksums distinguished.

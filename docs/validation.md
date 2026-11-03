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

Release verification uses a new Python environment with `include-system-site-packages = false`, package installation from the pinned requirements, tests in the staged source checkout, deterministic ZIP rebuilding, and Blender background registration/workflow checks with factory startup. The user's saved Blender preferences and existing two runtimes are not modified.

Run the commands in the root README. `scripts/blender_workflow_check.py` exercises public run operators, paths, 2D/3D coverage, HDF5, arrays, motion, cancellation and save/reopen:

```powershell
blender --background --factory-startup --python-exit-code 1 --python scripts/blender_workflow_check.py -- C:/temp/differt-check C:/path/to/differt/python.exe
```

Inspect actual process exits and receipts. Zero physical paths are valid measurements; failed workers or budget rejections are not zero-gain observations.

## Limits

No universal ray-tracer equivalence, GPU parity, full-wave accuracy, dielectric reciprocity or end-to-end geometry differentiation is established. Source/runtime hashes and configuration belong with any reported comparison. Historical artifacts are distributed as release assets, with local path strings redacted and original/redistributed checksums distinguished.

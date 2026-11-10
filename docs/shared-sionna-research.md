# Reciprocal and phase-alignment workflows on RT 2.2

This is the research extension of the [native migration](shared-sionna-runtime.md).
It uses the pinned Windows x64 CPU environment and its verified LLVM bootstrap.
The adapters live in this project and change methods only in the worker process.
Shared packages, both old environments, installed Blender extensions, original
scenes, reference datasets and historical reports remain unchanged.

## Run from the validated workstation

From the `bas` workspace in PowerShell:

The launcher sources are included in
[workstation/launchers](../workstation/launchers/README.md); the current workspace
already has them installed at its root.

```powershell
.\Launch_Phase_Alignment.ps1
.\Launch_Reciprocal_Diffraction.ps1
.\Check_Research_RT22.ps1 -RunComparison
```

The equivalent selectors are `Launch_Workflow.ps1 -Profile phase` and
`Launch_Diffraction.ps1 -DielectricProfile reciprocal`. Ordinary
`Launch_Workflow.ps1` and `Launch_Diffraction.ps1` still select native RT 2.2.
Use separate Blender sessions for different profiles. Settings are session-only;
opening a saved scene directly does not install the bootstrap integration.

Both engines remain external workers. DiffeRT and Maxwell use `work/runtime`.
Blender 5.2 keeps its bundled Python for the UI. Shared RT is never imported
into Blender Python, and its packages are never added to Blender's search path.

For a research script, run from this repository or its intended working directory:

```powershell
$rt = Join-Path $env:USERPROFILE 'Documents/Codex/shared-envs/sionna-rt-2.2-py312'
& "$rt\Scripts\python.exe" -I -B -m codex_sionna_runtime --check
& "$rt\Scripts\python.exe" -I -B -m codex_sionna_runtime .\scripts\rt22_research_worker.py --profile phase -- .\your_script.py
& "$rt\Scripts\python.exe" -I -B -m codex_sionna_runtime .\scripts\rt22_research_worker.py --profile reciprocal -- .\your_script.py
```

Append normal arguments. Replace the final script with `-m your_package.module`
for modules. Add `--receipt .\runs\profile.json` before `--` to retain the
source/version receipt. Research RT child processes also require this wrapper,
using `sys.executable` when they should inherit the same interpreter. The
`shared_sionna.command` helper constructs the invocation; paired runners and the
Blender integration already use it. It preserves arguments and working directories
and removes inherited old LLVM adapters and Python package paths.

The bootstrap initializes first. The research installer verifies pinned versions,
native source hashes and payload hashes before applying the selected profile.
Repeated installation of the same profile is idempotent; changing profiles in a
live process fails. An incompatible source or environment fails explicitly.
No package install, editable install, package-file mutation or second LLVM adapter
is required. The existing RT 2.1 version and source guards are unchanged.

For a notebook, choose the shared interpreter, call
`configure_verified_runtime()` before any Mitsuba/RT import, add this repository's
`scripts` directory to `sys.path`, then call `rt22_profiles.install('phase')` or
`rt22_profiles.install('reciprocal')` before creating scenes/solvers. Restart the
kernel to select another profile. No existing notebooks were rewritten.

## Paired reciprocal exports and Maxwell companions

From `bas`, select a **new** output directory:

```powershell
.\Run_Reciprocal_Rays.ps1 -Manifest .\work\dielectric-corrections\final\cases.json -Output .\work\my-rt22-reciprocal
.\Compare_Maxwell_Wedge.ps1 -Output .\work\my-rt22-maxwell2d
.\Compare_Native3D_Wedge.ps1 -Output .\work\my-rt22-pec3d
.\Compare_Dielectric3D_Wedge.ps1 -Output .\work\my-rt22-dielectric3d
```

The comparison launchers export fresh Sionna/DiffeRT reciprocal rays, verify
their manifests and hashes, then pass them through `--reuse-rays` to the unchanged
Maxwell companion programs. Maxwell computations stay in their original runtime.
Ray fields and full-wave companion fields remain separate products. The shared
route rejects existing output directories; its new defaults have an `rt22` suffix.
Explicit `-Manifest`, panel, accuracy and checkpoint options retain their meanings.
For reproducibility audits, copy checkpoints to a fresh folder first: the existing
Maxwell solver updates its checkpoint receipt when reusing modes.

The lower-level `run_dielectric.py` also accepts the shared interpreter with
`--profiles sionna-reciprocal,differt-reciprocal --precision float32`. Omit
`--llvm-library` for shared RT. Direct calls to the three historical Python
companion entry points without `--reuse-rays` retain their original RT 2.1 route.
Use the PowerShell entry points above for the migrated workflow.

## What was adapted

RT 2.2 refactored field transport and normalization into separate steps. Although
the equations are equivalent, the float32 operation order affects small phases.
The reviewed `historical_fields.py` payload preserves the three RT 2.1 field
methods' arithmetic on RT 2.2 data structures. Its upstream license, provenance
and original source hash are included. Both research profiles use that arithmetic;
native RT 2.2 remains available without those methods.

The phase profile retains native RT 2.2 candidate discovery and adds the existing
unshifted float64 reconstruction and complete-mesh segment visibility checks.
Only preliminary length gates are opened; final validation still requires the
inclusive 1 mm minimum. Valid corner paths survive and real obstacles remain
blocking. The reciprocal profile ports the existing guarded material, geometry,
depth and boundary corrections without modifying their original installer.

## Numerical acceptance

See the [portable receipt](../validation/shared-sionna-2.2-research.json).
Complete local logs, source diffs and comparisons are in `work/migrate-research22`;
fresh calculation directories use `work/r22-*`. Existing data was never overwritten.

| Comparison | Result |
| --- | --- |
| Fresh RT 2.1 vs RT 2.2 phase workbench | 1,299 identical physical routes and vertices; gain, delay, phase and Doppler export differences all zero |
| Sionna vs DiffeRT phase workbench | Zero exported phase difference for all 1,299 matched paths in both runtime runs |
| Fresh RT 2.1 vs RT 2.2 reciprocal campaign | 286/286 cases pass; complex coefficients/CIR, points and delays exactly equal after physical-route matching |
| RT 2.2 vs archived Maxwell-linked holdout | 72/72 pass; coefficients/CIR, points and delays exactly equal |
| RT 2.2 vs archived main reciprocal campaign | 280/286 pass the unchanged migration limits; six differences also reproduce on retained RT 2.1 |
| Geometry safety | Both valid corner fixtures retained; all 72 near-surface obstacle probes rejected; inclusive 1 mm boundary checked with deterministic and stochastic discovery |

Limits are unchanged from native migration: point error <= 1e-5 m, delay error
<= 1e-13 s, complex-field error <= 2e-10 + 1e-5 times baseline magnitude,
and phase error <= 1e-4 rad above the 1e-9 coefficient floor. Route matching uses
receiver, interactions and vertices; internal path storage order can differ.
Units, input mesh hashes, material parameters, array shapes and path counts are
checked. Tiny phase values around 1e-16 rad in early audit files are division
roundoff when comparing identical complex values; the portable comparator now
records zero for exactly equal values.

The six archived discrepancies are retained in the receipt:

- `boundary_concrete_skew_incident_VH` and `..._HV`;
- `boundary_concrete_28GHz_reflection0_VV` and `...reflectionn_VV`;
- `boundary_concrete_28GHz_reflection0_HH` and `...reflectionn_HH`.

Across the archived 286 cases, the largest absolute field difference is
1.1927e-9, and the largest assessed phase difference is 2.05495e-4 rad. The largest
relative error is 8.06% at a near-null coefficient; it must not be interpreted as
the error of a strong received field. Fresh RT 2.1 and RT 2.2 agree exactly in
all these cases. This establishes that the six archived replay discrepancies
are not introduced by this migration; their historical cause remains unresolved.
No tolerance was loosened and no archived reference was replaced.

The final receipt also records actual Blender Runtime Test/paired runs, the
30-case 3D PEC, 40-case 2D Maxwell and 54-case dielectric companion entry points,
native workflow regression checks and protected-file verification. These tests
validate execution and numerical preservation. They do not claim to reduce the
previously reported Maxwell model or discretization errors.

All three Maxwell companion outputs match their archived fields exactly. The
3D PEC and dielectric ray comparisons also match exactly. The 2D conversion of
Sionna ray fields differs by at most 5.9844e-9 in complex magnitude, 2.1401e-7
relative and 1.6988e-7 rad in phase, within the unchanged limits. DiffeRT's
archived 2D values match exactly. There were 47 distinct passing focused tests;
source/package/documentation checks passed. The repeated native paths, motion,
coverage, HDF5 and Geometry Nodes checks passed. All 12,264 protected source,
binary, environment and reference-data hashes remained unchanged.

To compare saved reciprocal campaigns using the same acceptance rules:

```powershell
# From bas; OLD.json and NEW.json are complete engine campaign outputs.
& .\work\runtime\Scripts\python.exe -B .\work\github-update\differt-bridge\scripts\compare_rt22_results.py OLD.json NEW.json .\work\comparison.json
```

A failing comparison returns nonzero and preserves the failed rows. Compare both
an archived baseline and a fresh retained-runtime baseline when investigating
historical replay differences. Never replace the former with the latter silently.

## Scope, rollback and retained environments

Phase alignment is validated for CPU LoS/specular path fields only; it rejects
diffraction, refraction and diffuse reflection. Reciprocal research rejects RT 2.2
source exclusion boxes. Research coverage, differentiability/gradients, GPU/CUDA,
PHY/SYS and arbitrary 3D Maxwell equivalence are not certified by these tests.
Use the native profile for ordinary coverage and the prior guarded domains for
Maxwell companions. No missing dependency was installed in shared RT.

Close the shared Blender session and run:

```powershell
.\Launch_Phase_Alignment.ps1 -Legacy
.\Launch_Reciprocal_Diffraction.ps1 -Legacy
.\Compare_Maxwell_Wedge.ps1 -Legacy -Output .\work\my-legacy-maxwell
.\Compare_Native3D_Wedge.ps1 -Legacy -Output .\work\my-legacy-pec
.\Compare_Dielectric3D_Wedge.ps1 -Legacy -Output .\work\my-legacy-dielectric
```

CLI rollback uses `work/sionna-runtime/Scripts/python.exe` and its original LLVM
setting. No shared-package rollback is necessary. The original launchers were
also copied to `work/migrate-research22/launchers-before` before editing.

`work/sionna-runtime` is 445,876,118 bytes (425.22 MiB). It remains the historical
replay/KP-experiment and reproduction fallback; deletion is not approved.
`work/runtime` is 645,085,810 bytes (615.20 MiB) and remains required for DiffeRT
and Maxwell. Neither is a safe deletion candidate for this workflow today.
Historical animation commands and the unfinished offline reproduction package
retain their original provenance and were not regenerated or relabelled here.

## Changed entry points and files

- Workspace launchers: `Launch_Shared_RT.ps1`, `Launch_Workflow.ps1`,
  `Launch_Diffraction.ps1`, `Launch_Reciprocal_Diffraction.ps1`, the three
  `Compare_*_Wedge.ps1` files, and new `Launch_Phase_Alignment.ps1`,
  `Run_Reciprocal_Rays.ps1`, `Check_Research_RT22.ps1`.
- Runtime code: `scripts/rt22_profiles/` (guarded payload, manifest, license and
  provenance), `rt22_research_worker.py`, `shared_sionna.py`, `run_dielectric.py`,
  `blender_shared_runtime.py`.
- Verification: `blender_research_check.py`, `check_rt22_profile.py`,
  `check_research_workflow.py`, `compare_rt22_results.py`,
  `tests/test_shared_sionna.py`, `tests/test_rt22_comparison.py`, and the new
  `validation/shared-sionna-2.2-research.json` receipt.
- Instructions: both workspace/repository `AGENTS.md` files, `RUNNING_SHARED_RT.txt`,
  `PROJECT.txt`, README, CONTRIBUTING and the shared-runtime/install/index docs.

The original reciprocal and Maxwell scientific kernels were not edited.

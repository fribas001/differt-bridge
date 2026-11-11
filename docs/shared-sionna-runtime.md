# Shared Sionna RT 2.2 migration

> **RT 2.1 retirement update:** the former `-Legacy` routes below are historical.
> Current launchers reject them; recover the old runtime through the verified
> offline kit. See [retirement and recovery](rt21-retirement.md). The migration
> measurements below remain the original evidence.

Validated workstation profile: Windows x64, Python 3.12.10, CPU
`llvm_ad_mono_polarized`, Sionna RT 2.2.0, Mitsuba 3.9.1, Dr.Jit 1.5.0,
NumPy 2.5.4, SciPy 1.18.1 and h5py 3.16.0. This is a venv, not Conda.
The shared root's `README.txt`, `requirements-lock.txt` and
`environment-manifest.json` define its pinned installation.

## Run on the validated workstation

From the `bas` workspace, `Launch_Workflow.ps1` opens the native float32
comparison workbench and `Launch_Diffraction.ps1` opens the diffraction
workbench with shared Sionna. DiffeRT retains `work/runtime`.

Version-controlled copies of the workspace PowerShell entry points are in
[workstation/launchers](../workstation/launchers/README.md). They must be copied
to an existing workspace root with the documented layout before use; they do
not install runtimes or download the historical datasets.

```powershell
.\Launch_Workflow.ps1
.\Launch_Diffraction.ps1
.\Launch_Phase_Alignment.ps1
.\Launch_Reciprocal_Diffraction.ps1
.\Check_Workflow.ps1 -RunComparison
.\Check_Research_RT22.ps1 -RunComparison
```

These project launchers configure the current Blender session and subsequent
scene loads. They do not save preferences, overwrite .blend files or edit the
installed add-ons. Always enter through the launcher: double-clicking an old
.blend file retains its historical runtime settings. Saving a scene yourself
will save the selected external interpreter, but future sessions still need
the launcher to supply the bootstrap integration.

Blender stays on its bundled Python for its UI. Simulation workers run in the
external shared Python. The integration wraps only the Sionna add-on's
subprocess interface, including paths, 2D/3D coverage, exports and Runtime Test.
It clears inherited `PYTHONPATH`, `PYTHONHOME` and `DRJIT_LIBLLVM_PATH` for those
children. The shared helper initializes and verifies its own adapter once per
process before Mitsuba/RT imports. No global PATH, LLVM or packages change.

Direct scripts, from the repository or other appropriate working directory:

```powershell
$rt = Join-Path $env:USERPROFILE 'Documents/Codex/shared-envs/sionna-rt-2.2-py312'
& "$rt\Scripts\python.exe" -I -B -m codex_sionna_runtime --check
& "$rt\Scripts\python.exe" -I -B -m codex_sionna_runtime .\your_script.py
& "$rt\Scripts\python.exe" -I -B -m codex_sionna_runtime -m your_package.module
```

Append normal arguments. When a shared process starts another RT process, use
`sys.executable` with `-I -B -m codex_sionna_runtime` again; bootstrap state is
not inherited across processes. Do not run RT using Blender's interpreter or
add the shared site-packages to Blender's `sys.path`.

The existing `run_dielectric.py` and `run_diffraction.py` automatically wrap
children when `--sionna-python` points at the shared helper installation. Their
legacy and Linux interpreter paths remain supported. For example, from `bas`:

```powershell
$rt = Join-Path $env:USERPROFILE 'Documents/Codex/shared-envs/sionna-rt-2.2-py312'
& .\work\runtime\Scripts\python.exe -B .\work\github-update\differt-bridge\scripts\run_diffraction.py `
  --differt-python .\work\runtime\Scripts\python.exe `
  --sionna-python "$rt\Scripts\python.exe" `
  --output .\work\rt22-new-comparison --only wedge_v,wedge_h,reflection_diffraction
```

Omit `--llvm-library` for the shared environment; its bootstrap owns LLVM.
Use a fresh output directory to preserve prior results. The orchestrator can
run on the DiffeRT interpreter, while each engine retains its own dependencies.
The optional process variable `SIONNA_SHARED_PYTHON` selects an independently
provisioned equivalent helper environment for the portable Blender scripts.

No active project notebooks or editor interpreter settings were found.
Notebooks in the separate upstream reference checkout were not changed.
For a new notebook, select the exact shared interpreter and run this first:

```python
from codex_sionna_runtime import configure_verified_runtime
mi, rt = configure_verified_runtime()
```

## Scientific scope and retained workflows

The initial native migration and the subsequent research-profile migration have
separate receipts. Historical reports retain their original runtime provenance.
See [research-profile migration](shared-sionna-research.md) for the source audit,
numerical replay results, limits and exact research commands.

| Workflow | Interpreter / status |
| --- | --- |
| Native paths, coverage, motion, HDF5 and Geometry Nodes | Shared RT 2.2 via bootstrap |
| Phase-aligned LoS/specular paths, full-mesh visibility, shared 1 mm policy | Shared RT 2.2, explicit process-local `phase` profile |
| Reciprocal dielectric paths and boundary corrections | Shared RT 2.2, explicit process-local `reciprocal` profile |
| DiffeRT and precision/arithmetic profiles | Existing `work/runtime` retained |
| Maxwell BIE/FEM and reference refinement | Existing `work/runtime` retained; NumPy 2.5.2 / SciPy 1.18.0 |
| Original RT 2.1 runs and KP experiments | Offline RT 2.1 recovery kit; legacy workspace launchers retired |
| Full Sionna PHY/SYS, TensorFlow or CUDA | Not supplied or validated by this shared CPU profile |

The RT 2.2 research installer checks exact source and payload hashes, then attaches
reviewed methods in the worker process. It never edits shared packages or relaxes
the old RT 2.1 installer. Research profiles preserve historical field operation
order. Switching profiles requires a new process. Coverage uses the native profile;
the research acceptance evidence covers path fields, not a corrected coverage model.

The three `Compare_*_Wedge.ps1` launchers now generate fresh reciprocal rays using
shared RT 2.2 and existing DiffeRT, then pass those exports to unchanged Maxwell
companion programs. `-Legacy` is retired; deliberate historical replay uses the
RT 2.1 recovery kit. Render-only animation commands retain their recorded inputs
and the DiffeRT runtime.

DiffeRT 0.12.0, JAX/JAXlib 0.12.0.1 and Warp 1.18.0 are not supplied by the
shared RT environment. pytest 9.2.0 is also absent there; development tests use
the separate development/DiffeRT environment. No dependency installation is
needed for the migrated native and research RT workflows.

Sionna 2.2's [release notes](https://github.com/NVlabs/sionna-rt/releases/tag/v2.2.0)
document a diffraction-point precision fix and API changes to scene removal
and radio material object bookkeeping. The tested project calls remain
compatible. Native-library implementations and package versions also differ,
so numerical agreement is checked with stated tolerances, not byte equality.

## Validation and rollback

See [migration measurements](../validation/shared-sionna-2.2.json). Full local
logs, inputs and before/after fields are under `work/migration-rt22` in `bas`.
The portable tests target clean upstream DiffeRT; the workstation's patched
float32 environment already failed three strict tests before this migration.
Those tolerances and scientific code were not changed.

The fresh 12-fixture diffraction comparison preserved path counts, array shapes,
delays and obstacle rejection. Maximum point displacement was 3.8147 micrometres;
maximum relative complex-field difference was 2.4605e-7 and maximum phase
difference was 4.6465e-8 radians. Limits were 1e-5 m, 1e-13 s, field relative
1e-5 plus absolute 2e-10, and 1e-4 radians. Phase was checked only above the
declared 1e-9 coefficient floor.

Four Blender paired cases passed the existing 0.001 per-metric tolerances,
including analytic Friis, delay, blocked-path and Doppler controls. Both engines
ran as external workers. A separate paths + 2D coverage + 3D coverage batch
passed with HDF5 and Geometry Nodes; 47 retained HDF5 datasets matched shapes
and dtypes, with the metres/Z-up coordinate declaration preserved in metadata.
Numeric values passed relative 1e-5 and absolute 1e-12
(0.001 for dB datasets). A fresh 64-panel Maxwell BIE mode exactly matched its
checkpoint, with linear residual 1.4514e-15. Seventeen focused tests and the
source/package/documentation checks passed. A 12,264-file protected hash check
passed, and the session launcher preserved both original .blend files tested.

Files updated in the workspace: `Launch_Workflow.ps1`, `Launch_Diffraction.ps1`,
`Check_Workflow.ps1`, `PROJECT.txt`; new `Launch_Shared_RT.ps1`,
`RUNNING_SHARED_RT.txt` and `AGENTS.md` document and select the execution route.
Repository changes are the two runner dispatchers, `blender_comparison_check.py`,
new `shared_sionna.py`/`shared_sionna_inline.py` bootstrap dispatch, the new
Blender session/batch and health-check scripts, `test_shared_sionna.py`,
`validation/shared-sionna-2.2.json`, `AGENTS.md`, and the README, contributor and
installation/documentation links. Physics kernels and installed add-ons were
not edited.

For deliberate historical rollback, follow the
[offline RT 2.1 recovery instructions](rt21-retirement.md) in a separate directory.
The former `-Legacy` switches now stop before starting a worker. Keep the current
launchers for Blender and use the recovery kit's explicit `run` command for a
historical script. No shared package rollback is needed because no shared package
was edited.

The old Sionna environment occupies 445,876,118 bytes (425.22 MiB), and the
DiffeRT environment occupies 645,085,810 bytes (615.20 MiB). RT 2.1 is now a
removal candidate after verified offline restoration; its original environment
remains intact pending separate deletion approval. DiffeRT remains necessary for
DiffeRT and Maxwell and must be kept.

The in-progress `reproduction/` package draft and downloaded wheelhouses were
preserved. They still target the original scientific environments; they are
not advertised as a completed RT 2.2 reproduction bundle.

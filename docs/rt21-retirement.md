# RT 2.1 retirement and offline recovery

**11 November observation:** `work/sionna-runtime` and the two temporary
verification folders listed below are now absent. This packaging task did not
delete them. The verified recovery ZIP remains and is included in the
[consolidated project release](project-archive.md). The dated retirement receipt
below preserves the state actually verified on 10 November.

The project now uses shared Sionna RT 2.2 for native, phase-aligned and reciprocal
Blender sessions. DiffeRT and Maxwell still require `work/runtime`. Shared packages,
the retained runtime files, saved scenes and scientific reference results were not
changed during retirement. No ray tracing, coverage or Maxwell simulations were run.

## Historical runtime recovery

The completed RT 2.1 recovery kit is built by
[`reproduction/rt21`](../reproduction/rt21/README.md). The delivered workspace
archive is `outputs/rt21-recovery-windows-x64.zip`, accompanied by its SHA-256
and validation receipt. The ZIP is 199,696,376 bytes (190.45 MiB).
Keep a copy on another disk before removing the old
environment if protection against disk failure is required.

It contains the portable Python 3.13.13 runtime, exact LLVM DLL and adapter,
41 offline dependency wheels with a hash lock, 19 runtime overlays, an inventory
of 22,519 scientific files, frozen project source, original launchers and the
existing reciprocal, phase and Maxwell reference data. The original environment
is not copied as a movable venv: setup creates a new isolated venv after extraction.

From the extracted package directory:

```powershell
.\Recover_RT21.cmd verify
.\Recover_RT21.cmd setup
.\Recover_RT21.cmd probe --profile native
.\Recover_RT21.cmd probe --profile phase
.\Recover_RT21.cmd probe --profile reciprocal
```

These commands verify files, restore packages offline and test imports/profile
activation. They do not perform simulations. A future historical script must be
explicitly requested with `Recover_RT21.cmd run`; see the package README.
The full four-runtime reproduction draft remains separate and is not presented
as a completed DiffeRT/Maxwell installation bundle.

## Retired entry points

`-Legacy` now stops before spawning a process in the normal launch/check/compare
entry points. The old `Test_Diffraction*` commands and historical animation-folder
`Launch*` commands also stop with recovery instructions. Their exact original
copies are preserved in the package and in `work/retire-rt21/launchers-before`.
Historical reports, render-only animation commands and `.blend` files remain.

The three Python `compare_*` companion entry points now default to the shared
interpreter through the existing paired runner; their scientific kernels and
`--reuse-rays` behavior are unchanged. The old on-disk reciprocal installer is
retired; the current workflow uses process-only adapters. The original installer
remains in the frozen source inside the recovery kit.

The normal commands remain:

```powershell
.\Launch_Workflow.ps1
.\Launch_Phase_Alignment.ps1
.\Launch_Diffraction.ps1
.\Launch_Reciprocal_Diffraction.ps1
```

Always open these workbenches through their current launchers. Historical saved
scenes can retain old interpreter paths; the launchers select shared RT 2.2 for
the session without rewriting the scene or installed add-ons.

## Verification and removal

The [retirement receipt](../validation/rt21-retirement.json) records successful
offline restoration of 22,519 scientific files, all three import-only profiles,
three Blender dispatch checks, 32 retired-route guards and ten static tests.
It distinguishes archive integrity, clean offline restoration,
scientific-file equality, import-only profile probes and Blender UI/dispatch checks
from numerical validation. The numerical migration results remain in the prior
RT 2.2 receipts; no new numerical equivalence is claimed by this packaging step.

Only `work/sionna-runtime` is a retirement candidate: 445,876,118 bytes
(425.22 MiB). Keep `work/runtime` and the shared `sionna-rt-2.2-py312` environment.
The original RT 2.1 environment is retained until separately approved for deletion.
Its old saved paths and legacy switches are no longer a rollback mechanism; use
the verified recovery archive to restore it deliberately into a separate location.

The two temporary build/restore directories remain under
`work/retire-rt21/package` and `work/rt21-restore-check` (1,030,426,295 bytes total).
Automatic approval review rejected their cleanup because the required approval
category is disabled in this session. They are disposable verification copies;
the ZIP and copied audit receipts are complete. No original environment was deleted.

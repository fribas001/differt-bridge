# Structure review: Molecular Nodes

Reviewed Brady Johnston's
[MolecularNodes at commit 1a634811f21c7f426fe804a4b94642ac52b510cd](https://github.com/BradyAJohnston/MolecularNodes/tree/1a634811f21c7f426fe804a4b94642ac52b510cd)
on 2026-11-08. This is an architectural comparison; no Molecular Nodes runtime
code or node assets are copied into DiffeRT-Bridge.

| Observed practice | Adaptation here |
| --- | --- |
| Contributor guide explains modules, build and testing | Root contributor guide, project map and common developer command |
| Configuration centralizes build/dependency choices | Developer paths in `pyproject.toml`; retain the existing extension manifest as version/package authority |
| Nodes have reviewable Python source and build/round-trip checks | Add an explicit structural contract and built-ZIP node checks; retain our binary source until a full conversion is validated |
| Tests run in Blender as well as Python | Separate `tests/blender/` smoke test, clean user directories and Blender CI |
| Per-platform test matrix | Windows and Linux portable/Blender jobs; no new macOS/GPU support claim |

Sources: the pinned
[contributor guide](https://github.com/BradyAJohnston/MolecularNodes/blob/1a634811f21c7f426fe804a4b94642ac52b510cd/CONTRIBUTING.md),
[project configuration](https://github.com/BradyAJohnston/MolecularNodes/blob/1a634811f21c7f426fe804a4b94642ac52b510cd/pyproject.toml),
[test workflow](https://github.com/BradyAJohnston/MolecularNodes/blob/1a634811f21c7f426fe804a4b94642ac52b510cd/.github/workflows/_tests.yml)
and [test isolation](https://github.com/BradyAJohnston/MolecularNodes/blob/1a634811f21c7f426fe804a4b94642ac52b510cd/tests/conftest.py).

## Choices specific to this project

Our two ray tracers run outside Blender. Bundling their dependencies into an
extension through `extbpy` would change that boundary, so the existing
deterministic ZIP builder remains. Blender's Python and external Python 3.12
are documented separately.

Scientific scripts and historical reports retain their locations and bytes.
The study catalog provides a navigable research layer without invalidating
source hashes or breaking earlier launchers. New studies can use dedicated
subdirectories and declare their inputs from the start.

A complete dependency lock and self-contained research release remain future
work, with the current gaps recorded in [reproducibility](reproducibility.md).
The large extension initializer also remains an incremental refactoring
target. This change adds checks around its current behavior before moving it.

## Validation of this adaptation

Locally on Windows, the new common runner passed 363 pytest cases and 45
inherited unit tests, plus report JavaScript checks. The pytest run selected
the saved upstream DiffeRT 0.12.0 source with the existing pinned dependencies;
it did not use the workstation's field-alignment patches or certify a new
clean installation. The new prerequisite checker accepted the declared local
inputs and rejected an empty workspace.

Blender 5.2.3 validated and loaded the built ZIP in an isolated factory session.
All 11 library groups and eight public result groups passed their interface
checks; user edits survived repeated append and save/reopen, and registration
cleanup passed. The extension ZIP retained its previous SHA-256:
`f5419cbb7a57719a88749757ae51ef7a7c9d64e63929b1bfb5b6e2e4a3c58009`.
Extension and existing scientific source files were not changed.

GitHub Actions subsequently passed all four jobs for
[`642b432`](https://github.com/fribas001/differt-bridge/commit/642b43242dbb7f7f3927abef3f37fcae90501ebe):

| Workflow | Linux | Windows |
| --- | --- | --- |
| [Portable Python/report checks and build](https://github.com/fribas001/differt-bridge/actions/runs/42500132794) | Passed | Passed |
| [Blender 5.2.3 package and node checks](https://github.com/fribas001/differt-bridge/actions/runs/42500132860) | Passed | Passed |

These runs use fresh GitHub-hosted environments. They validate the repository
tests and built extension on both systems; they do not recreate the installed
Sionna research profile or the full Maxwell campaign. No Maxwell campaign was
rerun for this organizational update.

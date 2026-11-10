# Contributing to DiffeRT-Bridge

Start with the [project map](docs/architecture.md). The extension, external
ray-tracing workers, and Maxwell research have different dependencies and
different validation requirements.

## Development environment

For native and explicitly profiled research RT work on the shared Windows workstation, follow the
[RT 2.2 bootstrap commands](docs/shared-sionna-runtime.md). Do not install this
project, pytest, DiffeRT or upgraded dependencies into that shared environment.
Development, DiffeRT, Maxwell and legacy replay keep separate interpreters.
Research adapters use the guarded process-only route in
[research migration](docs/shared-sionna-research.md); never relax the RT 2.1 guards.

Use a clean Python 3.12 virtual environment and Node.js 22 or newer:

```sh
python -m venv .venv
# Activate .venv with the command for your shell.
python -m pip install -r requirements-dev.txt
python tools/dev.py test
python tools/dev.py build
```

The Python executable above is the external development interpreter. Blender
uses its own bundled Python. Keep Sionna in its separate environment described
in [installation](docs/install.md). Do not add its dependencies to DiffeRT's
environment or install either engine into Blender for these checks.

The workstation's research runtime has additional precision and material
alignment patches. It is not the clean upstream environment targeted by the
portable release tests. Use a fresh environment when validating a release;
do not loosen test tolerances to accommodate an experimental profile.

## Commands

| Command | Purpose |
| --- | --- |
| `python tools/dev.py check` | Source/package checks, documentation links, research catalog and node-library hash |
| `python tools/dev.py test` | Portable pytest suite, inherited unit tests and report JavaScript checks |
| `python tools/dev.py build` | Checked deterministic ZIP and SHA-256 file in `dist/` |
| `python tools/dev.py blender --blender /path/to/blender` | Validate and exercise the built ZIP in isolated Blender 5.2 |
| `python tools/dev.py nodes-update --blender /path/to/blender` | Explicitly refresh the reviewable node contract after an intentional asset edit |
| `python tools/research.py` | List research stages and entry points |

On Windows, quote an executable path containing spaces. The task runner can be
called from another directory; it resolves project paths relative to itself.
Temporary test files and receipts go under ignored `runs/`. Blender checks use
factory startup and temporary configuration/extension directories, preserving
the user's saved preferences and installed extensions.

## Changing Blender behavior

Keep calculations and data transformations in functions that can be called
independently of UI operators. An operator should collect settings, invoke
the operation and report its result. Existing legacy code in `__init__.py`
will be separated incrementally when its behavior has integration coverage.

Use relative imports inside the extension: Blender extension namespaces need
not be named `differt_bridge`. Preserve unregister cleanup, persisted scene
properties, result attributes and existing user edits to node groups.

For a node change, follow [Geometry Nodes development](docs/geometry-nodes.md).
For worker/export changes, run the existing
[full Blender workflow check](scripts/blender_workflow_check.py) with an
explicit external Python executable as documented in [validation](docs/validation.md).
The lightweight package smoke test does not run the ray tracers.

## Changing scientific calculations

Use [the research catalog](research/README.md) to find the relevant study.
Retain native baselines, obstacles, failed cases, numerical uncertainty and
reference provenance. A shared optional full-wave companion is a different
model from native Sionna or DiffeRT diffraction.

Existing research scripts remain at their original paths because historical
reports, source hashes and launchers depend on them. Put new campaign-specific
orchestration under `research/<study>/`; keep new reusable physics modules
separate from plotting and packaging. Update the catalog and the study's input
inventory. Do not silently rewrite frozen evidence after changing a solver.

## Review and releases

Describe the behavior changed, validation actually run and remaining limits.
Include an explicit scope for runtime or physics changes. Keep generated
videos, numerical caches, environments and credentials out of Git. Reports
and large evidence sets belong in separately checksummed release assets.

The extension manifest is the authority for its ID/version and package file
list. `check_release.py` checks version agreement with the extension and
citation. Build and inspect artifacts before publishing; CI uploads test
artifacts but does not publish a release automatically.

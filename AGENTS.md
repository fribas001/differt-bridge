# Runtime and scientific preservation

- Read `docs/shared-sionna-runtime.md` before changing engine execution paths.
- Native Windows RT uses the shared `sionna-rt-2.2-py312` venv. Run scripts with
  its Python and `-I -B -m codex_sionna_runtime`; RT child processes need the
  same bootstrap, using `sys.executable` when inheriting that interpreter.
- Do not modify shared packages, install editable projects into the shared
  venv, combine LLVM adapters, or inject its packages into Blender Python.
- Explicit phase and reciprocal research workers use `rt22_research_worker.py`
  after the shared bootstrap. Read `docs/shared-sionna-research.md`; preserve its
  exact-source guards and historical operation order. Never mix profiles within
  a process or weaken the original RT 2.1 guards.
- DiffeRT, Maxwell and legacy RT 2.1 replay retain separate interpreters.
- Preserve reference data, result archives, uncommitted reproduction work and
  original environments. Deleting an environment requires separate approval.
- Record a numerical baseline and preserve units, geometry and tolerances.
  Portable release tests assume clean upstream DiffeRT; the workstation's
  patched float32 environment has three recorded pre-existing strict failures.

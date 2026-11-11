# Shared RT 2.2 workspace launchers

These are the PowerShell launchers used by the validated Windows workspace.
They are stored here for version control; **copy them to the workspace root
before running them**. `$PSScriptRoot` must resolve to that workspace, not this
repository subdirectory. Back up any existing launcher before replacing it.

They expect the established layout:

```text
WORKSPACE/
  Launch_Workflow.ps1
  Launch_Phase_Alignment.ps1
  Launch_Reciprocal_Diffraction.ps1
  ...other launchers from this folder...
  work/github-update/differt-bridge/   # this checkout
  work/runtime/                      # retained DiffeRT/Maxwell environment
  work/sionna-runtime/                # retired; not required by current launchers
  work/...                           # existing manifests and reference data
  outputs/differt-bridge/...          # existing scenes and historical launchers
```

`Launch_Shared_RT.ps1` locates the already-provisioned shared venv under
`$env:USERPROFILE/Documents/Codex/shared-envs/sionna-rt-2.2-py312`. The portable
copy replaces only the original account-specific path with that expression.
The other launcher contents match the validated workspace copies.

The launchers do not provision environments, download datasets, install the
bootstrap, or complete the unfinished reproduction bundle. The shared runtime
must already contain `codex_sionna_runtime` and its verified LLVM adapter.

Read [shared runtime instructions](../../docs/shared-sionna-runtime.md) and
[research profiles, validation and rollback](../../docs/shared-sionna-research.md)
before running. The `Check_*` and `Compare_*` commands perform calculations;
copying these files or reading the saved validation receipts does not run them.

RT 2.1 legacy switches now stop before execution. See the
[retirement and recovery guide](../../docs/rt21-retirement.md) for the offline kit.

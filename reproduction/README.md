# Four-runtime reproduction draft

The current consolidated delivery is the [project release kit](project/README.md):
current RT 2.2/DiffeRT recovery, archived evidence and media, with the verified
RT 2.1 kit as an optional separate archive. The original draft below is retained
as historical work and is not an executable full-campaign dispatcher.

This broader draft is unfinished; its campaign dispatcher is not implemented.
Use the completed [RT 2.1 recovery package](rt21/README.md) for historical Sionna
restoration. The commands below describe the broader draft target and are not
a verified installation procedure.

# Sionna / DiffeRT / Maxwell reproduction package

Target: Windows x64 CPU, Blender 5.2.3, Python 3.12.10 and Blender's Python
3.13.13. This package carries its own interpreters, Blender, LLVM, dependency
wheels, checked runtime overlays, scientific source and reference data.

Extract the entire ZIP to a local writable folder. Keep the extracted path
reasonably short; Windows still applies path-length limits to some libraries.
Run the following in PowerShell from that folder:

```powershell
.\Reproduce.cmd verify
.\Reproduce.cmd setup
.\Reproduce.cmd compare --suite pilot --profile native
.\Reproduce.cmd compare --suite holdout --profile reciprocal
.\Reproduce.cmd replay
.\Reproduce.cmd maxwell --mode smoke
.\Reproduce.cmd report
.\Reproduce.cmd blender-check
```

Setup installs wheels offline into four new environments under `local/`, with
system/user site packages disabled. It does not install or patch anything in
your existing Python or Blender installations. Set up after extraction;
virtual environments themselves are not relocatable. If moving to another
folder/computer, extract a new copy and run setup there.

## Distinct comparisons

- `native`: clean upstream DiffeRT and native Sionna physics. Sionna uses the
  verified Windows LLVM reliability adapter, which does not alter equations.
- `workstation`: the historical comparison environment, including material,
  field-precision and optional arithmetic/geometry support. It is not an
  unmodified upstream baseline.
- `reciprocal`: the historical runtime plus the explicitly selected dielectric
  correction. Original engine outputs remain separate from Maxwell fields.

`replay` recomputes analysis from the included reference checkpoints. It is not
a new Maxwell solve. `maxwell --mode smoke` computes fresh independent FEM/BIE
controls and compares their numerical fields with the preserved reference.
`maxwell --mode full` recomputes the latest fine-reference and BIE sweeps and
can take many hours. The selected reference retains its declared FEM64 tail;
reference uncertainty is not a certified continuum bound.

To open Blender with both configured engines, run `Reproduce.cmd blender`.
Use `Reproduce.cmd animation` to regenerate the latest comparison video.
Generated results, logs, caches and environment receipts stay under `local/`;
the packaged reference data and original source remain unchanged.

## Resources and evidence

Allow at least 5 GiB free disk before setup, plus space for regenerated media.
The largest FEM128 worker previously used roughly 7.2 GiB; a computer with
16 GiB RAM and adequate Windows commit/page-file capacity is the practical
starting point for the full reference. Resource guards stop large jobs if
available commit falls below 1 GiB or free disk below 5 GiB.

Use the bundle manifest for file integrity. Use numerical comparisons and
declared tolerances for recomputation; different CPUs/BLAS builds can change
last digits. Historical receipts retain their original provenance paths;
the portable commands resolve the new package location and do not execute
commands stored in those receipts. The latest target error concerns a shared
optional full-wave companion, not equality of the native ray tracers.

Consult `VALIDATION.json` for the exact fresh checks performed on this bundle.
Dependency wheels retain their upstream license files. `vendor/blender` and
`vendor/python312` retain their license notices; patch sources and notices are
under `patches/sources/`.

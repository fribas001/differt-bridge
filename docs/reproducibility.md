# Reproducing the workflow and the research

Record the exact Git commit, Blender version, operating system, engine
versions, configuration, input hashes and numerical acceptance tolerances.
The latest studies are on `research/dielectric-diffraction`; a default clone's
`main` branch may not contain them. Check out the commit cited by the study.

| Layer | Available from this repository | Remaining requirement |
| --- | --- | --- |
| Extension | Source, manifest, node asset, deterministic build | Blender 5.2 and an external runtime |
| Portable checks | One developer command, small fixtures, clean profile tests | Development dependencies and Node.js |
| Native diffraction fixtures | Generated inputs and paired runner | Separate configured engine environments |
| Latest full-wave study | Solvers, controls, analysis and report generators; release evidence and pinned runtime assets | Extract the matching assets; run the study explicitly into new output folders |
| Published report/video bytes | [Project release archive and gallery](project-archive.md) | Download the results and animation assets; verify hashes |

## Fresh clone checks

Commit `642b432` passed the
[portable checks](https://github.com/fribas001/differt-bridge/actions/runs/42500132794)
and [Blender 5.2.3 package checks](https://github.com/fribas001/differt-bridge/actions/runs/42500132860)
in fresh Windows and Linux GitHub-hosted environments. This verifies those
test/build workflows beyond the original workstation. It does not reproduce
the full Maxwell campaign or the workstation's Sionna research profile.

Follow [Contributing](../CONTRIBUTING.md) to create a clean external development
environment, then run:

```sh
python tools/dev.py test
python tools/dev.py blender --blender /path/to/blender
python tools/research.py
python tools/research.py polarization-residual --workspace /path/to/restored-workspace
```

The research command reports declared missing inputs and fails with exit code
2 when they are absent. An earlier study without an input inventory is also
reported as incomplete. Presence of listed files does not certify their
contents or all transitive prerequisites; the original runner's hash gates
and numerical controls still apply.

## What this organization does not establish

The Windows project recovery assets now preserve DiffeRT's complete dependency
wheel closure and audited overlays, and the exact RT 2.2 package/native payload.
Their setup creates isolated venvs without inheriting base-Python packages.
The historical RT 2.1 kit remains a separate optional asset. Some reference
resource guards use Windows APIs; these assets do not certify Linux/GPU replay.

Complete fresh recomputation of every Maxwell campaign on another physical
computer has not been demonstrated. The project archives preserve the existing
evidence and preceding inputs, with an isolated runtime setup and import/dispatch
checks. No further simulations were run during packaging, as requested. Historical
workstation evidence remains distinct from a new numerical validation run.

Compare scientific results using declared numerical tolerances. Byte-identical
results across operating systems, compiler/BLAS builds or CPU/GPU execution
are a stronger claim and are not guaranteed. Keep downloaded evidence hashes
separate from newly recomputed output hashes.

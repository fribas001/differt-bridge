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
| Latest full-wave study | Solvers, controls, analysis and report generators | Earlier reference data, workspace launchers and verified research profiles |
| Published report/video bytes | Historical release assets where linked | Latest media and evidence are still separate local artifacts |

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

The core DiffeRT packages are version-pinned in `requirements-external.txt`.
There is not yet a complete, hashed dependency lock for both engines and all
research/plotting dependencies. Some reference resource guards use Windows
APIs. The local research environment includes profiles beyond the clean
release runtime, and some dependencies were inherited from its base Python.

Complete reproduction of the latest Maxwell campaign from a fresh clone on
another machine has not been demonstrated. It needs a self-contained evidence
bundle, complete runtime/profile setup, all preceding inputs and a clean
environment run. The new structure makes these gaps visible; it does not turn
historical workstation evidence into a portable certification.

Compare scientific results using declared numerical tolerances. Byte-identical
results across operating systems, compiler/BLAS builds or CPU/GPU execution
are a stronger claim and are not guaranteed. Keep downloaded evidence hashes
separate from newly recomputed output hashes.

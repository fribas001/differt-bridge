# DiffeRT-Bridge 0.6.3

A Blender 5.2 companion to [SionnaRT-Bridge](https://github.com/fribas001/sionnart-bridge). Keep both extensions enabled, share the scene geometry, run each engine in its own Python environment, and compare saved paths, coverage samples and motion.

This first public release is a **prerelease**. The extension is derived from SionnaRT-Bridge 2.1.0 at commit `811c87ce3c7f352278f891fb399b510f6ad3ddb0`, under GPL-3.0-or-later. Scientific equivalence between the engines is not claimed.

## Start here

- [Install and configure both engines](docs/install.md)
- [Shared Sionna RT 2.2 workflow and historical-runtime rollback](docs/shared-sionna-runtime.md)
- [Reciprocal and phase-alignment migration measurements](docs/shared-sionna-research.md)
- [Documentation index](docs/index.md)
- [Validation, release checks and limitations](docs/validation.md)
- [Research studies: diffraction, reciprocity and Maxwell references](research/README.md)
- [Reproducing the workflow on another computer](docs/reproducibility.md)
- [Contributing, project structure and Geometry Nodes](CONTRIBUTING.md)
- [Release downloads: extension, reports and animation](https://github.com/fribas001/differt-bridge/releases/tag/v0.6.3)
- [Changes and provenance](CHANGELOG.md)

## Workflow

Install `differt_bridge-0.6.3.zip` with Blender's **Install from Disk** command. Configure **DiffeRT â†’ Runtime â†’ External Python** with a separate environment created from `requirements-external.txt`. In the DiffeRT panel, use **Copy Sionna Setup**, then **Run Both â€” Paths**. Each engine keeps its own settings, workers and result collections.

Geometry is shared. Device objects and radio settings are copied; repeat the copy after changing device constraints, static settings or animation assignments. Custom drivers on radio properties are not translated automatically. Use separate output folders for both engines.

The extension provides paths, per-link diagnostics, repeated depth benchmarks, shared point-receiver grids, planar/projected/stacked coverage, timeline runs, endpoint Doppler, Geometry Nodes visualization, HDF5/CSV/JSON exports and optional simulated CIR/CSI. Reports identify missing results and input mismatches rather than silently declaring equivalence.

## Model boundaries

| Area | Behavior and scope |
| --- | --- |
| Geometry | Native DiffeRT candidate search, with bridge float64 reconstruction and full-mesh visibility checks for supported reflection/diffraction chains |
| Fields | DiffeRT's native electromagnetic solver and material catalog; this release does not install the workstation's arithmetic-alignment experiments |
| Phase | Exported path coefficients exclude carrier propagation phase; CIR includes it exactly once |
| Diffraction | Finite adjacent-face wedges; open sheet edges are excluded; Sionna edge/lit-region flags have no exact mapping |
| Gradients | NumPy/SciPy geometry refinement and serialized Blender exports do not preserve an end-to-end gradient graph |
| Coverage | Point samples; these are not Sionna's surface-area estimators |
| Motion | TX/RX translation with frozen scatterers per frame; no moving-surface micro-Doppler |
| Materials | Thin slabs and dielectric surfaces; no volumetric ray bending or inherited vegetation-accuracy claim |
| Search | Exhaustive candidate budgets fail explicitly when exceeded; SBR/hybrid methods may miss candidates |

The principal tested deployment is Windows x64, Blender 5.2.3 LTS and Python 3.12. DiffeRT 0.12.0, JAX/JAXlib 0.12.0.1 and Warp 1.18.0 are pinned. Portable CI does not certify GPU execution or electromagnetic accuracy on every platform.

## Build and test

```powershell
python -m pip install -r requirements-dev.txt
python tools/dev.py test
python tools/dev.py build
python tools/dev.py blender --blender /path/to/blender
```

The deterministic ZIP and SHA-256 file are written to `dist/`. Scientific runtimes, compiler binaries, caches, generated frames and workstation backups are not bundled. Reproduce a generated diffraction fixture with `scripts/run_diffraction.py`; experimental Sionna field changes require an explicit flag and run only in that child process.

See [third-party attribution](THIRD_PARTY_SOFTWARE.md), [upstream provenance](UPSTREAM.json), [authors](AUTHORS.md), and [license](LICENSE).

## Research and reproducibility

The [research catalog](research/README.md) links all eleven investigations, their scope and established scripts. The [latest reference refinement](docs/dielectric3d-residual.md) reports the remaining polarization discrepancy and the separate research candidate, including uncertainty and regressions. Shared companion fields are distinct from native ray-tracer outputs.

Some advanced studies still require earlier local evidence and workstation profiles. Consult [reproducibility status](docs/reproducibility.md) before assuming a clone can recreate a full campaign. The [Molecular Nodes structure review](docs/molecularnodes-review.md) explains the contributor, testing and node-validation practices adopted for this project.

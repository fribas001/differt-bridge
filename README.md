# DiffeRT-Bridge 0.6.3

A Blender 5.2 companion to [SionnaRT-Bridge](https://github.com/fribas001/sionnart-bridge). Keep both extensions enabled, share the scene geometry, run each engine in its own Python environment, and compare saved paths, coverage samples and motion.

This first public release is a **prerelease**. The extension is derived from SionnaRT-Bridge 2.1.0 at commit `811c87ce3c7f352278f891fb399b510f6ad3ddb0`, under GPL-3.0-or-later. Scientific equivalence between the engines is not claimed.

## Start here

- [Install and configure both engines](docs/install.md)
- [Validation, release checks and limitations](docs/validation.md)
- [Diffraction findings and experimental corrections](docs/diffraction.md)
- [Dielectric reciprocity and boundary investigation](docs/dielectric-diffraction.md)
- [Reciprocal corrections and independent Maxwell validation](docs/dielectric-corrections.md)
- [Release downloads: extension, reports and animation](https://github.com/fribas001/differt-bridge/releases/tag/v0.6.3)
- [Changes and provenance](CHANGELOG.md)

## Workflow

Install `differt_bridge-0.6.3.zip` with Blender's **Install from Disk** command. Configure **DiffeRT → Runtime → External Python** with a separate environment created from `requirements-external.txt`. In the DiffeRT panel, use **Copy Sionna Setup**, then **Run Both — Paths**. Each engine keeps its own settings, workers and result collections.

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
python -m pytest
python -m unittest discover -s src/differt_bridge/tests -p 'test_*.py'
node src/differt_bridge/tests/test_report_math.cjs
python scripts/check_release.py
python scripts/build_extension.py
```

The deterministic ZIP and SHA-256 file are written to `dist/`. Scientific runtimes, compiler binaries, caches, generated frames and workstation backups are not bundled. Reproduce a generated diffraction fixture with `scripts/run_diffraction.py`; experimental Sionna field changes require an explicit flag and run only in that child process.

See [third-party attribution](THIRD_PARTY_SOFTWARE.md), [upstream provenance](UPSTREAM.json), [authors](AUTHORS.md), and [license](LICENSE).

See [the Maxwell model-error addendum](docs/diffraction-model-errors.md) for the independent boundary-integral cross-check, new angular/material sweeps, comparison-normalization correction and animation reproduction. No additional runtime physics patch is promoted by this study.

The [optional full-wave 2D refinement](docs/maxwell-refinement.md) reduces the canonical Maxwell discrepancy with a separate coupled boundary solve. It preserves native 3D engine exports and rejects unsupported scenes; see its independent FDFD validation and companion workflow.

The [native 3D investigation](docs/native3d-diffraction.md) validates point-dipole fields against an independent PEC Maxwell reference. It adds an optional canonical 3D Hertz-UTD correction and a guarded opaque-slab numerical fix in the reciprocal profile.

The [3D dielectric follow-up](docs/dielectric3d-diffraction.md) compares all vector dipole ports with independent coupled BIE/FEM Maxwell solutions, checks reciprocity and boundaries, and fixes weak-loss cancellation in Sionna's material square root. It preserves native exports and documents the remaining model errors, finite-distance source effects and limits of the infinite-wedge benchmark.

The [optional 3D dielectric refinement](docs/dielectric3d-refinement.md) adds a shared coupled full-wave field beside both ray exports. It validates new materials and port positions against independent FEM, rejects unsupported geometry before computation, and retains native UTD behavior for the normal Blender workflow.

The [weak-polarization convergence follow-up](docs/dielectric3d-weak.md) reduces the companion's panel-discretization error with fixed, unfitted spatial extrapolation. The default companion now uses the validated 16/32-panel pair; the original standard mode remains available. New materials, complete vector ports, finer independent FEM and spectral/domain controls verify the correction.

The [remaining-polarization reference audit](docs/dielectric3d-polarization.md) separates the previous 4.39% residual from Maxwell mesh uncertainty. It adds finer independent references, explicit tail and domain controls, an equivalent sparse-factorization policy for large reference solves, and an updated animation. Production companion fields and both native runtimes are preserved.

The [further polarization residual study](docs/dielectric3d-residual.md) refines the independent Maxwell reference, rejects an unsupported field-recovery change, and evaluates a separate finer BIE candidate. It includes off-grid analytic controls, explicit numerical uncertainty and a regenerated animation; production and installed workflows remain unchanged.

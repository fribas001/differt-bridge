# Historical notebook inputs

This project-generated numerical supplement is distributed under GPL-3.0-or-later
with DiffeRT-Bridge. It contains thirteen files totaling 244,201 bytes. It was prepared
on 15 November 2026 from preserved October studies; no scientific simulations were run.

`manifest.json` lists every analysis input, its original study-relative path, original
SHA-256, redistributed SHA-256, byte length and any transformation. All thirteen current
files are byte-for-byte copies. No original numeric values or failed controls were changed.
`notebooks/replay.py` verifies the complete bundle before loading any table.

## Source studies

| Bundle | Original study directory | Included files |
| --- | --- | --- |
| `focused_60ghz` | `focused_solver_comparison_20261017` | Complete results table, analysis and verification |
| `multiple_diffraction_60ghz` | `multidiffraction_20261017` | Complete results table, analysis and verification |
| `edge_fullwave_60ghz` | `edge_fullwave_20261017` | Analysis, declared contract, verification and zero-contrast diagnostic |
| `ris_controls_23_8ghz` | `RIS_Independent_Validation_238GHz_2026-10-13` | Complete native RT table, slab comparison and verification |

The first three folders were under the vegetation project's `outputs/veg/`; the last
was under the RIS project's `outputs/`. Their project-generated results were not in the
source/results inventories of DiffeRT's `project-2026-11-11` release when this supplement
was prepared. These files add analysis coverage rather than duplicate that archive.

## Interpretation

- **Focused vegetation:** 60 GHz, Sionna RT 2.2.0 / DiffeRT 0.12.0. The explicit checked
  direct-path replacement in corrected totals must not be confused with native raw totals.
  Repeated rows retain seeds and budgets; raw/corrected fields are both included.
- **Multiple diffraction:** same engine versions, four links, V/H and maximum total depth
  four. Incoherent loss is primary. Open-leaf-edge eligibility and coefficient differences
  confound direct engine ranking. The analysis includes original input hashes and search
  audits. Full exhaustive depth-four runs were not completed.
- **Edge controls:** 60 GHz, 2D infinite extrusion, Ez plane wave at ten degrees. Identical
  supplied first-order edges and a common coherent GO baseline isolate formulations;
  this is not a native path-discovery comparison. Sionna transcriptions were checked
  against native kernels. Both constructions fail the transparent-material limit.
- **RIS controls:** 23.8 GHz, fourteen ideal polarized controls and twelve failed geometry
  diagnostic rows. Full-wave slab data use paired empty-domain normalization and displaced-air
  phase correction. Twenty-six openEMS solves produced thirteen paired comparisons.
  The original verification receipt describes the state on 13 October; its prepared-only
  finite-leaf statement must not be interpreted as the status of later follow-up campaigns.

Material parameters are assumptions from the original studies, not new measurements.
These reduced controls do not validate full-tree loss, RIS calibration, hardware coupling
or the general physical accuracy of either ray tracer. Zero physical paths, missing
coefficients and failed diagnostics remain distinct.

## Replay versus recomputation

The full local field dumps, native raw result files, geometry, earlier helpers and runtime
installations are not included here. Recorded hashes for omitted upstream files identify
their provenance; they do not imply the files are downloaded or available from this bundle.
All four notebooks need only this bundle and the checked-in catalog/fixture generator.
Fresh scientific recomputation of the original campaigns still needs their workspace
inputs and runtime setup. The optional generated-fixture run is a separate experiment.

Maintainers can reproduce the selection from the preserved study folders:

```sh
python scripts/prepare_notebook_data.py --vegetation-root /path/to/outputs/veg --ris-root /path/to/ris/outputs
```

The importer checks all selected files exist before writing. It records any future
absolute-location redaction separately from source hashes and preserves numerical values.
Review changed hashes and the scientific provenance before replacing an established bundle.

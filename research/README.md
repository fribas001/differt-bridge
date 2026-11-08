# Research studies

This is the entry point for comparing the native ray tracers, investigating
diffraction and validating the optional Maxwell companion. The machine-readable
[catalog](studies.toml) connects each report with its established entry points.

```sh
python tools/research.py
python tools/research.py polarization-residual
```

| Stage | Report |
| --- | --- |
| Native diffraction fixtures | [Diffraction](../docs/diffraction.md) |
| Dielectric reciprocity and boundaries | [Survey](../docs/dielectric-diffraction.md) |
| Reciprocal corrections | [Independent controls](../docs/dielectric-corrections.md) |
| Model errors against Maxwell | [Model-error study](../docs/diffraction-model-errors.md) |
| Canonical 2D companion | [Full-wave refinement](../docs/maxwell-refinement.md) |
| Native 3D diffraction | [Point-source/PEC study](../docs/native3d-diffraction.md) |
| Native dielectric 3D diffraction | [Vector Maxwell comparison](../docs/dielectric3d-diffraction.md) |
| Optional 3D companion | [Guarded full-wave refinement](../docs/dielectric3d-refinement.md) |
| Weak polarization | [Fixed spatial extrapolation](../docs/dielectric3d-weak.md) |
| Remaining 4.39% discrepancy | [Reference audit](../docs/dielectric3d-polarization.md) |
| Remaining 1.56% discrepancy | [Further reference refinement](../docs/dielectric3d-residual.md) |

The latest reference revises the target production-companion discrepancy to
1.2179%. A separate candidate reaches 0.6612% on that target but regresses in
four of 36 groups. These numbers refer to the optional full-wave companion,
not native Sionna-versus-DiffeRT accuracy, and are qualified by the reference
sensitivity in the report.

## Reproduction status

`generated-fixtures` means the native diagnostic runner creates its test inputs.
`workspace-study` means the historical campaign uses the original workspace
and prior evidence. An entry point is not necessarily a self-contained command.
Follow its report for arguments, execution order, runtime profile and scope.

To check the latest study's declared entry prerequisites:

```sh
python tools/research.py polarization-residual --workspace /path/to/restored-workspace
```

This checks file presence only. Many earlier studies do not yet have complete
input inventories. See [reproducibility status](../docs/reproducibility.md).
Native engine outputs, a shared companion, independent references and rejected
candidates must remain separately labelled in analyses and animations.

## Source and output policy

Existing numerical modules stay under `scripts/` to preserve historical paths
and hashes. New study orchestration belongs in a dedicated subdirectory here,
with declared inputs and expected checks. No old evidence is moved or rewritten
by the catalog. Keep numerical caches, reports and videos outside the source
tree or under ignored output folders; distribute required evidence separately
with checksums and a restoration manifest.

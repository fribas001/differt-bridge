# Model and figure provenance

`manifest.json` checks every asset before notebook display or Blender rendering.
The original 13 numerical summaries in `../data/` are unchanged.

`models.json` extracts 22 synthetic cases from the original `plan.json` files:
11 focused 60 GHz cases, four final multiple-diffraction links, and seven ideal
23.8 GHz controls. Vertices, triangle indices, TX/RX coordinates and radio-material
values are preserved. It also retains the four blocked-link path examples from
`multidiffraction_20261017/figure_examples.json`. Source hashes and study-relative
identifiers are included. Actual plant/RIS diagnostic meshes are not included.

Three PNGs are byte-for-byte copies of historical project figures:

| Asset | Study | Meaning |
| --- | --- | --- |
| `focused_paths.png` | focused_solver_comparison_20261017 | Top views of retained paths; the third panel is a separate short wood-edge link |
| `multiple_paths.png` | multidiffraction_20261017 | Four retained V-polarized paths in `blocked_coupled`; losses refer to each path alone |
| `fullwave_fields.png` | edge_fullwave_20261017 | openEMS 2D normalized coherent Ez maps, with the 12 probes for each coupon |

Seven additional PNGs are new Blender presentation renders. Their JSON receipts record
the model identifier, camera, source geometry hash, renderer hash, image hash and Blender
version. These are not electromagnetic simulation results. The paired blocked-link
images use identical cameras and the strongest retained path for each engine; native
path-family differences remain visible. Surface colors and enlarged TX/RX/path markers
are illustrative. No physical ground plane is added. Detail views crop out remote devices.

The single wood screen has zero geometric thickness and an assigned slab thickness;
the closed square branch has geometric volume with a half-diameter slab assigned at each
crossing. These are distinct radio models. No display material is used as a radio material.

To re-extract the original source assets, run `scripts/prepare_notebook_visuals.py` with
`--vegetation-root` pointing at the directory containing the three vegetation study
folders and `--ris-root` at `RIS_Independent_Validation_238GHz_2026-10-13`. Then regenerate
the Blender images with `scripts/render_notebook_models.py` as described in
[the Blender notebook guide](../../docs/blender-notebooks.md). Re-extraction resets
the asset manifest; regenerate the seven renders immediately afterward.

These are project-generated assets under GPL-3.0-or-later. Jan-Hendrik Müller's optional
Jupyter extension is separately attributed in the guide; no upstream add-on source or
binary is bundled here.

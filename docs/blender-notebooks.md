# Model images and Blender notebooks

Notebooks 00–03 now place model images beside the comparisons. Notebook 04 provides
a gallery and an optional Blender renderer for all 22 preserved synthetic cases.
All five notebooks run with cached images in the ordinary analysis environment.
The exported notebook outputs embed the PNGs, so they can be read without Blender.

## Live rendering with Jan-Hendrik Müller's Jupyter extension

[jupyter-blender](https://github.com/kolibril13/jupyter-blender) starts an in-process
kernel: notebook cells can import `bpy` and use the running Blender instance.
The inspected version is **0.1.11**, requiring **Blender 5.1+**, at upstream commit
[`838a36a`](https://github.com/kolibril13/jupyter-blender/tree/838a36aa96836a6cce3c36133162c415d7a4baef).
It is an independent AGPL-3.0-or-later extension by Jan-Hendrik Müller and contributors.
It is linked as an optional dependency, not vendored into DiffeRT-Bridge.

1. In Blender Preferences → Get Extensions → Repositories, add
   `https://jan-hendrik-mueller.de/blender-extensions/index.json`, then install **Jupyter**.
   The author's [extension page](https://jan-hendrik-mueller.de/blender-extensions/)
   also links its download. Use a separate Blender profile for initial evaluation.
2. Open the 3D Viewport sidebar (**N**) → **Jupyter**. Click **Install Python Modules**.
   The extension manages its own Jupyter dependencies. Do not install the DiffeRT or
   Sionna engine requirements in Blender's Python.
3. Set the notebook directory to this repository's checkout, retain the default
   loopback host `127.0.0.1`, and click **Start Browser** (called **Start Notebook Server**
   in the upstream README). The server normally uses port 10462 and token authentication.
4. Open `notebooks/04_blender_models.ipynb` through that server. Run the cached cells,
   then set `RENDER_LIVE = True` to enable the optional rendering cells. A normal external
   Python kernel cannot import Blender's `bpy`; use the extension's running kernel.
5. Select a model case, a retained path if applicable, and the detail/overview framing.
   Renders and receipts go to `build/notebook-renders/`. Each call creates a separate
   **DiffeRT Notebook** scene; choose it in Blender's scene selector to inspect it.

The renderer preserves the current scene and its settings. It does not change saved
preferences, run electromagnetic solvers, install packages, save over a `.blend` file,
or replace the historical data. Colors, lights and marker widths describe a visual
presentation; they are not radio material parameters or extra physical objects.
Repeated calls retain additional scenes for inspection. Render execution is synchronous
on Blender's main thread and can briefly occupy the interface.

The paired-render cell uses identical geometry and camera settings for two retained
native paths, then displays the PNGs side by side. Outputs use embedded images and
work in HTML exports without an additional Jupyter widget package.

## Rebuild the checked-in model pictures

From the repository root, with Blender on PATH:

```sh
blender --background --factory-startup --python-exit-code 1 --python scripts/render_notebook_models.py
```

This regenerates seven images and JSON receipts using Cycles CPU, updates their asset
checksums, and checks that the original scene's objects and render settings survived.
It runs no DiffeRT or Sionna simulation. Images may vary across Blender/platform builds;
the receipts record the actual build version, renderer hash, camera and image hash.
The existing extension package is unaffected.

## Evidence and limits

- Seven fresh presentation renders were executed with Blender 5.2.0 LTS on Windows,
  using factory startup; original scene preservation passed.
- The rebuilt, packaged DiffeRT-Bridge also passed `blender_workflow_check.py` with
  factory startup, including paths, coverage, export, motion, cancellation and reopening.
- The ordinary Python notebook path is checked in Windows and Linux CI. CI does not
  install Blender or Jan-Hendrik's extension.
- The live extension UI/server workflow has not been exercised in this integration's
  validation. Its setup instructions and dependency boundaries were checked against
  the upstream source above; successful background renders do not establish that UI test.
- Geometry and retained paths come from the original synthetic study plans. The
  23.8 GHz actual-plant diagnostic meshes are excluded. Failed numerical controls remain
  visible in notebook 01. The 2D full-wave field maps are historical solver images,
  not Blender calculations or new physics validation.

See [asset provenance](../notebooks/assets/README.md) and the
[notebook guide](../notebooks/README.md).

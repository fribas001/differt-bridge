# Research notebooks

Four notebooks replay preserved numerical results with tables, figures and executable
checks. All default cells run without Blender, DiffeRT, Sionna, GPU access or downloads.
The 244 KB data supplement is included in the repository with source/output checksums.

| Notebook | Contents |
| --- | --- |
| [00 — Start here](00_start_here.ipynb) | Research map, provenance, evidence levels and phase/power conventions |
| [01 — Native comparison](01_native_comparison.ipynb) | 23.8 GHz controls and failed diagnostics; 60 GHz raw/corrected totals; optional new wedge fixtures |
| [02 — Multiple diffraction](02_multiple_diffraction.ipynb) | Order-dependent loss, exhaustive/hybrid controls, ray budgets and native path-family differences |
| [03 — Full-wave validation](03_fullwave_validation.ipynb) | Slab mesh/PML checks, fixed-edge 2D comparisons and failed transparent-material consistency |

## Install and run

Use Python 3.12 or later in a dedicated analysis environment. From the repository root:

```sh
python -m venv .venv-notebooks
# Windows PowerShell:
.venv-notebooks/Scripts/python.exe -m pip install -r requirements-notebooks.txt
.venv-notebooks/Scripts/python.exe -m jupyter lab notebooks
# macOS/Linux: use .venv-notebooks/bin/python instead.
```

Select the environment's Python kernel and choose **Restart Kernel and Run All Cells**.
The notebooks locate the repository from either its root or the `notebooks/` directory.

For unattended validation and HTML output with an explicitly selected interpreter:

```sh
.venv-notebooks/Scripts/python.exe scripts/execute_notebooks.py
```

This executes fresh kernels and writes executed notebooks, HTML pages and an execution
receipt to `build/notebooks/`. It installs no persistent kernelspec. The default checked-in
notebooks have cleared outputs; CI publishes executed copies and HTML as an artifact.

## Optional fresh native run

Notebook 01 has a disabled-by-default `RUN_NATIVE` section. Set the absolute path to a
separate pinned DiffeRT interpreter, optionally a separate Sionna interpreter and LLVM
library, then enable it. It invokes `scripts/run_diffraction.py` in a new `runs/` directory.
These generated 3.5 GHz wedge fixtures are separate from the historical 23.8/60 GHz tables.
The other notebooks do not run native solvers. Failed workers and candidate-budget limits
remain explicit in the runner's receipt.

Follow [engine installation](../docs/install.md) for native environments. Do not install
both engines into the notebook environment. Experimental Sionna profiles remain available
only through the existing runner's explicit option, outside the default notebook workflow.

## Scope and provenance

The notebooks recompute summary quantities and check their recorded bounds. They are
analysis replays, not fresh physics validation. Native engine differences, historically
corrected direct contributions, independent full-wave references and failed physical
limits remain separately labeled. See [data provenance](data/README.md) and the
[research index](../docs/research.md) before interpreting a result.

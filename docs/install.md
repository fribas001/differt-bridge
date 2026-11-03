# Installation and the two-engine workflow

## DiffeRT runtime

Use a fresh Python 3.12 environment. A Sionna environment must remain separate.

```powershell
git clone https://github.com/fribas001/differt-bridge.git
cd differt-bridge
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-external.txt
.\.venv\Scripts\python.exe -c "import differt,jax; print(differt.__version__,jax.__version__,jax.devices())"
```

Alternatively, `scripts/setup_runtime.ps1 -Python C:/path/to/python.exe -Environment .venv` creates and probes the environment. Install the ZIP from the [prerelease](https://github.com/fribas001/differt-bridge/releases/tag/v0.6.3) through Blender 5.2 **Edit → Preferences → Add-ons → Install from Disk**. Enable DiffeRT-Bridge; retain SionnaRT-Bridge.

In **DiffeRT → Runtime**, select External Python and the new environment's `Scripts/python.exe`. Choose a writable results folder and press **Test Runtime**. Default Python/results paths can also be saved under the extension's preferences. Explicit scene paths take precedence over these defaults.

## Sionna runtime

Follow [SionnaRT-Bridge's installation guide](https://github.com/fribas001/sionnart-bridge/blob/main/src/sionnart_bridge/README.md), using that repository's own dependency file. DiffeRT-Bridge does not import Sionna, Mitsuba or Dr.Jit inside its worker.

For the specifically validated Windows CPU stack, see the [scoped LLVM adapter](https://github.com/fribas001/sionnart-bridge/tree/main/tools/windows_llvm_adapter). It is an optional runtime workaround with version/hash checks, backup and restore. CUDA users should follow Sionna's native setup. Do not treat the adapter as a generic LLVM upgrade or a diffraction physics fix.

## Compare

1. Open or create your Sionna scene.
2. Use **DiffeRT → Copy Sionna Setup**. Geometry is shared; devices and radio controls are copied into separate DiffeRT collections.
3. Set each extension's external interpreter and separate results folder.
4. Begin with maximum depth 1, LoS and specular reflection, isotropic antennas and a small scene.
5. Use **Run Both — Paths** and open the comparison report. Check its actual-input and geometry matching status before interpreting deltas.
6. Enable diffraction or additional features separately and consult the model-limit table and diffraction report.

Do not expect the workstation research profile's zero phase residual on a fresh native installation. That historical result used additional arithmetic/material/geometry alignment beyond this release's default runtime. The native comparison is retained to expose actual engine differences.

## Reproducible diffraction diagnostics

```powershell
.\.venv\Scripts\python.exe scripts/run_diffraction.py --differt-python .venv/Scripts/python.exe --output runs/diffraction
# Add Sionna only when its separate environment is ready:
.\.venv\Scripts\python.exe scripts/run_diffraction.py --differt-python .venv/Scripts/python.exe --sionna-python C:/path/to/sionna/python.exe --llvm-library 'C:/Program Files/LLVM/bin/LLVM-C.dll' --output runs/paired
```

`--suite physics` selects the extended field fixtures. `--experimental-sionna kp_assembly` or `kp_depth` adds an isolated candidate run; no installed source file is changed. The native Sionna run is retained alongside it. Deep exhaustive DiffeRT cases can exceed the configured search budget; such cases and nonzero child exit codes remain in the receipt.

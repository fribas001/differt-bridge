# Historical Sionna RT 2.1 recovery package

This is an offline Windows x64 recovery kit for the retired RT 2.1 interpreter.
The current Blender workflow uses shared RT 2.2 and separate DiffeRT/Maxwell.
This kit does not replace that workflow or install anything into its runtimes.

Extract the entire archive to a short, writable path, then run PowerShell there:

```powershell
.\Recover_RT21.cmd verify
.\Recover_RT21.cmd setup
.\Recover_RT21.cmd probe --profile native
.\Recover_RT21.cmd probe --profile phase
.\Recover_RT21.cmd probe --profile reciprocal
```

Setup installs the hash-pinned wheels entirely offline, restores all audited
scientific files, and relocates only the LLVM manifest's absolute DLL path.
It creates a new `local/runtime` venv; it never copies an existing venv or needs
the retired environment. A bundled Python 3.13.13 interpreter and the exact
LLVM DLL/adapter are included. Keep 2 GiB free for extraction and restoration.
Runtime imports verify CPU LLVM and profile activation without tracing rays,
building radio maps, executing JIT arithmetic or solving Maxwell equations.
For a fresh location, extract again and run setup there; venvs are not movable.

The package contains exact dependency wheels and a hash lock, the overlay and
its pre/post hashes, the original scientific-file inventory, frozen project
source, historical launchers, the 286-case reciprocal campaign, 72-case holdout,
phase evidence and the latest Maxwell reference checkpoints. These reference
fields are preserved evidence, not new numerical validation of the restored kit.
The full four-runtime DiffeRT/Maxwell reproduction draft is a separate project.

To explicitly run a historical script later (this **can** run simulations):

```powershell
.\Recover_RT21.cmd run --profile reciprocal -- .\project\scripts\dielectric_worker.py reciprocal sionna .\reference\work\dielectric-corrections\final\cases.json .\local\new-reciprocal --precision float32 --diffraction-geometry validated
```

Use `phase` only for the validated LoS/specular geometry/arithmetic profile.
The portable Python runner preserves arguments and the package working
directory. Native RT 2.1 here includes the original reliability and opt-in
geometry support; it is not an unpatched upstream installation. Original
receipts retain provenance paths; the launcher does not execute those paths.

`MANIFEST.json` protects every immutable package file. Keep the accompanying
archive SHA-256 and validation receipt with the ZIP. Validation distinguishes
file equality/import checks from numerical simulations. Exact floating-point
replay on a different CPU is not guaranteed by byte-identical package files.

The archived `.blend` files and old launcher copies are historical evidence.
Do not launch them directly with old absolute interpreter settings. Use the
current shared RT 2.2 Blender launchers for everyday work. Restoring RT 2.1 for
a future historical comparison is deliberate and isolated from those sessions.

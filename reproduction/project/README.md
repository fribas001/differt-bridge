# Project recovery and reproduction assets

Download the source, results, animations and Windows runtime archives from the
same release. Verify their SHA-256 values from `SHA256SUMS.txt`, then extract all
four into the same **fresh, short, writable** directory (for example `C:\rt-replay`).
Keep 6 GiB free for extraction and setup. No existing environment is overwritten.

```powershell
.\Replay.cmd verify
.\Replay.cmd setup
.\Replay.cmd probe --profile native
.\Replay.cmd probe --profile phase
.\Replay.cmd probe --profile reciprocal
.\Replay.cmd blender-check --profile phase --blender 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
.\Replay.cmd blender --profile reciprocal --blender 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
```

Use Blender 5.2.3 for the recorded UI/dispatch validation. Blender itself is an
external application dependency; the two exact installed add-ons are included.
The commands above verify files, restore isolated runtimes, import modules and
inspect Blender dispatch. They perform no scientific simulations and save no scenes.

The Python 3.12.10 interpreter is included. DiffeRT dependencies install offline
from hash-pinned wheels, then receive audited historical patches. RT 2.2 packages
and its verified LLVM adapter restore from an exact installed-payload snapshot
into a new venv. Console-script executables and old venv launchers are excluded;
invoke modules using the recovered interpreter. These are Windows x64 CPU stacks.
The arithmetic profile additionally requires AVX2/FMA. Shared packages on the
original computer are never changed. The optional RT 2.1 recovery ZIP is separate:
extract it into its own directory and follow its README.

Open `workspace/index.html` for existing reports and videos. Historical results
retain their original provenance, including old absolute paths inside receipts.
The recovery commands resolve the new location. Archived workspace PowerShell
launchers retain workstation settings; use `Replay.cmd` on another computer.

Scientific scripts are in `workspace/work/github-update/differt-bridge/scripts`.
The repository's `research/studies.toml` and linked study documents map the eleven
diffraction/Maxwell studies to entry points. The archive also preserves the earlier
coverage, motion, specular phase and obstacle investigations with their results.
Commands below are **explicit calculations**, not part of setup:

```powershell
.\Replay.cmd run --engine differt --profile reciprocal -- work/github-update/differt-bridge/scripts/run_dielectric.py --differt-python work/runtime/Scripts/python.exe --sionna-python work/rt22-runtime/Scripts/python.exe --output work/new-reciprocal --profiles sionna-reciprocal,differt-reciprocal --precision float32 --manifest work/dielectric-corrections/final/cases.json
```

This example reruns the preserved 286-case reciprocal manifest. For another
study, use its documented script and arguments.
For paired runners set `--differt-python work/runtime/Scripts/python.exe` and
`--sionna-python work/rt22-runtime/Scripts/python.exe`. Use a **new output folder**;
the recovered reference data is evidence, not disposable calculation output.
Run generic Maxwell/report scripts with `--engine differt`. `--profile phase` is
restricted to the declared LoS/specular domain; it is not a diffraction model.

This release preserves the code, dependencies, inputs, checkpoints and published
results required to investigate and rerun the recorded studies. It does not claim
bitwise numerical identity on every CPU, exhaustive fresh replay of every study,
or certified arbitrary-geometry Maxwell accuracy. Read the numerical tolerances,
six archived replay discrepancies and model/reference limitations in the reports.
No simulations were rerun to assemble this release.

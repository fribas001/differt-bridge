# Project recovery and reproduction assets

Download `fetch.py` and `assets.json` from the same project release, or use this
directory in the release branch checkout. With Python 3.12 or later:

```powershell
python .\fetch.py --destination C:\rt-replay --extract
Set-Location C:\rt-replay
```

The downloader verifies each transfer part and reconstructs the four original
source, results, animations and Windows runtime ZIPs. It then verifies their
whole-file SHA-256 values before extraction. Interrupted downloads resume from
verified parts. Large files are split only for reliable transfer; the joined ZIPs
are byte-identical to the recovery-tested archives. Add `--historical` to also
download the separate RT 2.1 kit, which must be extracted in its own directory.

Use a **fresh, short, writable** destination and keep 6 GiB free for downloads,
extraction and setup. No existing environment is overwritten. Python is needed
only for this initial downloader; the runtime archive includes Python 3.12.10.
Alternatively, concatenate the numbered parts in order, verify the resulting
ZIPs against `SHA256SUMS.txt`, and extract the four main ZIPs into one directory.

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

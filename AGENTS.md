# DiffeRT-Bridge repository instructions

## Start here

Read README.md, docs/install.md, docs/validation.md and docs/diffraction.md.
The extension lives in src/differt_bridge/. Keep its DiffeRT identity, settings,
workers and results separate from SionnaRT-Bridge, while preserving the documented
shared-scene workflow. Retain UPSTREAM.json and third-party attribution.

## Runtime and outputs

Use the pinned external requirements and a separate Python environment for each
engine. The default public workflow uses native upstream solvers. Experimental
field corrections require the documented explicit option and an isolated child
process; never install them silently or make them the default. A runtime/compiler
adapter does not establish a change in electromagnetic correctness.

Use structured subprocess argument arrays and hidden background processes on
Windows. Test with an isolated Blender profile, preserving the user's preferences
and installed environments. Keep each engine's outputs in separate directories.
Generated packages belong in dist/; exclude caches, compiler/runtime binaries,
credentials and workstation-specific paths from Git and release bundles.

## Scientific and comparison contracts

Preserve geometry and device/settings identity checks. Repeat setup copying when
the documented workflow requires it; missing or mismatched runs must remain
visible. Reuse saved outputs for presentation-only edits. Changed physical inputs
need new matching calculations.

Exported path coefficients exclude carrier propagation phase; CIR applies it
exactly once. Preserve units, polarization conventions and output schemas.
Point-receiver samples are not Sionna's surface-area estimates. Zero physical
paths are valid observations; failed workers and candidate-budget rejections
must not become zero-gain observations.

Retain native baselines, failed controls and historical evidence. Do not adjust
visibility tolerances, expected hashes or reference results just to force engine
agreement. Record source/runtime/input hashes, seeds, budgets, field profile and
numerical precision. Report dielectric discrepancies and other documented limits;
software checks do not establish universal engine equivalence, convergence,
full-wave accuracy or an end-to-end differentiable geometry pipeline.

## Validation

For code or packaging changes, run the relevant checks from the repository root:

```text
python -m pytest
python -m unittest discover -s src/differt_bridge/tests -p "test_*.py"
node src/differt_bridge/tests/test_report_math.cjs
python scripts/check_release.py
python scripts/build_extension.py
```

For Blender integration changes, follow docs/validation.md and
scripts/blender_workflow_check.py using the packaged extension in a fresh profile.
For physics/comparison changes, use the relevant documented diffraction fixtures
and controls, retaining the native baseline and explicit experimental labels.
Inspect process exits and receipts. Documentation-only changes require path and
command review, not new native simulations.

## Documentation and delivery

Update affected guides and CHANGELOG.md for user-visible changes. Keep the README
focused on installation, use and scope; put detailed evidence in the relevant
guide. Report executed checks, environment and remaining limits accurately.

For authorized releases, align package/manifest/citation versions and retain the
exact source commit, deterministic archive and SHA-256. Preserve earlier tags
and evidence. Distinguish a rebuilt package from historical workstation results.
This is a public GPL-derived project: retain provenance, authorship and licences,
and keep private scenes and bulky generated media outside Git. Push or publish
within the user's authorized task.

# Changes

## Unreleased — developer structure

- Add a documentation index, contributor guide, architecture map and research catalog.
- Add shared check/test/build commands and an isolated Blender package smoke test.
- Record a reviewable Geometry Nodes contract and validate the shipped library against it.
- Separate portable and Blender CI, with Windows and Linux coverage configured.
- Document remaining reproduction gaps; retain existing extension/scientific source bytes and historical paths.

## 0.6.3 — first public prerelease

- Separate Blender namespace, runtime preferences and result collections for DiffeRT beside SionnaRT-Bridge.
- Shared setup copying, paired workers, saved-run comparison, path diagnostics, shared receiver grids and repeated depth benchmarks.
- Float64 reconstruction and full-mesh visibility for supported reflection/diffraction chains, preserving real thin obstacles and finite-edge checks.
- Explicit passband path versus baseband CIR convention, antenna/array adaptation, coverage, motion and structured exports.
- Portable setup and generated diffraction fixtures, scientific limitations, raw evidence and isolated Sionna physics candidates.

Derived from SionnaRT-Bridge 2.1.0, commit `811c87ce3c7f352278f891fb399b510f6ad3ddb0`. Earlier 0.x workstation packages and optional runtime arithmetic-alignment experiments were local research checkpoints, not public releases. This package does not automatically apply those runtime experiments.

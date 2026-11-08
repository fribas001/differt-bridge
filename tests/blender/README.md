# Blender package checks

Run `python tools/dev.py blender --blender /path/to/blender` from the repository.
The driver builds the extension, validates it with Blender's extension command,
and starts a factory Blender 5.2 session with temporary user directories.

`check_extension.py` loads the extracted ZIP using a different package name,
checks registration, verifies the Geometry Nodes contract and public result
groups, preserves a user edit across repeated append and save/reopen, and checks
unregistration and handler cleanup. No external engine is imported or invoked.
The receipt records the actual Blender version and tested package hash under
ignored `runs/blender/receipt.json`.

This is a package/lifecycle/asset smoke test. It does not certify ray-tracing
results, visual pixel identity, full Geometry Nodes evaluation, or the user's
two installed runtimes. For end-to-end propagation checks, use the existing
[workflow runner](../../scripts/blender_workflow_check.py) with an explicit
runtime and the study-specific paired campaigns.

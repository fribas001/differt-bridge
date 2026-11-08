# Geometry Nodes development

The current authoritative asset is
[`differt_geometry_nodes.blend`](../src/differt_bridge/assets/differt_geometry_nodes.blend).
It contains the path and coverage display groups, including nested groups.
The extension appends missing groups, preserves existing user edits and
restores missing groups after loading a scene.

## Reviewable contract

[`tests/fixtures/geometry_nodes.json`](../tests/fixtures/geometry_nodes.json)
records the asset SHA-256, group names, socket identifiers/types/directions,
named attributes, node types and links. This makes structural changes visible
in Git even though the library is binary. It is a regression snapshot, not a
complete serialization: all socket defaults, shaders and visual behavior are
not represented. The asset hash detects any binary change; a reviewer must
still inspect intentional appearance/default changes.

After editing a copy of the node library in Blender 5.2 and placing the reviewed
asset back in its source location:

```sh
python tools/dev.py nodes-update --blender /path/to/blender
git diff -- tests/fixtures/geometry_nodes.json
python tools/dev.py blender --blender /path/to/blender
```

Normal checks never rewrite the expected contract. A mismatched asset hash
fails before packaging. The Blender test compares the actual node structure
loaded from the built ZIP with that contract. It also checks repeated append,
user-edit preservation, required result groups, save/reopen and registration
cleanup. See [the test scope](../tests/blender/README.md).

## Authoring rules

Treat group names, socket identifiers and result attribute names as an API.
Preserve units and domains when displaying paths, gain, power or phase. Keep
propagation geometry and visual-only geometry distinct. A display change must
not alter the obstacles passed to a ray tracer.

Molecular Nodes now generates its node library from Python sources. A similar
conversion is a useful future step here, after a round-trip test shows that
all our groups, defaults, materials and evaluated output survive conversion.
Until that test exists, the binary asset remains authoritative and versioned.

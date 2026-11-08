"""Exercise the built ZIP in factory Blender without any scientific runtime."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import tomllib
import zipfile

import bpy

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from node_contract import describe, expected


def main():
    archive, output = map(lambda value: Path(value).resolve(), sys.argv[sys.argv.index("--") + 1:])
    output.mkdir(parents=True, exist_ok=True)
    receipt = output / "receipt.json"
    receipt.write_text(json.dumps({"status": "running"}), encoding="utf-8")
    assert bpy.app.version[:2] == (5, 2), bpy.app.version_string
    contract = expected()
    before_handlers = {name: list(getattr(bpy.app.handlers, name)) for name in
                       ("load_pre", "load_post", "frame_change_post", "render_pre", "depsgraph_update_post")}
    with tempfile.TemporaryDirectory(prefix="extension-", dir=output) as directory:
        folder = Path(directory)
        with zipfile.ZipFile(archive) as source:
            # Only this freshly built project ZIP is extracted; still validate paths.
            for name in source.namelist():
                target = (folder / name).resolve()
                if not target.is_relative_to(folder):
                    raise ValueError("Archive member escapes extraction directory")
            source.extractall(folder)
        manifest = tomllib.loads((folder / "blender_manifest.toml").read_text(encoding="utf-8"))
        asset = folder / "assets/differt_geometry_nodes.blend"
        assert hashlib.sha256(asset.read_bytes()).hexdigest() == contract["sha256"]
        # An arbitrary package namespace catches fragile absolute extension imports.
        spec = importlib.util.spec_from_file_location("bridge_package_test", folder / "__init__.py",
                                                     submodule_search_locations=[str(folder)])
        bridge = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = bridge
        spec.loader.exec_module(bridge)
        bridge.register()
        try:
            assert hasattr(bpy.types.Scene, "differt_bridge")
            assert hasattr(bpy.types.Object, "differt_device_config")
            assert hasattr(bpy.types.Material, "differt_radio")
            loaded = bridge._ensure_bundled_geometry_nodes(verbose=False)
            assert loaded["status"] == "OK", loaded
            names = [item["name"] for item in contract["groups"]]
            groups = [bpy.data.node_groups[name] for name in names]
            assert describe(groups) == contract["groups"], "Node interfaces or graph structure changed"
            assert bridge._ensure_bundled_geometry_nodes(verbose=False)["loaded"] == 0
            count = len(bpy.data.node_groups)
            edited = groups[0]
            edited["test_user_edit"] = "preserve me"
            # Blender discards unreferenced datablocks when saving. Exercise an
            # actual user's node modifier, rather than an orphaned library group.
            mesh = bpy.data.meshes.new("Test result carrier")
            mesh.from_pydata([(0.0, 0.0, 0.0)], [], [])
            carrier = bpy.data.objects.new("Test result carrier", mesh)
            bpy.context.scene.collection.objects.link(carrier)
            carrier.modifiers.new("Test nodes", "NODES").node_group = edited
            bridge._ensure_bundled_geometry_nodes(verbose=False)
            assert edited["test_user_edit"] == "preserve me"
            assert len(bpy.data.node_groups) == count
            required = {bridge._DEFAULT_GEOMETRY_NODES_GROUP}
            for modes in (bridge._RADIO_MAP_MODE_DEFINITIONS, bridge._RADIO_MAP_PROJECTED_MODE_DEFINITIONS,
                          bridge._RADIO_MAP_3D_MODE_DEFINITIONS):
                required.update(item["node_group"] for item in modes.values())
            for name in required:
                group = bridge._existing_geometry_nodes_group(name, "test")
                assert group.bl_idname == "GeometryNodeTree"
                assert any(item.item_type == "SOCKET" and item.in_out == "OUTPUT" and
                           item.socket_type == "NodeSocketGeometry" for item in group.interface.items_tree), name
            # Save actual datablocks and reopen; handlers must retain user edits.
            bpy.context.preferences.filepaths.save_version = 0
            bpy.context.preferences.filepaths.file_preview_type = "NONE"
            saved = folder / "smoke.blend"
            bpy.ops.wm.save_as_mainfile(filepath=str(saved))
            bpy.ops.wm.open_mainfile(filepath=str(saved))
            assert bpy.data.node_groups[names[0]]["test_user_edit"] == "preserve me"
            assert all(bpy.data.node_groups.get(name) is not None for name in required)
        finally:
            bridge.unregister()
        assert not hasattr(bpy.types.Scene, "differt_bridge")
        assert not hasattr(bpy.types.Object, "differt_device_config")
        assert not hasattr(bpy.types.Material, "differt_radio")
        for name, handlers in before_handlers.items():
            assert list(getattr(bpy.app.handlers, name)) == handlers, name
        bridge.register()
        bridge.unregister()
        assert not bpy.app.timers.is_registered(bridge._post_register_init_timer)
        assert not any(name.split(".")[0] in {"differt", "sionna", "mitsuba", "drjit", "jax"}
                       for name in sys.modules), "Scientific engines must remain outside Blender"
    receipt.write_text(json.dumps(dict(status="passed", blender=bpy.app.version_string,
        package=archive.name, package_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
        extension_version=manifest["version"], node_groups=len(names), public_result_groups=len(required),
        checks=["built ZIP", "isolated preferences", "alternate package namespace", "node contract",
                "idempotent append", "preserved user node edits", "save and reopen", "registration lifecycle",
                "handler cleanup", "external engine isolation"]), indent=2) + "\n", encoding="utf-8")
    print("BLENDER_PACKAGE_PASS", receipt)


if __name__ == "__main__":
    main()

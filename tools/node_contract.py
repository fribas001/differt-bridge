"""Readable public interfaces and graph structure of the shipped node library.

Run inside Blender through tools/dev.py nodes-update. This is a regression
contract, not a replacement or a full serialization of the .blend source.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
CONFIG = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["bridge"]
ASSET = Path(CONFIG["source"]) / "assets/differt_geometry_nodes.blend"


def describe(groups):
    result = []
    for group in sorted(groups, key=lambda item: item.name):
        interface = []
        for item in group.interface.items_tree:
            row = dict(name=item.name, kind=item.item_type,
                       parent=item.parent.name if item.parent else None)
            if item.item_type == "SOCKET":
                row.update(identifier=item.identifier, direction=item.in_out, socket_type=item.socket_type)
            interface.append(row)
        nodes = []
        for node in sorted(group.nodes, key=lambda item: item.name):
            row = dict(name=node.name, type=node.bl_idname)
            if getattr(node, "node_tree", None):
                row["group"] = node.node_tree.name
            if node.bl_idname in {"GeometryNodeInputNamedAttribute", "GeometryNodeStoreNamedAttribute"}:
                row["attribute"] = node.inputs["Name"].default_value
                row["data_type"] = node.data_type
            nodes.append(row)
        links = sorted([link.from_node.name, link.from_socket.identifier,
                        link.to_node.name, link.to_socket.identifier] for link in group.links)
        result.append(dict(name=group.name, type=group.bl_idname, interface=interface,
                           nodes=nodes, links=links))
    return result


def load(bpy, asset):
    with bpy.data.libraries.load(str(asset), link=False) as (source, target):
        target.node_groups = list(source.node_groups)
    return [group for group in target.node_groups if group is not None]


def expected():
    return json.loads((ROOT / CONFIG["asset_contract"]).read_text(encoding="utf-8"))


def main():
    import bpy
    if "--update" not in sys.argv:
        raise SystemExit("Use tools/dev.py nodes-update to explicitly update the contract")
    if bpy.app.version[:2] != (5, 2):
        raise RuntimeError("Regenerate the contract with Blender 5.2")
    if bpy.data.node_groups:
        raise RuntimeError("The node contract must be generated in a clean Blender session")
    asset = ROOT / ASSET
    result = dict(schema_version=1, asset=ASSET.as_posix(),
                  sha256=hashlib.sha256(asset.read_bytes()).hexdigest(),
                  blender_series=CONFIG["blender_series"], groups=describe(load(bpy, asset)))
    path = ROOT / CONFIG["asset_contract"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("NODE_CONTRACT_WRITTEN", path, len(result["groups"]), "groups")


if __name__ == "__main__":
    main()

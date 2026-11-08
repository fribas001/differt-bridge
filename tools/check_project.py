"""Check the contributor-facing structure without importing Blender or engines."""
import ast
import hashlib
import json
from pathlib import Path
import re
import tomllib
from urllib.parse import unquote, urlsplit

from research import catalog

ROOT = Path(__file__).resolve().parents[1]


def project_file(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("Missing or invalid project file: " + name)
    return path


def check_asset(root, contract):
    if contract["schema_version"] != 1:
        raise ValueError("Unsupported Geometry Nodes contract")
    asset = project_file(root, contract["asset"])
    if hashlib.sha256(asset.read_bytes()).hexdigest() != contract["sha256"]:
        raise ValueError("Node library changed: inspect the asset, regenerate its contract, and run Blender checks")
    names = [group["name"] for group in contract["groups"]]
    if not names or len(names) != len(set(names)):
        raise ValueError("Empty or duplicated node-group contract")


def check_links(root):
    pages = [root / "README.md", root / "CONTRIBUTING.md"]
    pages += sorted((root / "docs").rglob("*.md"))
    pages += sorted((root / "research").rglob("*.md"))
    pages += sorted((root / "tests/blender").glob("*.md"))
    for page in pages:
        for link in re.findall(r"\[[^\]]*\]\(([^\s)]+)(?:\s+[^)]*)?\)", page.read_text(encoding="utf-8")):
            target = urlsplit(link.strip("<>"))
            if target.scheme or target.netloc or not target.path:
                continue
            resolved = (page.parent / unquote(target.path)).resolve()
            if not resolved.is_relative_to(root.resolve()) or not resolved.exists():
                raise ValueError(f"Broken documentation link in {page.relative_to(root)}: {link}")


def main():
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["bridge"]
    manifest = tomllib.loads(project_file(ROOT, config["source"] + "/blender_manifest.toml").read_text(encoding="utf-8"))
    if not manifest["blender_version_min"].startswith(config["blender_series"] + "."):
        raise ValueError("Blender test series and extension minimum disagree")
    contract = json.loads(project_file(ROOT, config["asset_contract"]).read_text(encoding="utf-8"))
    check_asset(ROOT, contract)
    studies = catalog(ROOT)
    ids = [study["id"] for study in studies]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate study IDs")
    for study in studies:
        if study["portability"] not in {"generated-fixtures", "workspace-study"}:
            raise ValueError("Unrecognized portability state")
        project_file(ROOT, study["report"])
        for name in study["entrypoints"]:
            project_file(ROOT, name)
        for name in study["prerequisites"]:
            if not (ROOT / name).resolve().is_relative_to(ROOT):
                raise ValueError("Prerequisite path escapes the workspace")
    for path in (ROOT / "tools").rglob("*.py"):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    check_links(ROOT)
    print(f"Project structure passed: {len(studies)} studies, {len(contract['groups'])} node groups, local documentation links")


if __name__ == "__main__":
    main()

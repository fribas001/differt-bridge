"""Navigate studies and identify declared missing workspace prerequisites.

This command does not install profiles, run expensive solvers, or certify
reproducibility. Scientific runners retain their own hash/acceptance gates.
"""
import argparse
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def catalog(root=ROOT):
    config = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["bridge"]
    data = tomllib.loads((root / config["study_catalog"]).read_text(encoding="utf-8"))
    if data["schema_version"] != 1:
        raise ValueError("Unsupported study catalog version")
    return data["study"]


def missing_prerequisites(study, workspace):
    workspace = workspace.resolve()
    missing = []
    for name in study["prerequisites"]:
        path = (workspace / name).resolve()
        if not path.is_relative_to(workspace):
            raise ValueError("Prerequisite escapes workspace: " + name)
        if not path.is_file():
            missing.append(name)
    return missing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("study", nargs="?", help="Study ID; omit to list all studies")
    parser.add_argument("--workspace", type=Path, help="Check declared prerequisites under this workspace")
    args = parser.parse_args()
    studies = catalog()
    if args.study is None:
        if args.workspace:
            parser.error("Choose a study when checking a workspace")
        for study in studies:
            print(f"{study['id']:24} {study['portability']:20} {study['title']}")
        return
    match = next((study for study in studies if study["id"] == args.study), None)
    if match is None:
        parser.error("Unknown study ID")
    print(match["title"])
    print("Portability:", match["portability"])
    print("Report:", match["report"])
    print("Entry points (see report for order and arguments):")
    for name in match["entrypoints"]:
        print(" ", name)
    if args.workspace:
        if not match["prerequisites"] and match["portability"] == "workspace-study":
            print("Prerequisite inventory is incomplete. Consult the study report and original evidence.")
            raise SystemExit(2)
        missing = missing_prerequisites(match, args.workspace)
        for name in missing:
            print("MISSING:", name)
        print("Presence check only; this does not validate contents, all transitive inputs, or runtime profiles.")
        if missing:
            raise SystemExit(2)
        print("Declared prerequisites present.")


if __name__ == "__main__":
    main()

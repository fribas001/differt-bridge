"""Developer commands, independent of the installed Blender/engine environments."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib

ROOT = Path(__file__).resolve().parents[1]
CONFIG = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["bridge"]
SOURCE = ROOT / CONFIG["source"]


def run(*command, env=None):
    print("Running:", " ".join(map(str, command)), flush=True)
    subprocess.run(list(map(str, command)), cwd=ROOT, env=env, check=True)


def python(script, *arguments, env=None):
    run(sys.executable, "-B", ROOT / script, *arguments, env=env)


def check():
    python("scripts/check_release.py")
    python("tools/check_project.py")


def build():
    check()
    python("scripts/build_extension.py")
    manifest = tomllib.loads((SOURCE / "blender_manifest.toml").read_text(encoding="utf-8"))
    return ROOT / "dist" / f"{manifest['id']}-{manifest['version']}.zip"


def test(node):
    check()
    temp_root = ROOT / "runs" / "tests"
    temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="check-", dir=temp_root) as directory:
        env = dict(os.environ, TEMP=directory, TMP=directory, TMPDIR=directory,
                   PYTHONDONTWRITEBYTECODE="1", OPENBLAS_NUM_THREADS="1")
        run(sys.executable, "-B", "-m", "pytest", "--basetemp", Path(directory) / "pytest", env=env)
        run(sys.executable, "-B", "-m", "unittest", "discover", "-s",
            SOURCE / "tests", "-p", "test_*.py", env=env)
        run(node, SOURCE / "tests/test_report_math.cjs", env=env)


def blender(executable, update_nodes=False):
    resolved = shutil.which(executable)
    if resolved is None:
        raise FileNotFoundError(f"Blender executable not found: {executable}")
    output = ROOT / "runs" / "blender"
    output.mkdir(parents=True, exist_ok=True)
    # Each invocation gets a clean profile. Never load/save the user's preferences.
    with tempfile.TemporaryDirectory(prefix="profile-", dir=output) as directory:
        env = dict(os.environ, PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1")
        env.pop("PYTHONPATH", None)
        for variable, folder in (("BLENDER_USER_CONFIG", "config"),
                                 ("BLENDER_USER_SCRIPTS", "scripts"),
                                 ("BLENDER_USER_EXTENSIONS", "extensions"),
                                 ("TEMP", "temp"), ("TMP", "temp"), ("TMPDIR", "temp")):
            path = Path(directory) / folder
            path.mkdir(exist_ok=True)
            env[variable] = str(path)
        common = [resolved, "--background", "--factory-startup"]
        if update_nodes:
            run(*common, "--python-exit-code", "1", "--python",
                ROOT / "tools/node_contract.py", "--", "--update", env=env)
            return
        archive = build()
        run(*common, "--command", "extension", "validate", archive, env=env)
        run(*common, "--python-exit-code", "1", "--python",
            ROOT / "tests/blender/check_extension.py", "--", archive, output, env=env)
        receipt = json.loads((output / "receipt.json").read_text(encoding="utf-8"))
        if receipt["status"] != "passed":
            raise RuntimeError("Blender checks did not complete")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", help="Check packaging, documentation, research catalog and node asset hash")
    commands.add_parser("build", help="Check and build the deterministic extension ZIP")
    tests = commands.add_parser("test", help="Run portable Python and report JavaScript tests")
    tests.add_argument("--node", default="node")
    for name in ("blender", "nodes-update"):
        command = commands.add_parser(name, help="Check the built extension" if name == "blender" else
                                       "Explicitly regenerate the reviewable Geometry Nodes contract")
        command.add_argument("--blender", default="blender", help="Blender 5.2 executable")
    args = parser.parse_args()
    if args.command == "check":
        check()
    elif args.command == "build":
        build()
    elif args.command == "test":
        test(args.node)
    else:
        blender(args.blender, update_nodes=args.command == "nodes-update")


if __name__ == "__main__":
    main()

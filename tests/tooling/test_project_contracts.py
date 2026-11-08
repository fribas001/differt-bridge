"""Reject stale node evidence and missing/escaping research inputs."""
import hashlib
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from check_project import check_asset
from research import missing_prerequisites


def test_changed_library_requires_explicit_contract_review(tmp_path):
    asset = tmp_path / "nodes.blend"
    asset.write_bytes(b"original asset")
    contract = dict(schema_version=1, asset="nodes.blend",
                    sha256=hashlib.sha256(asset.read_bytes()).hexdigest(), groups=[dict(name="paths")])
    check_asset(tmp_path, contract)
    asset.write_bytes(b"changed asset")
    with pytest.raises(ValueError, match="Node library changed"):
        check_asset(tmp_path, contract)


def test_missing_reference_is_not_reported_as_available(tmp_path):
    study = dict(prerequisites=["reference/config.json", "reference/mode.npz"])
    (tmp_path / "reference").mkdir()
    (tmp_path / "reference/config.json").write_text("{}")
    assert missing_prerequisites(study, tmp_path) == ["reference/mode.npz"]


@pytest.mark.parametrize("name", ["../outside.json", "a/../../outside.json"])
def test_prerequisite_cannot_escape_workspace(tmp_path, name):
    with pytest.raises(ValueError, match="escapes workspace"):
        missing_prerequisites(dict(prerequisites=[name]), tmp_path)

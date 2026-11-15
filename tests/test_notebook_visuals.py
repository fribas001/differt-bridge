"""Check that figures remain tied to their original geometry and comparison scope."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('notebook_visuals', ROOT / 'notebooks/visuals.py')
visuals = importlib.util.module_from_spec(spec)
spec.loader.exec_module(visuals)


def test_visual_integrity_and_corruption(tmp_path):
    manifest = visuals.verify_assets()
    assert {e['path'] for e in manifest['files']} == {
        p.name for p in visuals.ASSETS.iterdir() if p.name not in ('README.md', 'manifest.json')}
    original = [e for e in manifest['files'] if e['kind'] == 'historical-figure']
    assert len(original) == 3
    assert all(e['sha256'] == e['source_sha256'] for e in original)
    copied = tmp_path / 'assets'
    shutil.copytree(visuals.ASSETS, copied)
    (copied / 'models.json').write_bytes(b'{}')
    with pytest.raises(ValueError, match='integrity'):
        visuals.verify_assets(copied)


def test_paired_renders_use_same_camera_geometry_and_original_paths():
    models_path = visuals.ASSETS / 'models.json'
    models = json.loads(models_path.read_text())['models']
    assert len(models) == 22
    assert not any('actual_' in name for name in models)
    model = models['multiple/blocked_coupled']
    for route in model['paths']:
        # Retained native paths include float32 endpoints; plan coordinates are decimal.
        assert route['points'][0] == pytest.approx(model['tx'], rel=0, abs=1e-7)
        assert route['points'][-1] == pytest.approx(model['rx'], rel=0, abs=1e-7)
        assert len(route['points']) == len(route['events']) + 2
    assert model['paths'][0]['events'] == ['D']
    assert model['paths'][1]['events'] == ['D', 'D']
    pair = [json.loads((visuals.ASSETS / f'blocked_{name}.json').read_text())
            for name in ('sionna', 'differt')]
    assert pair[0]['camera'] == pair[1]['camera']
    for i, receipt in enumerate(pair):
        assert receipt['case'] == 'multiple/blocked_coupled'
        assert receipt['geometry_sha256'] == hashlib.sha256(models_path.read_bytes()).hexdigest()
        assert receipt['path_label'] == model['paths'][i]['label']
        assert receipt['renderer_sha256'] == hashlib.sha256((ROOT / 'notebooks/blender_render.py').read_bytes()).hexdigest()


def test_model_units_and_selected_control_dimensions():
    models = json.loads((visuals.ASSETS / 'models.json').read_text())['models']
    assert all(m['units'] == 'm' for m in models.values())
    leaf, branch = models['focused/leaf_branch']['shapes']
    def extent(shape, axis):
        values = [v[axis] for v in shape['vertices']]
        return max(values) - min(values)
    assert [extent(leaf, i) for i in range(3)] == pytest.approx([0, .08, .12])
    assert [extent(branch, i) for i in range(3)] == pytest.approx([.02, .02, .2])
    assert models['focused/leaf_branch']['radio_materials']['leaf']['d'] == .0002
    for model in models.values():
        for shape in model['shapes']:
            assert all(len(face) == 3 and all(0 <= i < len(shape['vertices']) for i in face)
                       for face in shape['triangles'])

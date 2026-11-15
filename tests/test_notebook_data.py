"""Protect scientific interpretation and integrity of the replay supplement."""
import importlib.util
import json
import math
from pathlib import Path
import shutil

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('notebook_replay', ROOT / 'notebooks/replay.py')
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)


def test_all_bundled_inputs_retain_original_bytes():
    manifest = replay.verify_data()
    assert len(manifest['files']) == 13
    assert all(e['sha256'] == e['source_sha256'] for e in manifest['files'])
    actual = {p.relative_to(replay.DATA).as_posix() for p in replay.DATA.rglob('*')
              if p.is_file() and p.name not in ('manifest.json', 'README.md')}
    assert actual == {e['path'] for e in manifest['files']}


def test_corrupt_input_is_rejected_before_analysis(tmp_path):
    target = tmp_path / 'data'
    shutil.copytree(replay.DATA, target)
    path = target / 'ris_controls_23_8ghz/rt_comparison.csv'
    path.write_bytes(path.read_bytes().replace(b'False', b'True', 1))
    with pytest.raises(ValueError, match='integrity'):
        replay.verify_data(target)


def test_source_links_and_numerical_values_survive_path_redaction():
    source = ROOT / 'scripts/prepare_notebook_data.py'
    importer_spec = importlib.util.spec_from_file_location('data_importer', source)
    importer = importlib.util.module_from_spec(importer_spec)
    importer_spec.loader.exec_module(importer)
    original = {'url': 'https://docs.openems.de/en/latest/concepts/excitations.html',
                'local': 'D:/archived-work/results.json', 'field': [0.25, -3.5]}
    redactions = []
    clean = importer.sanitize(original, redactions)
    assert clean['url'] == original['url']
    assert clean['field'] == original['field']
    assert clean['local'] == '<historical-path>/results.json'
    assert len(redactions) == 1


def test_missing_geometry_results_are_not_zero_error_controls():
    rows = replay.read_csv('ris_controls_23_8ghz/rt_comparison.csv')
    ideal = [r for r in rows if r['diagnostic'] == 'False']
    failed = [r for r in rows if r['diagnostic'] == 'True']
    assert len(ideal) == 14 and all(r['passed'] == 'True' for r in ideal)
    assert len(failed) == 12 and all(r['passed'] == 'False' for r in failed)
    assert all(r['solver_power_difference_db'] == '' for r in failed)
    assert max(abs(float(r['solver_power_difference_db'])) for r in ideal) < 0.00019
    assert not replay.read_json('ris_controls_23_8ghz/verification.json')['production_acceptance']


def test_fullwave_errors_recompute_and_failed_physical_limit_survives():
    data = replay.read_json('edge_fullwave_60ghz/analysis.json')
    for row in data['rows']:
        field = complex(*row['fdtd_ratio'])
        assert -20 * math.log10(abs(field)) == pytest.approx(row['fdtd_loss_db'], abs=1e-10)
        for engine in ('sionna', 'differt'):
            assert row[f'{engine}_loss_db'] - row['fdtd_loss_db'] == pytest.approx(
                row[f'{engine}_loss_error_db'], abs=1e-10)
    receipt = replay.read_json('edge_fullwave_60ghz/verification.json')
    assert receipt['numerical_gates_passed']
    assert receipt['transparent_material_consistency'] is False


def test_notebooks_default_to_offline_replay():
    paths = list((ROOT / 'notebooks').glob('[0-9][0-9]_*.ipynb'))
    assert len(paths) == 5
    for path in paths:
        notebook = json.loads(path.read_text(encoding='utf-8'))
        assert not notebook['metadata']['differt_bridge']['simulations_default']
        code = '\n'.join(''.join(c['source']) for c in notebook['cells'] if c['cell_type'] == 'code')
        if 'subprocess.run' in code:
            assert 'RUN_NATIVE = False' in code and 'if RUN_NATIVE:' in code
        if 'render_model(' in code:
            assert 'RENDER_LIVE = False' in code and 'if RENDER_LIVE:' in code
        assert all(not c.get('outputs') for c in notebook['cells'])

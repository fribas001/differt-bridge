"""Safety boundaries for release recovery; no scientific engines imported."""
import importlib.util
import json
from pathlib import Path
import pytest

SOURCE=Path(__file__).resolve().parents[1]/'reproduction/project/replay.py'
spec=importlib.util.spec_from_file_location('project_replay',SOURCE)
replay=importlib.util.module_from_spec(spec);spec.loader.exec_module(replay)

def test_paths_cannot_escape(tmp_path):
    with pytest.raises(ValueError,match='escapes'):
        replay.inside(tmp_path,'../outside')

def test_verify_rejects_changed_payload(tmp_path,monkeypatch):
    monkeypatch.setattr(replay,'ROOT',tmp_path)
    p=tmp_path/'payload';p.write_bytes(b'original')
    (tmp_path/'_manifests').mkdir()
    (tmp_path/'_manifests/test.json').write_text(json.dumps({'files':{'payload':{'bytes':8,'sha256':replay.sha(p)}}}))
    assert replay.verify()==1
    p.write_bytes(b'modified')
    with pytest.raises(ValueError,match='changed'):replay.verify()

def test_environment_drops_external_python_and_llvm(tmp_path,monkeypatch):
    monkeypatch.setattr(replay,'ROOT',tmp_path)
    monkeypatch.setenv('SystemRoot',str(tmp_path/'Windows'))
    monkeypatch.setenv('PYTHONPATH','foreign-packages')
    monkeypatch.setenv('DRJIT_LIBLLVM_PATH','foreign-adapter')
    env=replay.environment('phase')
    assert 'PYTHONPATH' not in env and 'DRJIT_LIBLLVM_PATH' not in env
    assert env['RADIO_RT22_PROFILE']=='phase'
    assert env['DIFFERT_ARITHMETIC_PROFILE']=='sionna_order'

def test_rt_children_always_bootstrap():
    args=replay.rt_command(['worker.py','--input','a b.json'],'reciprocal')
    assert args[1:5]==['-I','-B','-m','codex_sionna_runtime']
    assert args[6:9]==['--profile','reciprocal','--']
    assert args[-3:]==['worker.py','--input','a b.json']

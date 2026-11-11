"""Recovery safety checks using small temporary files, without engine imports."""
import hashlib,importlib.util,json
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('rt21_recovery',Path(__file__).resolve().parents[1]/'reproduction/rt21/recover.py')
recovery=importlib.util.module_from_spec(spec);spec.loader.exec_module(recovery)

def test_recovery_paths_cannot_escape(tmp_path):
    assert recovery.inside(tmp_path,'data/fixture.json').is_relative_to(tmp_path)
    with pytest.raises(ValueError,match='escapes'):recovery.inside(tmp_path,'../outside')

@pytest.mark.parametrize('damage',['missing','changed'])
def test_manifest_rejects_lost_or_changed_payload(tmp_path,monkeypatch,damage):
    monkeypatch.setattr(recovery,'ROOT',tmp_path)
    data=b'original';p=tmp_path/'fixture.txt';p.write_bytes(data)
    (tmp_path/'MANIFEST.json').write_text(json.dumps(dict(schema=1,files={'fixture.txt':dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())})))
    recovery.verify()
    if damage=='missing':p.unlink()
    else:p.write_bytes(b'modified')
    with pytest.raises(ValueError,match='changed recovery payload'):recovery.verify()

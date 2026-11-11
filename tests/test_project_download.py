import hashlib,importlib.util
from pathlib import Path
import pytest
SOURCE=Path(__file__).resolve().parents[1]/'reproduction/project/fetch.py'
spec=importlib.util.spec_from_file_location('project_fetch',SOURCE)
fetch=importlib.util.module_from_spec(spec);spec.loader.exec_module(fetch)
def row(name,data):return {'name':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
def test_join_is_byte_identical(tmp_path):
    cache=tmp_path/'cache';cache.mkdir();data=b'first'+b'second';parts=[row('a',b'first'),row('b',b'second')]
    (cache/'a').write_bytes(b'first');(cache/'b').write_bytes(b'second')
    target=fetch.assemble({**row('joined.zip',data),'parts':parts},cache,tmp_path)
    assert target.read_bytes()==data and not (cache/'a').exists()
def test_changed_part_is_rejected(tmp_path):
    cache=tmp_path/'cache';cache.mkdir();(cache/'a').write_bytes(b'changed')
    with pytest.raises(ValueError,match='integrity'):
        fetch.assemble({**row('out.zip',b'original'),'parts':[row('a',b'original')]},cache,tmp_path)
    assert not (tmp_path/'out.zip').exists()
@pytest.mark.parametrize('name',['../escape','C:escape','folder\\file','/absolute','..'])
def test_reject_unsafe_names(name):
    with pytest.raises(ValueError):fetch.filename(name)

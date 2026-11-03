import ast,tomllib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'src/differt_bridge'

def test_manifest_is_complete_and_no_sionna_runtime_imports():
    manifest=tomllib.loads((SOURCE/'blender_manifest.toml').read_text(encoding='utf-8'))
    assert manifest['id']=='differt_bridge'
    assert manifest['blender_version_min']=='5.2.0'
    assert 'differt_backend.py' in manifest['build']['paths']
    for relative in manifest['build']['paths']:
        assert (SOURCE/relative).is_file(),relative
    for path in SOURCE.rglob('*.py'):
        tree=ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            modules=([node.module] if isinstance(node,ast.ImportFrom) else
                     [a.name for a in node.names] if isinstance(node,ast.Import) else [])
            assert all((m or '').split('.')[0] not in {'sionna','mitsuba','drjit'} for m in modules),path

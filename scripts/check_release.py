"""Portable package, version and accidentally included workstation-data checks."""
import ast,re,tomllib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];SRC=ROOT/'src/differt_bridge'
manifest=tomllib.loads((SRC/'blender_manifest.toml').read_text())
assert manifest['version']=='0.6.3' and manifest['id']=='differt_bridge'
assert re.search(r'^_ADDON_VERSION\s*=\s*[\"\']0\.6\.3[\"\']',(SRC/'__init__.py').read_text(),re.M)
assert 'version: 0.6.3' in (ROOT/'CITATION.cff').read_text()
for name in manifest['build']['paths']:assert (SRC/name).is_file(),name
for folder in (SRC,ROOT/'scripts',ROOT/'tests'):
    for p in folder.rglob('*.py'):
        if '__pycache__' not in p.parts:ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
for p in ROOT.rglob('*'):
    if not p.is_file() or any(x in p.parts for x in ('.git','.venv','runs','dist','build','__pycache__','.pytest_cache')):continue
    if p.suffix in ('.py','.md','.json','.toml','.yml','.ps1','.txt'):
        text=p.read_text(encoding='utf-8-sig')
        assert not re.search(r'C:[/\\]+Users[/\\]+feolr',text,re.I),p
        assert not re.search(r'gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}',text),p
print('Portable source, package contents, versions and workstation-path checks passed.')

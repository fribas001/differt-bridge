"""Import/version checks only. Never trace paths, perform JIT arithmetic or solve fields."""
import importlib, json, os, site, sys
from importlib.metadata import version
from pathlib import Path

engine,root,profile=sys.argv[1:];root=Path(root).resolve()
assert Path(sys.prefix).is_relative_to(root/'workspace/work')
assert Path(sys.base_prefix).resolve()==root/'vendor/python312'
assert not site.ENABLE_USER_SITE
spec=json.loads((root/'runtime_payload'/engine/'spec.json').read_text())
expected={k:v['version'] for k,v in spec['packages'].items()} if engine=='differt' else spec['packages']
actual={name:version(name) for name in expected}
assert actual==expected,(actual,expected)
names=['numpy','scipy','h5py','differt','jax','matplotlib','PIL'] if engine=='differt' else ['numpy','scipy','h5py','mitsuba','sionna.rt','drjit','codex_sionna_runtime']
for name in names:
    module=importlib.import_module(name)
    if getattr(module,'__file__',None):assert Path(module.__file__).resolve().is_relative_to(Path(sys.prefix))
if engine=='rt22':
    import mitsuba as mi
    assert mi.variant()=='llvm_ad_mono_polarized'
if engine=='differt' and profile=='reciprocal':
    import radio_dielectric_bootstrap
    # Activation is lazy and targets the Blender backend, not differt itself.
    # Import the archived backend to exercise the real guarded installation.
    sys.path.insert(0,str(root/'extensions/differt_bridge'))
    import differt_backend
    assert 'reciprocal_corrections' in sys.modules
record={'passed':True,'engine':engine,'profile':profile,'versions':actual,'isolated':True,'simulations_run':False}
path=root/'local'/('probe-'+engine+'-'+profile+'.json');path.write_text(json.dumps(record,indent=2)+'\n')
print('IMPORT_PROBE_PASS',engine,profile,flush=True)

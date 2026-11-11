"""Import/version/adapter checks only: no PathSolver, JIT arithmetic or fields."""
import importlib.metadata as md,json,os,sys
from pathlib import Path
root=Path(sys.argv[1]).resolve();out=Path(sys.argv[2])
assert Path(sys.prefix).resolve().is_relative_to(root/'local')
assert Path(sys.base_prefix).resolve().is_relative_to(root/'vendor')
assert not __import__('site').ENABLE_USER_SITE
import numpy,scipy,h5py,mitsuba as mi
mi.set_variant('llvm_ad_mono_polarized')
import drjit as dr,sionna.rt as rt
versions={p:md.version(p) for p in ('sionna-rt','drjit','mitsuba','numpy','scipy','h5py')}
assert versions=={'sionna-rt':'2.1.0','drjit':'1.5.0','mitsuba':'3.9.1','numpy':'2.5.2','scipy':'1.18.1','h5py':'3.16.0'}
for module in (numpy,scipy,h5py,mi,dr,rt):assert Path(module.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
adapter=dr._bridge_llvm_batch_status
assert adapter['status']=='enabled' and Path(adapter['original_llvm']).resolve()==root/'vendor/llvm/LLVM-C.dll'
if os.environ['RADIO_DIELECTRIC_PROFILE']=='reciprocal':
    import reciprocal_corrections
    assert reciprocal_corrections._INSTALLED['sionna']['profile']=='reciprocal'
from sionna.rt.path_solvers._bridge_geometry import geometry_profile
from sionna.rt.path_solvers._bridge_segment_policy import segment_profile
out.write_text(json.dumps(dict(passed=True,versions=versions,python=sys.version,base_prefix=sys.base_prefix,
    prefix=sys.prefix,variant=mi.variant(),geometry=geometry_profile(),segments=segment_profile(),
    dielectric=os.environ['RADIO_DIELECTRIC_PROFILE'],adapter=adapter,simulations_run=False),indent=2)+'\n')
print('IMPORT_ONLY_PROBE_PASS',versions)

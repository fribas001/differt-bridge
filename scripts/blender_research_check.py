"""Fresh paired scene run; writes separate evidence and never saves source scenes."""
import hashlib,importlib,json,os,sys,time
from pathlib import Path
import bpy

root,out,profile,runtime=sys.argv[sys.argv.index('--')+1:]
if runtime!='shared':raise RuntimeError('Legacy Blender checks are retired; use the isolated RT 2.1 recovery kit.')
root=Path(root).resolve();out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(Path(__file__).resolve().parent))
from shared_sionna import DEFAULT_PYTHON,attach_bridge
scene_file=root/'outputs/differt-bridge/examples'/('segment_length_aligned/Shared_Segment_Length_Workbench.blend' if profile=='phase' else 'diffraction_batch/Diffraction_Workbench.blend')
scene_hash=hashlib.sha256(scene_file.read_bytes()).hexdigest()
bpy.ops.wm.open_mainfile(filepath=str(scene_file))
s=importlib.import_module('bl_ext.user_default.sionnart_bridge');d=importlib.import_module('bl_ext.user_default.differt_bridge')
scene=bpy.context.scene
if runtime=='shared':attach_bridge(s)
for engine in ('sionna','differt'):
    settings=getattr(scene,engine+'_bridge');settings.runtime_mode='EXTERNAL'
    python=DEFAULT_PYTHON if engine=='sionna' and runtime=='shared' else root/'work'/('runtime' if engine=='differt' else 'sionna-runtime')/'Scripts/python.exe'
    setattr(settings,engine+'_python',str(python));settings.workspace_dir=str(out/engine)
if runtime=='shared':
    assert bpy.ops.sionna_bridge.test_environment()=={'FINISHED'},scene.sionna_bridge.last_status
    probe=json.loads(scene.sionna_bridge.runtime_probe_json)
    assert probe['sionna_rt']=='2.2.0' and probe['variant']=='llvm_ad_mono_polarized',probe
assert bpy.ops.differt_bridge.run_comparison()=={'FINISHED'}
deadline=time.monotonic()+1200
while d._comparison.active():
    assert time.monotonic()<deadline,scene.differt_bridge.comparison_status
    d._comparison.tick();time.sleep(.1)
assert scene.differt_bridge.comparison_status.startswith('Comparison ready:'),scene.differt_bridge.comparison_status
folder=Path(scene.differt_bridge.comparison_report).parent
diagnostics=json.loads((folder/'path_diagnostics.json').read_text())
phases=[r['delta_phase_rad'] for r in diagnostics['rows'] if r['delta_phase_rad'] is not None]
assert hashlib.sha256(scene_file.read_bytes()).hexdigest()==scene_hash
result=dict(profile=profile,runtime=runtime,counts=diagnostics['counts'],maximum_phase_difference_rad=max(map(abs,phases),default=None),
            report=str(folder),scene_source=str(scene_file),scene_sha256=scene_hash,saved_source_scene=False)
(out/'checks.json').write_text(json.dumps(result,indent=2));print('RESEARCH_CHECK',json.dumps(result),flush=True)
if profile=='phase':
    assert diagnostics['counts']['matched']==1299,diagnostics['counts']
    assert max(map(abs,phases))==0.,result
else:
    assert diagnostics['counts']=={'matched':3},diagnostics['counts']
    assert max(map(abs,phases))<=1e-4,result


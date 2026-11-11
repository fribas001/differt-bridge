"""Load existing Blender workbenches and inspect dispatch without simulations."""
import hashlib,importlib,json,os,runpy,sys
from pathlib import Path
from types import SimpleNamespace
import bpy
root,out=map(Path,sys.argv[sys.argv.index('--')+1:]);root=root.resolve();out=out.resolve()
scripts=Path(__file__).resolve().parent;sys.path.insert(0,str(scripts))
from check_research_workflow import profile_environment
from shared_sionna import DEFAULT_PYTHON,BridgeSubprocess
rows=[]
for profile,name in [('native','segment_length_aligned/Native_Float32_Workbench.blend'),
                     ('phase','segment_length_aligned/Shared_Segment_Length_Workbench.blend'),
                     ('reciprocal','diffraction_batch/Diffraction_Workbench.blend')]:
    path=root/'outputs/differt-bridge/examples'/name;before=hashlib.sha256(path.read_bytes()).hexdigest()
    os.environ.update(profile_environment(profile))
    bpy.ops.wm.open_mainfile(filepath=str(path))
    runpy.run_path(str(scripts/'blender_shared_runtime.py'),run_name='__main__')
    scene=bpy.context.scene;s=scene.sionna_bridge;d=scene.differt_bridge
    assert s.runtime_mode=='EXTERNAL' and Path(s.sionna_python)==DEFAULT_PYTHON
    assert Path(d.differt_python).resolve()==root/'work/runtime/Scripts/python.exe'
    addon=importlib.import_module('bl_ext.user_default.sionnart_bridge')
    assert isinstance(addon.subprocess,BridgeSubprocess)
    calls=[];fake=BridgeSubprocess(SimpleNamespace(run=lambda *a,**kw:calls.append((a,kw))))
    fake.run([str(DEFAULT_PYTHON),'worker.py','--config','scene inputs.json'])
    argv=calls[0][0][0]
    assert argv[:5]==[str(DEFAULT_PYTHON),'-I','-B','-m','codex_sionna_runtime']
    if profile!='native':assert argv[6:9]==['--profile',profile,'--']
    assert 'DRJIT_LIBLLVM_PATH' not in calls[0][1]['env']
    assert hashlib.sha256(path.read_bytes()).hexdigest()==before
    rows.append(dict(profile=profile,scene_sha256=before,shared_runtime_selected=True,
                     differt_runtime_retained=True,dispatch_checked_without_execution=True))
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(dict(passed=True,checks=rows,simulations_run=False,scenes_saved=False),indent=2))
print('BLENDER_RETIREMENT_CHECK_PASS',flush=True)

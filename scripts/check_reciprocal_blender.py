"""Fresh comparison through the saved workbench and both installed extensions."""
import importlib,json,sys,time,os
from pathlib import Path
import addon_utils,bpy

args=sys.argv[sys.argv.index('--')+1:];root,scratch,output=(Path(p).resolve() for p in args)
activation=scratch/'activation';activation.mkdir(parents=True,exist_ok=True)
os.environ['RADIO_DIELECTRIC_RECEIPT']=str(activation)
bridges={e:importlib.import_module('bl_ext.user_default.'+n) for e,n in [('sionna','sionnart_bridge'),('differt','differt_bridge')]}
for b in bridges.values():assert addon_utils.check(b.__name__)==(True,True)
d=bridges['differt'];prefs=d._runtime_preferences.preferences()
saved={k:getattr(prefs,k) for k in ('sionna_python','differt_python','llvm_library','workspace_root')}
bpy.ops.wm.open_mainfile(filepath=str(root/'outputs/differt-bridge/examples/diffraction_batch/Diffraction_Workbench.blend'))
scene=bpy.context.scene
for e in bridges:
    settings=getattr(scene,e+'_bridge');settings.workspace_dir=str(scratch/'runs'/e)
    assert settings.runtime_mode=='EXTERNAL' and Path(getattr(settings,e+'_python')).is_file()
assert bpy.ops.differt_bridge.run_comparison()=={'FINISHED'}
deadline=time.monotonic()+1200
while d._comparison.active():
    if time.monotonic()>deadline:raise TimeoutError('Blender comparison')
    d._comparison.tick();time.sleep(.1)
settings=scene.differt_bridge
assert settings.comparison_status.startswith('Comparison ready:'),settings.comparison_status
diag=json.loads((Path(settings.comparison_report).parent/'path_diagnostics.json').read_text())
assert diag['counts'].get('matched',0)>0
assert saved=={k:getattr(prefs,k) for k in saved}
activated={e:json.loads((activation/(e+'_profile.json')).read_text())['profile']=='reciprocal' for e in bridges}
assert all(activated.values()),('Missing worker activation receipts',activated)
result=dict(status='passed',blender=bpy.app.version_string,both_extensions_enabled=True,preferences_preserved=True,
            fresh_external_workers=True,activated=activated,counts=diag['counts'],comparison_report=settings.comparison_report,
            max_phase_difference_rad=max((abs(r['delta_phase_rad']) for r in diag['rows'] if r['delta_phase_rad'] is not None),default=None))
output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2));print('RECIPROCAL_BLENDER_PASS',json.dumps(result))

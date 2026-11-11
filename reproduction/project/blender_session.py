"""Configure a clean Blender session using recovered external workers; no saves/solves."""
import hashlib, importlib, importlib.util, json, os, sys, types
from pathlib import Path
from types import SimpleNamespace
import bpy
from bpy.app.handlers import persistent

args=sys.argv[sys.argv.index('--')+1:];root=Path(args[0]).resolve();profile=args[1];check='--check' in args
work=root/'workspace';scripts=work/'work/github-update/differt-bridge/scripts'
sys.path.insert(0,str(scripts))
from shared_sionna import attach_bridge,BridgeSubprocess
assert bpy.app.version[:2]==(5,2),bpy.app.version_string
# Register the exact archived add-ons in their original namespace, without
# changing the user's preferences or installing into their Blender profile.
for name in ('bl_ext','bl_ext.user_default'):
    if name not in sys.modules:
        package=types.ModuleType(name);package.__path__=[];sys.modules[name]=package
for addon in ('sionnart_bridge','differt_bridge'):
    name='bl_ext.user_default.'+addon;folder=root/'extensions'/addon
    spec=importlib.util.spec_from_file_location(name,folder/'__init__.py',submodule_search_locations=[str(folder)])
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);module.register()
bridge=importlib.import_module('bl_ext.user_default.sionnart_bridge');attach_bridge(bridge)
@persistent
def configure(_unused=None):
    for scene in bpy.data.scenes:
        s=scene.sionna_bridge;s.runtime_mode='EXTERNAL';s.sionna_python=str(work/'work/rt22-runtime/Scripts/python.exe')
        s.sionna_site_packages='';s.drjit_libllvm_path='';s.runtime_probe_json=''
        d=scene.differt_bridge;d.runtime_mode='EXTERNAL';d.differt_python=str(work/'work/runtime/Scripts/python.exe')
        d.differt_site_packages='';d.drjit_libllvm_path='';d.runtime_probe_json=''
        for engine,settings in [('sionna',s),('differt',d)]:
            # New calculations must never write into an archived result directory.
            destination=root/'local/runs'/profile/engine;destination.mkdir(parents=True,exist_ok=True)
            settings.workspace_dir=str(destination)
            # Preserve access to archived results when the recorded path exists
            # in the recovered workspace. This changes session settings only.
            for prop in settings.bl_rna.properties:
                if prop.type!='STRING' or not (prop.identifier.startswith('last_') or prop.identifier.endswith('_report')):continue
                value=getattr(settings,prop.identifier,'').replace('\\','/')
                if ':/' not in value:continue
                for marker in ('/outputs/','/work/'):
                    if marker in value:
                        candidate=work/(marker[1:]+value.split(marker,1)[1])
                        if candidate.exists():setattr(settings,prop.identifier,str(candidate))
                        break
bpy.app.handlers.load_post.append(configure)
scenes={'native':'segment_length_aligned/Native_Float32_Workbench.blend',
        'phase':'segment_length_aligned/Shared_Segment_Length_Workbench.blend',
        'reciprocal':'diffraction_batch/Diffraction_Workbench.blend'}
scene=work/'outputs/differt-bridge/examples'/scenes[profile]
before=hashlib.sha256(scene.read_bytes()).hexdigest();bpy.ops.wm.open_mainfile(filepath=str(scene));configure()
if check:
    calls=[];fake=BridgeSubprocess(SimpleNamespace(run=lambda *a,**kw:calls.append((a,kw))))
    fake.run([bpy.context.scene.sionna_bridge.sionna_python,'worker.py'])
    command=calls[0][0][0]
    assert command[1:5]==['-I','-B','-m','codex_sionna_runtime']
    if profile!='native':assert command[6:9]==['--profile',profile,'--']
    for settings in (bpy.context.scene.sionna_bridge,bpy.context.scene.differt_bridge):
        assert Path(settings.workspace_dir).resolve().is_relative_to(root/'local/runs')
    assert hashlib.sha256(scene.read_bytes()).hexdigest()==before
    (root/'local'/('blender-'+profile+'.json')).write_text(json.dumps({'passed':True,'profile':profile,'blender':bpy.app.version_string,
        'scene_hash':before,'external_workers':True,'outputs_relocated':True,'dispatch_checked_without_execution':True,'simulations_run':False,'scenes_saved':False},indent=2))
    print('RECOVERED_BLENDER_DISPATCH_PASS',profile,flush=True)

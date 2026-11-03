"""Run one real two-engine reference case in factory-startup Blender.

blender --background --factory-startup --python-exit-code 1 --python THIS_SCRIPT --
    CASE OUTPUT_DIRECTORY SIONNA_SOURCE SIONNA_PYTHON DIFFERT_PYTHON
CASE: free_space, ground_reflection, blocked_los, receiver_motion
"""
import bpy
import os
import importlib.util
import json
import math
from pathlib import Path
import shutil
import sys
import time

case,out,source,sionna_python,differt_python=sys.argv[sys.argv.index('--')+1:]
out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
source=Path(source).resolve()
root=Path(__file__).resolve().parents[1]/'src/differt_bridge'

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path/'__init__.py',submodule_search_locations=[str(path)])
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module
    spec.loader.exec_module(module);module.register();return module

s=load('sionna_comparison_test',source)
d=load('differt_comparison_test',root)
for obj in list(bpy.data.objects):bpy.data.objects.remove(obj,do_unlink=True)
scene=bpy.context.scene;scene.name=case.replace('_',' ').title()
scene.frame_start=1;scene.frame_end=2;scene.render.fps=24
bpy.context.preferences.filepaths.save_version=0
ss=scene.sionna_bridge;ds=scene.differt_bridge
ss.runtime_mode=ds.runtime_mode='EXTERNAL'
ss.sionna_python=sionna_python;ds.differt_python=differt_python
ss.drjit_libllvm_path=os.environ.get('DRJIT_LIBLLVM_PATH','')
ss.workspace_dir=str(out/'sionna_runs');ds.workspace_dir=str(out/'differt_runs')
ss.dynamic_mode=ds.dynamic_mode=False
ss.parameter_analysis_enabled=True
ss.export_format='NONE';ss.export_geometry_nodes_metadata=False
ss.samples_per_src=32768;ss.max_num_paths_per_src=4096
ss.frequency_ghz=3.5;ss.enable_los=True
ss.enable_reflection=case=='ground_reflection';ss.max_depth=1 if ss.enable_reflection else 0
ss.enable_refraction=ss.enable_diffuse=ss.enable_diffraction=False
ss.tx_array_rows=ss.tx_array_cols=ss.rx_array_rows=ss.rx_array_cols=1
ss.tx_antenna_pattern=ss.rx_antenna_pattern='iso'
ss.tx_polarization=ss.rx_polarization='V'
ss.timeline_mode='RANGE' if case=='receiver_motion' else 'CURRENT'
ss.enable_mobility_doppler=True
s._ensure_bundled_geometry_nodes(verbose=False);d._ensure_bundled_geometry_nodes(verbose=False)
env=s._ensure_environment(scene)
bpy.ops.sionna_bridge.create_default_materials()
mesh=bpy.data.meshes.new('ReferenceSurface')
if case=='blocked_los':points=[(0,-20,-20),(0,20,-20),(0,20,20),(0,-20,20)]
else:
    z=0 if case=='ground_reflection' else -50
    points=[(-20,-20,z),(20,-20,z),(20,20,z),(-20,20,z)]
mesh.from_pydata(points,[],[(0,1,2,3)])
surface=bpy.data.objects.new('ReferenceSurface',mesh);env['scene'].objects.link(surface)
mesh.materials.append(bpy.data.materials['itu_concrete'])
for role in ('TX','RX'):bpy.ops.sionna_bridge.add_device(role=role)
tx=s._device_objects(scene,'TX')[0];rx=s._device_objects(scene,'RX')[0]
tx.location=(-2,0,2);rx.location=(2,0,2)
if case=='receiver_motion':
    for frame,x in [(0,2),(3,2.3)]:
        rx.location.x=x;rx.keyframe_insert(data_path='location',frame=frame)
    for layer in rx.animation_data.action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for curve in bag.fcurves:
                    for key in curve.keyframe_points:key.interpolation='LINEAR'
scene.frame_set(1);bpy.context.view_layer.update()
# Temporary output choices must survive the paired-path runner.
ss.simulation_mode='BATCH';ss.simulate_radio_map=True;ss.simulate_radio_map_3d=True
ds.simulation_mode='RADIO_MAP'
flags=lambda: {e:{p:getattr(getattr(bpy.context.scene,e+'_bridge'),p) for p in d._comparison.TEMPORARY} for e in ('sionna','differt')}
before=flags()
path=out/(case+'.blend')
bpy.ops.wm.save_as_mainfile(filepath=str(path))
checks=[]
if case=='free_space':
    assert bpy.ops.differt_bridge.run_comparison()=={'FINISHED'}
    process=s._RUN_STATE['process']
    assert bpy.ops.differt_bridge.cancel_comparison()=={'FINISHED'}
    assert process.poll() is not None and not d._comparison.active()
    assert flags()==before
    checks.append('cancel terminates owned worker and restores settings')
    assert bpy.ops.differt_bridge.run_comparison()=={'FINISHED'}
    process=s._RUN_STATE['process']
    bpy.ops.wm.open_mainfile(filepath=str(path))
    assert process.poll() is not None and not d._comparison.active()
    assert flags()==before
    checks.append('opening another file cancels the comparison')
    scene=bpy.context.scene;ss=scene.sionna_bridge;ds=scene.differt_bridge

assert bpy.ops.differt_bridge.run_comparison()=={'FINISHED'}
deadline=time.monotonic()+600
while d._comparison.active():
    assert time.monotonic()<deadline,ds.comparison_status
    d._comparison.tick();time.sleep(.05)
assert ds.comparison_status.startswith('Comparison ready:'),ds.comparison_status
assert flags()==before,(flags(),before)
report_dir=Path(ds.comparison_report).parent
report=json.loads((report_dir/'comparison.json').read_text())
assert all(pair['status']=='matched_inputs' for pair in report['pairs']),report['pairs']
checks.append('captured inputs and exported geometry matched')
gain_rows=[r for r in report['rows'] if r['metric']=='total_power_db']
for row in report['rows']:
    delta=row['differt_minus_sionna']
    if delta is not None:assert abs(delta)<1e-3,(case,row)
checks.append('all available metric deltas below 0.001 in their stated units')
expected_paths=0 if case=='blocked_los' else 2 if case=='ground_reflection' else 1
for row in report['rows']:
    if row['metric']=='path_count':assert row['sionna']==row['differt']==expected_paths,row
    if case=='blocked_los' and row['metric']=='total_power_db':
        assert row['sionna'] is None and row['differt'] is None
    if case=='free_space':
        if row['metric']=='total_power_db':
            expected=20*math.log10(299792458/3.5e9/(4*math.pi*4))
            assert abs(row['sionna']-expected)<1e-3 and abs(row['differt']-expected)<1e-3
        if row['metric']=='first_arrival_ns':
            expected=4/299792458*1e9
            assert abs(row['sionna']-expected)<1e-3 and abs(row['differt']-expected)<1e-3
    if case=='receiver_motion' and row['metric']=='max_abs_doppler_hz':
        assert abs(row['sionna']-2.4*3.5e9/299792458)<1e-3,row
checks.append('reference path counts and analytic free-space/doppler checks')
target=out/'comparison';shutil.copytree(report_dir,target,dirs_exist_ok=True)
ds.comparison_report=str(target/'comparison.html')
assert bpy.ops.differt_bridge.compare_results()=={'FINISHED'}
selected=json.loads((Path(ds.comparison_report).parent/'comparison.json').read_text())
assert selected['run_ids']==report['run_ids']
assert all(p['status']=='matched_inputs' for p in selected['pairs'])
ds.comparison_report=str(target/'comparison.html')
checks.append('saved embedded results compare without rerunning')
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.show_region_ui=True
            area.spaces.active.region_3d.view_distance=14
            area.spaces.active.region_3d.view_location=(0,0,1)
bpy.ops.wm.save_as_mainfile(filepath=str(path))
summary={'case':case,'blender':bpy.app.version_string,'checks':checks,'links':len(report['pairs']),
         'expected_paths_per_link':expected_paths,'max_gain_delta_db':max((abs(r['differt_minus_sionna']) for r in gain_rows if r['differt_minus_sionna'] is not None),default=None),
         'scene':str(path),'report':str(target/'comparison.html')}
(out/'checks.json').write_text(json.dumps(summary,indent=2))
print('COMPARISON_CASE_PASS',json.dumps(summary),flush=True)
d.unregister();s.unregister()

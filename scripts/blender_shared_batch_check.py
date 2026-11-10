"""Exercise paths, both coverage workers, HDF5 and Geometry Nodes in Blender.

blender --background --factory-startup --python-exit-code 1 --python SCRIPT --
    OUTPUT SIONNA_SOURCE SIONNA_PYTHON
"""
import importlib.util
import json
from pathlib import Path
import sys
import time
import bpy

out,source,python=sys.argv[sys.argv.index('--')+1:]
out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True);source=Path(source).resolve()
sys.path.insert(0,str(Path(__file__).resolve().parent))
from shared_sionna import attach_bridge,is_shared
spec=importlib.util.spec_from_file_location('sionna_batch_test',source/'__init__.py',submodule_search_locations=[str(source)])
b=importlib.util.module_from_spec(spec);sys.modules[spec.name]=b;spec.loader.exec_module(b);b.register()
if is_shared(python):attach_bridge(b)
for obj in list(bpy.data.objects):bpy.data.objects.remove(obj,do_unlink=True)
scene=bpy.context.scene;s=scene.sionna_bridge
s.runtime_mode='EXTERNAL';s.sionna_python=python;s.workspace_dir=str(out/'runs')
s.dynamic_mode=False;s.refresh_scene_before_run=True
env=b._ensure_environment(scene);b._ensure_bundled_geometry_nodes(verbose=False)
bpy.ops.sionna_bridge.create_default_materials()
mesh=bpy.data.meshes.new('Floor');mesh.from_pydata([(-20,-20,-1),(20,-20,-1),(20,20,-1),(-20,20,-1)],[],[(0,1,2,3)])
floor=bpy.data.objects.new('Floor',mesh);env['scene'].objects.link(floor)
mesh.materials.append(bpy.data.materials['itu_concrete'])
for role in ('TX','RX'):bpy.ops.sionna_bridge.add_device(role=role)
b._device_objects(scene,'TX')[0].location=(-2,0,3)
b._device_objects(scene,'RX')[0].location=(2,0,1)
s.samples_per_src=32768;s.max_num_paths_per_src=4096;s.max_depth=1
s.enable_refraction=False;s.enable_diffuse=False;s.enable_diffraction=False
s.tx_array_rows=s.tx_array_cols=s.rx_array_rows=s.rx_array_cols=1
s.tx_antenna_pattern=s.rx_antenna_pattern='iso';s.tx_polarization=s.rx_polarization='V'
s.timeline_mode='CURRENT';s.export_format='HDF5';s.export_geometry_nodes_metadata=True
s.radio_map_size_x=s.radio_map_size_y=2;s.radio_map_cell_size_x=s.radio_map_cell_size_y=1;s.radio_map_height=1
s.radio_map_3d_size_x=s.radio_map_3d_size_y=2;s.radio_map_3d_size_z=1
s.radio_map_3d_cell_size_x=s.radio_map_3d_cell_size_y=1;s.radio_map_3d_cell_size_z=.5;s.radio_map_3d_center_z=1.25
s.simulation_mode='BATCH';s.simulate_paths=s.simulate_radio_map=s.simulate_radio_map_3d=True
assert bpy.ops.sionna_bridge.run_selected()=={'FINISHED'}
deadline=time.monotonic()+600
while any(state.get('process') for state in (b._RUN_STATE,b._RADIO_MAP_STATE,b._RADIO_MAP_3D_STATE)):
    assert time.monotonic()<deadline,s.last_status_details
    for state,poll in [(b._RUN_STATE,b._poll_sionna_process),(b._RADIO_MAP_STATE,b._poll_radio_map_process),(b._RADIO_MAP_3D_STATE,b._poll_radio_map_3d_process)]:
        if state.get('process') and state['process'].poll() is not None:poll()
    time.sleep(.05)
assert not b._BATCH_STATE['active']
assert 'failed' not in s.last_status.lower() and 'rejected' not in s.last_status.lower(),(s.last_status,s.last_status_details)
export=Path(s.last_export_path);assert export.is_file() and export.suffix=='.h5'
meta=json.loads(Path(s.last_export_metadata_path).read_text())
assert set(meta['categories'])=={'paths','coverage_2d','coverage_3d'}
for key in ('last_radio_map_object','last_radio_map_3d_object'):
    obj=bpy.data.objects[getattr(s,key)];assert obj.modifiers[0].node_group
result=dict(passed=True,python=python,export=str(export),status=s.last_status,
            metadata=s.last_export_metadata_path,categories=list(meta['categories']))
(out/'checks.json').write_text(json.dumps(result,indent=2))
print('SIONNA_BATCH_PASS',str(out/'checks.json'),flush=True)
b.unregister()

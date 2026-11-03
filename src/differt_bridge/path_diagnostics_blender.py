"""Saved point capture and a separate, non-exported diagnostic overlay."""
import json
import math
from pathlib import Path
import uuid
import bpy
from . import path_diagnostics as diagnostics


def capture(obj,study):
    if obj is None or not isinstance(obj.data,bpy.types.Mesh):
        return diagnostics.unavailable(study,'No embedded path mesh is selected')
    count=len(obj.data.vertices)
    if count>diagnostics.MAX_POINTS:
        return diagnostics.unavailable(study,'Point capture exceeds the 1,000,000-point limit')
    columns={}
    for name in (*diagnostics.REQUIRED_COLUMNS,*diagnostics.METRIC_COLUMNS):
        attr=obj.data.attributes.get(name)
        if attr is None or attr.domain!='POINT' or attr.data_type not in ('INT','FLOAT') or len(attr.data)!=count:
            continue
        values=[0]*count if attr.data_type=='INT' else [0.]*count
        attr.data.foreach_get('value',values);columns[name]=values
    return diagnostics.from_columns(study,columns)


def collection(scene,create=False):
    owner=scene.get('radio_diagnostics_owner')
    found=next((c for c in scene.collection.children if owner and c.get('radio_diagnostics_owner')==owner),None)
    if found is None and create:
        owner=uuid.uuid4().hex;scene['radio_diagnostics_owner']=owner
        found=bpy.data.collections.new('Radio Path Diagnostics')
        found['radio_diagnostics_owner']=owner;scene.collection.children.link(found)
    return found


def clear(scene):
    coll=collection(scene)
    if coll is None:return
    for obj in list(coll.objects):
        if obj.get('radio_diagnostic_route'):
            curve=obj.data;bpy.data.objects.remove(obj,do_unlink=True)
            if isinstance(curve,bpy.types.Curve) and curve.users==0:bpy.data.curves.remove(curve)


def show(scene):
    path=Path(scene.differt_bridge.comparison_report).parent/'path_diagnostics.json'
    if not path.is_file():raise ValueError('Create a comparison report with path diagnostics first')
    if path.stat().st_size>100*1024*1024:raise ValueError('Diagnostic file exceeds 100 MB')
    report=json.loads(path.read_text(encoding='utf-8'))
    if report.get('schema')!='radio_path_diagnostics_v1':raise ValueError('Unknown diagnostic schema')
    rows=[r for r in report['rows'] if r['frame']==scene.frame_current and r['status'] in
          ('sionna_only','differt_only','sionna_unmatched_subset','differt_unmatched_subset')]
    if not rows:raise ValueError('No unambiguous unmatched captured paths in the current frame; inspect the report for matches or unavailable traces')
    rows=rows[:500]
    for row in rows:
        p=row['sionna'] or row['differt']
        if not 2<=len(p['points'])<=1024 or any(len(v)!=3 or not all(diagnostics.finite(x) for x in v) for v in p['points']):
            raise ValueError('Invalid path vertices in the diagnostic report')
    clear(scene);coll=collection(scene,True)
    for row in rows:
        engine='sionna' if row['sionna'] else 'differt';path=row[engine]
        curve=bpy.data.curves.new('Captured '+engine+' route','CURVE')
        curve.dimensions='3D';curve.bevel_depth=.018;curve.bevel_resolution=2
        spline=curve.splines.new('POLY');spline.points.add(len(path['points'])-1)
        for point,position in zip(spline.points,path['points']):point.co=(*position,1.)
        obj=bpy.data.objects.new(f'{engine} {row["tx"]} to {row["rx"]} path {path["path_index"]}',curve)
        obj['radio_diagnostic_route']=True;obj['radio_diagnostic_status']=row['status']
        obj['radio_diagnostic_run']=report['run_ids'][engine];obj['radio_diagnostic_frame']=row['frame']
        obj.color=(.8,.12,.06,1.) if engine=='sionna' else (.05,.3,.85,1.)
        obj.show_in_front=True;coll.objects.link(obj)
        material=bpy.data.materials.get('Radio Diagnostics '+engine)
        if material is None:
            material=bpy.data.materials.new('Radio Diagnostics '+engine);material.diffuse_color=obj.color
        curve.materials.append(material)
    scene.differt_bridge.comparison_diagnostics_status=f'{len(rows)} captured routes at frame {scene.frame_current}; Sionna red, DiffeRT blue (limit 500)'
    return len(rows)


def build_classes(comparison_bridge):
    class DIFFERT_OT_ShowPathDifferences(bpy.types.Operator):
        bl_idname='differt_bridge.show_path_differences'
        bl_label='Show Unmatched Paths'
        bl_description='Overlay up to 500 unmatched captured paths in the current frame; Sionna red, DiffeRT blue. The source simulation geometry is unchanged'
        bl_options={'REGISTER','UNDO'}
        @classmethod
        def poll(cls,context):return not comparison_bridge.active()
        def execute(self,context):
            try:
                count=show(context.scene);self.report({'INFO'},f'Showing {count} captured paths');return {'FINISHED'}
            except Exception as exc:self.report({'ERROR'},str(exc));return {'CANCELLED'}

    class DIFFERT_OT_ClearPathDifferences(bpy.types.Operator):
        bl_idname='differt_bridge.clear_path_differences'
        bl_label='Clear Path Overlay'
        bl_options={'REGISTER','UNDO'}
        def execute(self,context):
            clear(context.scene);context.scene.differt_bridge.comparison_diagnostics_status='';return {'FINISHED'}
    return (DIFFERT_OT_ShowPathDifferences,DIFFERT_OT_ClearPathDifferences)

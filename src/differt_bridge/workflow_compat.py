"""Explicit, non-destructive import of the companion Sionna bridge setup."""
import bpy


def copy_properties(source,target,skip=()):
    count=0
    for prop in source.bl_rna.properties:
        name=prop.identifier
        if name=='rna_type' or name in skip or name.startswith('last_') or prop.is_readonly:
            continue
        if not hasattr(target,name): continue
        if prop.type=='COLLECTION': continue
        try:
            setattr(target,name,getattr(source,name));count+=1
        except (TypeError,ValueError,AttributeError): pass
    return count


def copy_setup(bridge,context):
    scene=context.scene
    if not hasattr(scene,'sionna_bridge'):
        raise RuntimeError('Enable SionnaRT-Bridge first, then open your Sionna scene')
    source=bpy.data.collections.get('sionna_env')
    if source is None: raise RuntimeError('This scene has no sionna_env collection')
    settings=scene.differt_bridge
    copy_properties(scene.sionna_bridge,settings,skip=(
        'workspace_dir','runtime_mode','runtime_probe_json','runtime_probe_fingerprint',
        'drjit_libllvm_path','geometry_nodes_group_name',
        'radio_map_geometry_nodes_group_name','radio_map_3d_geometry_nodes_group_name',
    ))
    env=bridge._ensure_environment(scene,migrate=False)
    # Geometry objects stay shared; edits and Geometry Nodes evaluate identically.
    static=next((c for c in source.children if c.get('sionna_collection_role')=='scene' or c.name=='scene'),None)
    if static is None: raise RuntimeError('No Sionna static-scene collection found')
    procedural=next((c for c in static.children if c.get('sionna_collection_role')=='procedural_geometry' or c.name=='procedural_geometry'),None)
    procedural_objects=set(procedural.all_objects) if procedural else set()
    geometry=0
    for obj in static.all_objects:
        target=env['procedural_geometry'] if obj in procedural_objects else env['scene']
        if obj.name not in target.objects:target.objects.link(obj)
        geometry+=1
        for slot in obj.material_slots:
            if slot.material and hasattr(slot.material,'sionna_radio'):
                copy_properties(slot.material.sionna_radio,slot.material.differt_radio)
    device_map={}
    source_keys={str(o.get('sionna_device_id') or o.name) for o in scene.objects
                 if o.get('sionna_role') in ('TX','RX')}
    for clone in scene.objects:
        if clone.get('differt_source_device') and clone['differt_source_device'] not in source_keys:
            if 'differt_role' in clone: del clone['differt_role']
            clone['differt_source_inactive']=True
            clone.hide_set(True)
    for obj in list(scene.objects):
        role=obj.get('sionna_role')
        if role not in ('TX','RX'):continue
        key=str(obj.get('sionna_device_id') or obj.name)
        clone=next((o for o in scene.objects if o.get('differt_source_device')==key),None)
        if clone is None:
            clone=obj.copy()
            clone.name='DiffeRT_'+obj.name
            for prop in list(clone.keys()):
                if prop.startswith('sionna_'):del clone[prop]
            env['txs' if role=='TX' else 'rxs'].objects.link(clone)
        clone['differt_role']=role;clone['differt_source_device']=key
        if clone.get('differt_source_inactive'):
            del clone['differt_source_inactive']
            clone.hide_set(False)
        if hasattr(obj,'sionna_device_config'):
            copy_properties(obj.sionna_device_config,clone.differt_device_config)
        clone.matrix_world=obj.matrix_world.copy()
        if obj.animation_data and obj.animation_data.action:
            clone.animation_data_create();clone.animation_data.action=obj.animation_data.action
        device_map[obj]=clone
    for clone in device_map.values():
        config=clone.differt_device_config
        for prop in config.bl_rna.properties:
            if prop.type=='POINTER' and not prop.is_readonly:
                value=getattr(config,prop.identifier,None)
                if isinstance(value,bpy.types.Object) and value in device_map:
                    setattr(config,prop.identifier,device_map[value])
    # Copy curves on the same ID, without self-referential drivers (which create depsgraph cycles).
    linked=0
    for owner,source_attr,target_attr in [(scene,'sionna_bridge','differt_bridge')]+[
        (m,'sionna_radio','differt_radio') for m in bpy.data.materials if hasattr(m,'sionna_radio')]:
        source_settings=getattr(owner,source_attr);target_settings=getattr(owner,target_attr)
        for prop in source_settings.bl_rna.properties:
            if prop.type not in ('FLOAT','INT','BOOLEAN') or prop.is_readonly or not hasattr(target_settings,prop.identifier):continue
            source_path=source_attr+'.'+prop.identifier;target_path=target_attr+'.'+prop.identifier
            if not source_settings.is_property_set(prop.identifier):continue
            # Only link animated properties, not all settings.
            anim=owner.animation_data
            if not anim or not anim.action:continue
            curves=[]
            for layer in anim.action.layers:
                for strip in layer.strips:
                    for bag in strip.channelbags:
                        curves.extend((bag,c) for c in list(bag.fcurves) if c.data_path==source_path)
            for bag,curve in curves:
                index=curve.array_index if prop.is_array else -1
                owner.driver_remove(target_path,index)
                previous=bag.fcurves.find(target_path,index=curve.array_index)
                if previous:bag.fcurves.remove(previous)
                copied=bag.fcurves.new(target_path,index=curve.array_index)
                copied.extrapolation=curve.extrapolation
                copied.keyframe_points.add(len(curve.keyframe_points))
                for old,new in zip(curve.keyframe_points,copied.keyframe_points):
                    for attribute in ('co','interpolation','easing','handle_left_type','handle_right_type','handle_left','handle_right','amplitude','back','period'):
                        setattr(new,attribute,getattr(old,attribute))
                for old in curve.modifiers:
                    new=copied.modifiers.new(old.type)
                    copy_properties(old,new)
                copied.update()
                linked+=1
    return geometry,len(device_map),linked


def build_operator(bridge):
    class DIFFERT_OT_CopySionnaSetup(bpy.types.Operator):
        bl_idname='differt_bridge.copy_sionna_setup'
        bl_label='Copy Sionna Setup'
        bl_description='Share environment geometry, copy TX/RX and radio settings into the separate DiffeRT workflow'
        bl_options={'REGISTER','UNDO'}
        def execute(self,context):
            try:
                geometry,devices,drivers=copy_setup(bridge,context)
                self.report({'INFO'},f'Copied {devices} devices; shared {geometry} geometry objects; copied {drivers} animation curves')
                return {'FINISHED'}
            except Exception as exc:
                self.report({'ERROR'},str(exc));return {'CANCELLED'}
    return DIFFERT_OT_CopySionnaSetup

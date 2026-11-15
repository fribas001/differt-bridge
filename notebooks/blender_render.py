"""Render preserved diagnostic geometry in a fresh Blender scene, without solvers."""
import hashlib
import json
from pathlib import Path
import threading

ROOT = Path(__file__).resolve().parents[1]


def render_model(case, output, *, path_index=None, detail=False, samples=24):
    """Run on Blender's main thread. Existing scenes and preferences are untouched.

    Leaves/wood use display colors, unrelated to their radio material parameters.
    Device and path markers are enlarged for legibility. No ground is introduced.
    A new scene is retained so the user can inspect it after rendering.
    """
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError('Blender rendering must run on its main thread.')
    import bpy
    from mathutils import Vector
    from visuals import verify_assets
    verify_assets()
    source = ROOT / 'notebooks/assets/models.json'
    model = json.loads(source.read_text())['models'][case]
    if path_index is not None and not 0 <= path_index < len(model.get('paths', [])):
        raise ValueError('This model has no retained path at that index.')
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    old_scene = bpy.context.window.scene if bpy.context.window else None
    scene = bpy.data.scenes.new('DiffeRT Notebook - ' + case.replace('/', ' - '))
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 1000
    scene.render.resolution_y = 650
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = str(output)
    scene.view_settings.view_transform = 'Standard'
    world = bpy.data.worlds.new('Notebook white world')
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.92, 0.95, 1.0, 1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.65
    scene.world = world

    def material(name, color):
        mat = bpy.data.materials.new('Notebook ' + name)
        mat.diffuse_color = (*color, 1)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get('Principled BSDF')
        bsdf.inputs['Base Color'].default_value = (*color, 1)
        bsdf.inputs['Roughness'].default_value = 0.65
        return mat

    mats = {key: material(key, color) for key, color in {
        'leaf': (0.07, 0.42, 0.22), 'wood': (0.40, 0.20, 0.07),
        'tx': (0.8, 0.055, 0.06), 'rx': (0.035, 0.24, 0.67),
        'path': (0.9, 0.36, 0.02),
    }.items()}
    all_points = []
    for index, shape in enumerate(model['shapes']):
        mesh = bpy.data.meshes.new('Notebook model mesh')
        mesh.from_pydata(shape['vertices'], [], shape['triangles'])
        mesh.update()
        obj = bpy.data.objects.new(shape.get('name', f"{shape['material']}_{index}"), mesh)
        scene.collection.objects.link(obj)
        obj.data.materials.append(mats[shape['material']])
        obj['role'] = 'historical_model_geometry'
        all_points.extend(shape['vertices'])
    points = list(all_points)
    if not detail or not points:
        points.extend([model['tx'], model['rx']])
    lo = Vector([min(p[i] for p in points) for i in range(3)])
    hi = Vector([max(p[i] for p in points) for i in range(3)])
    centre = (lo + hi) / 2
    span = max(max(hi - lo), 0.01)

    def line(name, coordinates, radius, mat):
        curve = bpy.data.curves.new(name, 'CURVE')
        curve.dimensions = '3D'
        curve.resolution_u = 1
        curve.bevel_depth = radius
        curve.bevel_resolution = 3
        spline = curve.splines.new('POLY')
        spline.points.add(len(coordinates) - 1)
        for point, coordinate in zip(spline.points, coordinates):
            point.co = (*coordinate, 1)
        obj = bpy.data.objects.new(name, curve)
        scene.collection.objects.link(obj)
        curve.materials.append(mat)
        obj['role'] = 'display_marker_only'
        return obj

    # Short crosses mark the exact antenna centres; arms are display symbols.
    for key in ('tx', 'rx'):
        pos = Vector(model[key])
        for direction in ((1, 0, 0), (0, 1, 0), (0, 0, 1)):
            delta = Vector(direction) * span * 0.012
            line(key.upper(), [pos - delta, pos + delta], span * 0.003, mats[key])
    path = model['paths'][path_index] if path_index is not None else None
    if path:
        line(path['label'], path['points'], span * 0.0018, mats['path'])
    camera_data = bpy.data.cameras.new('Notebook camera')
    camera = bpy.data.objects.new('Notebook camera', camera_data)
    scene.collection.objects.link(camera)
    camera.location = centre + Vector((0.65, -1.4, 0.85)) * span
    camera.rotation_euler = (centre - camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera_data.type = 'ORTHO'
    inverse = camera.rotation_euler.to_matrix().transposed()
    projected = [inverse @ (Vector(p) - centre) for p in points]
    # ortho_scale is the horizontal extent for these landscape images.
    width = max(p.x for p in projected) - min(p.x for p in projected)
    height = max(p.y for p in projected) - min(p.y for p in projected)
    camera_data.ortho_scale = max(width, height * 1000 / 650) * 1.25
    camera_data.clip_start = span * 0.0001
    camera_data.clip_end = span * 100
    scene.camera = camera
    lamp_data = bpy.data.lights.new('Notebook key light', 'AREA')
    lamp = bpy.data.objects.new('Notebook key light', lamp_data)
    scene.collection.objects.link(lamp)
    lamp.location = centre + Vector((-0.5, -1, 2)) * span
    lamp.rotation_euler = (centre - lamp.location).to_track_quat('-Z', 'Y').to_euler()
    lamp_data.energy = 120 * span * span
    lamp_data.shape = 'DISK'
    lamp_data.size = span * 2
    try:
        bpy.ops.render.render(write_still=True, scene=scene.name)
    finally:
        if old_scene and bpy.context.window:
            bpy.context.window.scene = old_scene
    receipt = {
        'case': case, 'scene': scene.name, 'blender': bpy.app.version_string,
        'engine': 'CYCLES', 'device': 'CPU', 'samples': samples,
        'geometry_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'renderer_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'image_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
        'path_label': path['label'] if path else None, 'detail_crop': detail,
        'camera': {'location': list(camera.location), 'rotation': list(camera.rotation_euler),
                   'ortho_scale': camera_data.ortho_scale, 'resolution': [1000, 650]},
        'scope': 'Presentation render of preserved geometry; no electromagnetic calculation.',
    }
    output.with_suffix('.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt

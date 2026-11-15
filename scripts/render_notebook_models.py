"""Run with Blender --background --factory-startup --python-exit-code 1 --python."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'notebooks'))
from blender_render import render_model

TARGETS = [
    ('ris/two_leaves', 'ris_two_leaves', {}),
    ('focused/leaf_branch', 'focused_leaf_branch', {'detail': True}),
    ('focused/wood_slab_20mm', 'focused_wood_slab', {'detail': True}),
    ('focused/wood_box_10mm', 'focused_wood_box', {'detail': True}),
    ('multiple/mixed_centre', 'multiple_cluster', {}),
    ('multiple/blocked_coupled', 'blocked_sionna', {'path_index': 0}),
    ('multiple/blocked_coupled', 'blocked_differt', {'path_index': 1}),
]


def main():
    import bpy
    original = bpy.context.scene
    original_objects = list(original.objects)
    original_engine, original_output = original.render.engine, original.render.filepath
    assets = ROOT / 'notebooks/assets'
    manifest = json.loads((assets / 'manifest.json').read_text())
    # Do not change old manifest entries while generating their replacements.
    # Stage fresh outputs outside assets so checksums remain valid throughout.
    stage = ROOT / 'build/model-renders'
    receipts = []
    for case, name, kwargs in TARGETS:
        receipts.append(render_model(case, stage / f'{name}.png', **kwargs))
    assert bpy.context.scene == original
    assert list(original.objects) == original_objects
    assert (original.render.engine, original.render.filepath) == (original_engine, original_output)
    import shutil
    files = [e for e in manifest['files'] if e['kind'] != 'blender-render']
    for (_, name, _), receipt in zip(TARGETS, receipts):
        for suffix in ('.png', '.json'):
            target = assets / (name + suffix)
            shutil.copyfile(stage / target.name, target)
            files.append({'path': target.name, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                          'kind': 'blender-render', 'case': receipt['case']})
    manifest['files'] = files
    (assets / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('BLENDER_NOTEBOOK_RENDER_PASS: 7 images; original scene preserved', flush=True)


if __name__ == '__main__':
    main()

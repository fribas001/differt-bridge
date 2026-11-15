"""Extract synthetic comparison geometry and preserved figures for the notebooks."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vegetation-root', required=True, type=Path)
    parser.add_argument('--ris-root', required=True, type=Path)
    parser.add_argument('--output', type=Path, default=ROOT / 'notebooks/assets')
    args = parser.parse_args()
    focused = args.vegetation_root / 'focused_solver_comparison_20261017'
    multiple = args.vegetation_root / 'multidiffraction_20261017'
    edge = args.vegetation_root / 'edge_fullwave_20261017'
    sources = [focused / 'plan.json', multiple / 'plan.json', args.ris_root / 'plan.json',
               multiple / 'figure_examples.json']
    figures = [
        (focused / 'figures/01_geometry_and_paths.png', 'focused_paths.png',
         'Historical top-view path projections. Panels have different scales; panel (c) is a separate short wood-edge link.'),
        (multiple / 'figures/01_native_paths.png', 'multiple_paths.png',
         'Historical blocked_coupled case, V polarization. Actual retained 3D paths projected onto XY; labeled losses are individual-path values, not total-channel loss or an accuracy ranking.'),
        (edge / 'figures/02_fullwave_fields.png', 'fullwave_fields.png',
         'Historical openEMS normalized coherent Ez field maps for 2D infinite-z coupons. These are not the finite 3D ray-tracing scenes. White circles locate the 12 probes per coupon.'),
    ]
    for path in sources + [p for p, _, _ in figures]:
        if not path.is_file():
            raise FileNotFoundError(path)
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    models = {}
    source_records = []
    for prefix, source in zip(('focused', 'multiple', 'ris'), sources[:3]):
        plan = json.loads(source.read_text())
        source_records.append({'source_relative': f'{source.parent.name}/{source.name}',
                               'source_sha256': sha(source)})
        for case in plan['cases']:
            if prefix == 'ris' and case['diagnostic']:
                continue  # Actual plant/RIS meshes are outside this synthetic supplement.
            if prefix == 'multiple' and case['name'] not in (
                    'mixed_left', 'mixed_centre', 'mixed_right', 'blocked_coupled'):
                continue
            shapes = case.get('shapes')
            if shapes is None:
                shapes = ([{'vertices': case['vertices'], 'triangles': case['triangles'],
                            'material': 'leaf'}] if case['triangles'] else [])
            models[f'{prefix}/{case["name"]}'] = {
                'study': prefix, 'case': case['name'], 'frequency_hz': plan['frequency_hz'],
                'units': 'm', 'tx': case['tx'], 'rx': case['rx'],
                'shapes': [{k: s[k] for k in ('vertices', 'triangles', 'material', 'name', 'solid_bounds')
                            if k in s} for s in shapes],
                'radio_materials': case.get('materials', {'leaf': case.get('material', {})}),
            }
    examples = json.loads(sources[3].read_text())
    models['multiple/blocked_coupled']['paths'] = [
        {'label': label, 'points': row['points'], 'events': row['events'],
         'power': row['power'], 'polarization': examples['polarization']}
        for label, row in examples['examples'].items()]
    source_records.append({'source_relative': f'{multiple.name}/figure_examples.json',
                           'source_sha256': sha(sources[3])})
    model_path = out / 'models.json'
    model_path.write_text(json.dumps({'schema': 1, 'scope': 'Synthetic diagnostic models only; no private plant scenes.',
                                     'sources': source_records, 'models': models}, indent=2) + '\n')
    files = [{'path': 'models.json', 'sha256': sha(model_path),
              'kind': 'geometry-extract', 'transform': 'Selected synthetic cases and four retained blocked-link paths; coordinates and indices unchanged.'}]
    for source, name, caption in figures:
        shutil.copyfile(source, out / name)
        files.append({'path': name, 'sha256': sha(out / name), 'source_sha256': sha(source),
                      'source_relative': f'{source.parents[1].name}/figures/{source.name}',
                      'kind': 'historical-figure', 'transform': 'byte-for-byte copy', 'caption': caption})
    (out / 'manifest.json').write_text(json.dumps({'schema': 1, 'license': 'GPL-3.0-or-later; project-generated assets',
                                                'files': files}, indent=2) + '\n')
    print(f'Prepared {len(models)} synthetic model cases and {len(figures)} historical figures.')


if __name__ == '__main__':
    main()

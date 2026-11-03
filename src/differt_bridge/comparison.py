"""Portable comparisons of captured path results; no Blender dependency."""
import csv
import hashlib
import html
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

try:
    from . import parameter_analysis as analysis
    from . import point_coverage
    from . import path_diagnostics
except ImportError:
    import parameter_analysis as analysis
    import point_coverage
    import path_diagnostics

METRICS = analysis.METRICS
CRITICAL = ('frequency_hz', 'max_depth', 'los', 'specular_reflection',
            'diffuse_reflection', 'refraction', 'diffraction', 'mobility_doppler')
MATERIAL_FIELDS = ('model', 'itu_type', 'relative_permittivity', 'conductivity',
                   'thickness', 'scattering_coefficient', 'xpd_coefficient',
                   'scattering_pattern', 'directive_alpha_r', 'backscatter_alpha_r',
                   'backscatter_alpha_i', 'backscatter_lambda', 'plant_model')


def finite(value):
    return isinstance(value, (int, float)) and math.isfinite(value)


def same(left, right):
    if finite(left) and finite(right):
        return math.isclose(left, right, rel_tol=1e-7, abs_tol=1e-9)
    return left == right


def endpoint(name):
    # The companion's explicit Copy Sionna Setup operation uses this prefix.
    return str(name).removeprefix('DiffeRT_')


def _index(study, copied_names=False):
    result = {}
    for record in study.get('records', []):
        name = endpoint if copied_names else str
        key = (int(record['frame']), name(record['tx']), name(record['rx']))
        if key in result:
            raise ValueError('Ambiguous endpoint names after prefix normalization: ' + str(key))
        result[key] = record
    if not result:
        raise ValueError('No per-link path results in this study')
    return result


def _inputs(record, study):
    values = record.get('values', {})
    result = {'solver/' + k: values.get('solver/' + k) for k in CRITICAL}
    for key, value in study.get('context', {}).items():
        if key.startswith('antenna/'):
            result[key] = value
    for role, name in (('transmitters', record['tx']), ('receivers', record['rx'])):
        prefix = 'device/' + role + '/' + name + '/'
        for key, value in values.items():
            if key.startswith(prefix):
                suffix = key[len(prefix):].replace('orientation_sionna_rad', 'orientation_rad').replace('orientation_differt_rad', 'orientation_rad')
                result['device/' + role + '/' + suffix] = value
    for key, value in values.items():
        if key.startswith('material/') and key.rsplit('/', 1)[-1] in MATERIAL_FIELDS:
            result[key] = value
    return result


def geometry_evidence(config):
    """Hash world-space PLY geometry and its material assignment at launch.

    The bridge exporters bake all transforms into their PLY vertices. This
    deliberately rejects other geometry encodings instead of claiming equality.
    """
    output = {}
    for frame in config.get('frames', []):
        try:
            xml_path = Path(frame.get('scene_xml') or config['scene_xml'])
            materials = {str(m['source_name']): str(m.get('blender_name', m['source_name']))
                         for m in frame.get('materials', config.get('materials', []))}
            shapes = []
            for shape in ET.parse(xml_path).getroot().findall('shape'):
                if shape.get('type') != 'ply' or shape.find('transform') is not None:
                    raise ValueError('Only world-space PLY geometry can be verified')
                filename = shape.find("string[@name='filename']")
                ref = shape.find('ref')
                material_id = ref.get('id', '').removeprefix('mat-') if ref is not None else ''
                if filename is None or material_id not in materials:
                    raise ValueError('Missing mesh or material identity')
                mesh = (xml_path.parent / filename.get('value')).resolve()
                normals = shape.find("boolean[@name='face_normals']")
                raw = mesh.read_bytes()
                header, marker, body = raw.partition(b'end_header\n')
                if not marker or not header.startswith(b'ply\n'):
                    raise ValueError('Unsupported PLY header')
                # Exporter attribution comments differ; topology, numeric format
                # and vertex/face bytes must still agree exactly.
                header = b'\n'.join(line for line in header.splitlines()
                                     if not line.startswith((b'comment ', b'obj_info ')))
                shapes.append([hashlib.sha256(header + b'\nend_header\n' + body).hexdigest(), materials[material_id],
                               normals.get('value') if normals is not None else None])
            if not shapes:
                raise ValueError('No exported mesh geometry')
            digest = hashlib.sha256(json.dumps(sorted(shapes), separators=(',', ':')).encode()).hexdigest()
            output[str(frame['frame'])] = {'sha256': digest, 'shape_count': len(shapes), 'method': 'world_space_ply_physical_and_material_assignment_v1'}
        except (OSError, ValueError, KeyError, ET.ParseError) as exc:
            output[str(frame['frame'])] = {'sha256': None, 'reason': str(exc)}
    return output


def load_study(path):
    path = Path(path)
    if path.suffix.lower() in ('.h5', '.hdf5'):
        try:
            import h5py
        except ImportError as exc:
            raise ValueError('Reading HDF5 requires h5py; use a configured runtime or its .metadata.json file') from exc
        with h5py.File(path, 'r') as handle:
            raw = handle['metadata/export_json'][()]
            payload = json.loads(raw.decode() if isinstance(raw, bytes) else raw)
    elif path.suffix.lower() == '.zip':
        with zipfile.ZipFile(path) as archive:
            names = [n for n in archive.namelist() if n.endswith('.metadata.json')]
            if len(names) != 1:
                raise ValueError('Choose an export ZIP with exactly one .metadata.json')
            payload = json.loads(archive.read(names[0]))
    else:
        payload = json.loads(path.read_text(encoding='utf-8-sig'))
    if payload.get('records') and payload.get('schema') in ('sionna_parameter_study', 'differt_parameter_study'):
        _index(payload)
        return payload
    # The inherited capture helper names this Euler field after its engine.
    # Normalize the field before rebuilding a study from Sionna export metadata.
    category = payload.get('categories', {}).get('paths', {})
    for frame in category.get('parameters', {}).get('frames', []):
        for role in ('transmitters', 'receivers'):
            for device in frame.get(role, []):
                if 'orientation_sionna_rad' in device:
                    device['orientation_differt_rad'] = device.pop('orientation_sionna_rad')
    return analysis.from_export(payload)


def compare_studies(left, right):
    a, b = _index(left), _index(right, copied_names=True)
    pairs, rows = [], []
    context_a, context_b = left.get('context', {}), right.get('context', {})
    for key in sorted(a.keys() | b.keys()):
        x, y = a.get(key), b.get(key)
        issues, notes = [], []
        if x is None or y is None:
            issues.append('missing_link')
        else:
            p, q = _inputs(x, left), _inputs(y, right)
            for name in sorted(p.keys() | q.keys()):
                if name not in p or name not in q or not same(p[name], q[name]):
                    issues.append('input:' + name)
            for name in CRITICAL:
                if p.get('solver/' + name) is None or q.get('solver/' + name) is None:
                    notes.append('Unrecorded input: ' + name)
            antenna_keys = ['antenna/'+role+'/'+field for role in ('tx','rx') for field in
                            ('pattern','num_rows','num_cols','vertical_spacing','horizontal_spacing','polarization','polarization_model')]
            if not all(k in context for k in antenna_keys for context in (context_a, context_b)):
                notes.append('Antenna configuration is not fully recorded')
            if not all('device/'+role+'/position/'+str(axis) in data
                       for role in ('transmitters', 'receivers') for axis in range(3) for data in (p, q)):
                notes.append('Endpoint positions are not fully recorded')
            if not all('device/'+role+'/orientation_rad/'+str(axis) in data
                       for role in ('transmitters', 'receivers') for axis in range(3) for data in (p, q)):
                notes.append('Endpoint orientations are not fully recorded')
            if not all(any(k.startswith('material/') and k.endswith('/model') for k in data) for data in (p,q)):
                notes.append('Radio materials are not fully recorded')
            if x['tx'] != y['tx'] or x['rx'] != y['rx']:
                notes.append('Copied-setup DiffeRT_ endpoint prefix normalized')
            for name in ('samples_per_src', 'synthetic_array', 'seed', 'differt_solver'):
                xv, yv = x.get('values', {}).get('solver/' + name), y.get('values', {}).get('solver/' + name)
                if xv != yv:
                    notes.append('Backend setting differs: ' + name + ' (' + str(xv) + ' / ' + str(yv) + ')')
            gx = left.get('geometry_evidence', {}).get(str(key[0]), {})
            gy = right.get('geometry_evidence', {}).get(str(key[0]), {})
            if gx.get('sha256') and gy.get('sha256') and gx.get('method') == gy.get('method'):
                if gx['sha256'] != gy['sha256']:
                    issues.append('geometry_differs')
                geometry = 'verified_equal' if gx['sha256'] == gy['sha256'] else 'different'
            else:
                geometry = 'unverified'
                notes.append('Exported geometry identity was not captured for both runs')
        status = 'missing_link' if x is None or y is None else 'inputs_differ' if issues else 'matched_inputs' if geometry == 'verified_equal' and not any('not fully' in n or 'Unrecorded' in n for n in notes) else 'partially_verified'
        pair = {'frame': key[0], 'tx': key[1], 'rx': key[2], 'status': status,
                'geometry': geometry if x is not None and y is not None else 'unverified',
                'issues': issues, 'notes': notes}
        pairs.append(pair)
        for metric, (label, unit) in METRICS.items():
            av = x.get('metrics', {}).get(metric) if x else None
            bv = y.get('metrics', {}).get(metric) if y else None
            # Absent paths never become fabricated gains or delays.
            if metric not in ('path_count', 'los_available'):
                if x and x.get('metrics', {}).get('path_count') == 0: av = None
                if y and y.get('metrics', {}).get('path_count') == 0: bv = None
            av, bv = av if finite(av) else None, bv if finite(bv) else None
            rows.append({**pair, 'metric': metric, 'label': label, 'unit': unit,
                         'sionna': av, 'differt': bv,
                         'differt_minus_sionna': bv-av if av is not None and bv is not None else None})
    return {'schema': 'radio_engine_comparison_v1', 'run_ids': {'sionna': left.get('run_id'), 'differt': right.get('run_id')},
            'scope': 'Incoherent path-power sum and delays, first TX/RX antenna pair; path maps are excluded.',
            'conventions': ['Equal inputs do not establish identical physical models.',
                            'Sionna area-averaged maps and DiffeRT point samples require a separate comparison.',
                            'Synthetic versus explicitly traced arrays can differ; start with one element.',
                            'No-path gain and delay values remain unavailable, not zero.'],
            'pairs': pairs, 'rows': rows}


def write_report(directory, left, right, title='Sionna and DiffeRT comparison', path_tolerance_m=.001):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    report = compare_studies(left, right)
    for name, data in [('comparison.json', report), ('sionna.study.json', left), ('differt.study.json', right)]:
        (directory / name).write_text(json.dumps(data, indent=2, allow_nan=False), encoding='utf-8')
    columns = ('frame','tx','rx','metric','unit','sionna','differt','differt_minus_sionna','status','geometry','issues','notes')
    with (directory / 'comparison.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        for row in report['rows']:
            writer.writerow({**row, 'issues': '; '.join(row['issues']), 'notes': '; '.join(row['notes'])})
    esc = lambda value: html.escape(str(value), quote=True)
    number = lambda value: '—' if value is None else f'{value:.8g}'
    body = []
    for row in report['rows']:
        body.append('<tr data-metric="'+esc(row['metric'])+'"><td>'+str(row['frame'])+'</td><td>'+esc(row['tx']+' → '+row['rx'])+'</td><td>'+esc(row['label'])+'</td><td>'+number(row['sionna'])+'</td><td>'+number(row['differt'])+'</td><td>'+number(row['differt_minus_sionna'])+'</td><td>'+esc(row['unit'])+'</td><td>'+esc(row['status'])+'</td></tr>')
    issues = ''.join('<li><strong>Frame '+str(p['frame'])+' · '+esc(p['tx']+' → '+p['rx'])+'</strong>: '+esc('; '.join(p['issues']+p['notes']) or 'Captured inputs and exported geometry agree')+'</li>' for p in report['pairs'])
    options = ''.join('<option value="'+key+'">'+esc(value[0])+'</option>' for key,value in METRICS.items())
    page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>'''+esc(title)+'''</title><style>
body{font:15px system-ui,sans-serif;color:#192b3b;background:#f4f6fa;margin:0;padding:36px}main{max-width:1200px;margin:auto}h1{font-size:30px;margin-bottom:8px}.card{background:white;border:1px solid #dbe3eb;border-radius:12px;padding:22px;margin:18px 0}p,li{line-height:1.6}a{color:#165aa7}select,input{padding:8px;margin:5px;border:1px solid #abb9c8;border-radius:6px}table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:left;padding:10px;border-bottom:1px solid #e3e8ed}td:nth-child(n+4):nth-child(-n+6){font-variant-numeric:tabular-nums;text-align:right}th{position:sticky;top:0;background:#eaf0f7}.scroll{overflow:auto}.muted{color:#526373}code{overflow-wrap:anywhere}
</style><main><p class="muted">RADIO WORKFLOW · PATH RESULTS</p><h1>'''+esc(title)+'''</h1><p>Δ = DiffeRT − Sionna. Links are paired by frame and endpoint names, with the copied DiffeRT_ prefix normalized.</p><div class="card"><strong>Captured runs</strong><p>Sionna: <code>'''+esc(left.get('run_id',''))+'''</code><br>DiffeRT: <code>'''+esc(right.get('run_id',''))+'''</code></p><p>'''+esc(report['scope'])+'''</p><a href="comparison.csv">Download CSV</a> · <a href="comparison.json">Comparison JSON</a> · <a href="sionna.study.json">Sionna snapshot</a> · <a href="differt.study.json">DiffeRT snapshot</a></div><div class="card"><h2>Metrics</h2><label>Metric <select id="metric"><option value="">All metrics</option>'''+options+'''</select></label><label>Filter <input id="filter" placeholder="Frame, endpoint, status…"></label><div class="scroll"><table><thead><tr><th>Frame</th><th>Link</th><th>Metric</th><th>Sionna</th><th>DiffeRT</th><th>Δ</th><th>Unit</th><th>Input check</th></tr></thead><tbody>'''+''.join(body)+'''</tbody></table></div></div><div class="card"><h2>Input checks</h2><ul>'''+issues+'''</ul><h2>Interpretation</h2><ul>'''+''.join('<li>'+esc(x)+'</li>' for x in report['conventions'])+'''</ul></div></main><script>function filter(){let m=document.querySelector('#metric').value,q=document.querySelector('#filter').value.toLowerCase();document.querySelectorAll('tbody tr').forEach(r=>r.hidden=(m&&r.dataset.metric!==m)||!r.textContent.toLowerCase().includes(q))}document.querySelector('#metric').addEventListener('change',filter);document.querySelector('#filter').addEventListener('input',filter);</script></html>'''
    path = directory / 'comparison.html'
    point_coverage.write_report(directory, left, right, report)
    path_diagnostics.write_report(directory, left, right, report, path_tolerance_m)
    page = page.replace('<strong>Captured runs</strong>', '<a href="path_diagnostics.html">Individual path diagnostics</a><br><br><strong>Captured runs</strong>')
    page = page.replace('<strong>Captured runs</strong>', '<a href="point_coverage.html">Shared point coverage and timing</a><br><br><strong>Captured runs</strong>')
    path.write_text(page, encoding='utf-8')
    return path, report

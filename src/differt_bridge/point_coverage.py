"""Shared point sampling and portable spatial reports, independent of Blender."""
import csv
import html
import json
import math
from pathlib import Path


def grid_positions(center, size, columns, rows):
    if not (1 <= columns <= 32 and 1 <= rows <= 32 and columns * rows <= 256):
        raise ValueError('Use 1–32 rows/columns and at most 256 point receivers')
    if len(center) != 3 or len(size) != 2 or not all(math.isfinite(v) for v in (*center, *size)) or min(size) <= 0:
        raise ValueError('Grid center and size must be finite, with positive XY size')
    return [(center[0] + ((i + .5) / columns - .5) * size[0],
             center[1] + ((j + .5) / rows - .5) * size[1], center[2])
            for j in range(rows) for i in range(columns)]


def _position(record, role):
    if record is None:
        return [None] * 3
    name = record['tx' if role == 'transmitters' else 'rx']
    values = record.get('values', {})
    point = [values.get(f'device/{role}/{name}/position/{i}') for i in range(3)]
    return [v if isinstance(v, (float, int)) and math.isfinite(v) else None for v in point]


def samples(left, right, report):
    a = {(r['frame'], r['tx'], r['rx']): r for r in left['records']}
    b = {(r['frame'], str(r['tx']).removeprefix('DiffeRT_'), str(r['rx']).removeprefix('DiffeRT_')): r for r in right['records']}
    counts = {(r['frame'], r['tx'], r['rx']): r for r in report['rows'] if r['metric'] == 'path_count'}
    result = []
    for row in report['rows']:
        if row['metric'] != 'total_power_db': continue
        key = (row['frame'], row['tx'], row['rx'])
        rx_a, rx_b = _position(a.get(key), 'receivers'), _position(b.get(key), 'receivers')
        verified = row['status'] == 'matched_inputs' and all(v is not None for v in rx_a + rx_b)
        result.append(dict(frame=row['frame'], tx=row['tx'], rx=row['rx'], status=row['status'],
            sionna_position=rx_a, differt_position=rx_b, tx_position=_position(a.get(key), 'transmitters'),
            sionna_gain_db=row['sionna'], differt_gain_db=row['differt'],
            delta_db=row['differt_minus_sionna'] if verified else None,
            sionna_paths=counts[key]['sionna'], differt_paths=counts[key]['differt'], plot_eligible=verified))
    return result


def _color(value, lo, hi, delta=False):
    if value is None: return '#acb3bb'
    t = max(0., min(1., (value-lo)/(hi-lo)))
    if delta:
        start, stop = ((49, 103, 169), (248, 248, 248)) if t <= .5 else ((248, 248, 248), (182, 49, 59))
        t = 2*t if t <= .5 else 2*t-1
    else:
        start, stop = (37, 53, 133), (245, 210, 60)
    return '#'+''.join(f'{round(a+(b-a)*t):02x}' for a,b in zip(start,stop))


def _svg(points, key, lo, hi):
    """Uninterpolated scatter: screen distance preserves XY aspect ratio."""
    esc = lambda value: html.escape(str(value), quote=True)
    all_xy = [p['sionna_position'][:2] for p in points]
    all_xy += [p['tx_position'][:2] for p in points if all(v is not None for v in p['tx_position'][:2])]
    xmin, xmax = min(p[0] for p in all_xy), max(p[0] for p in all_xy)
    ymin, ymax = min(p[1] for p in all_xy), max(p[1] for p in all_xy)
    span = max(xmax-xmin, ymax-ymin, 1.) * 1.15
    cx, cy = (xmin+xmax)/2, (ymin+ymax)/2
    xy = lambda p: (190+(p[0]-cx)/span*280, 175-(p[1]-cy)/span*280)
    items = ['<svg role="img" aria-label="Point receiver gains, XY coordinates" viewBox="0 0 380 365">',
             '<rect x="50" y="35" width="280" height="280" fill="#f5f7fa" stroke="#ccd5df"/>']
    for point in points:
        x,y = xy(point['sionna_position']); value = point[key]
        title = f"{point['rx']}: {value if value is not None else 'unavailable'} dB; XYZ {point['sionna_position']}; paths {point['sionna_paths']} / {point['differt_paths']}"
        items.append(f'<circle cx="{x:.3f}" cy="{y:.3f}" r="6" fill="{_color(value,lo,hi,key=="delta_db")}" stroke="#354350" stroke-width=".5"><title>{esc(title)}</title></circle>')
    tx = points[0]['tx_position']
    if all(v is not None for v in tx):
        x,y = xy(tx)
        items.append(f'<path d="M {x-7:.3f},{y:.3f} h 14 M {x:.3f},{y-7:.3f} v 14" stroke="#111" stroke-width="3"><title>{esc(points[0]["tx"])} (TX), XYZ {esc(tx)}</title></path>')
    items += [f'<text x="190" y="350" text-anchor="middle">X: {cx-span/2:.2f} to {cx+span/2:.2f} m</text>',
              f'<text transform="translate(15,175) rotate(-90)" text-anchor="middle">Y: {cy-span/2:.2f} to {cy+span/2:.2f} m</text>', '</svg>']
    return ''.join(items)


def write_report(directory, left, right, comparison):
    directory = Path(directory)
    points = samples(left, right, comparison)
    data = dict(schema='radio_point_coverage_v1', run_ids=comparison['run_ids'],
                quantity='Incoherent path-power sum, first TX/RX antenna pair, point receivers',
                execution={engine: study.get('execution', {}) for engine,study in [('sionna',left),('differt',right)]},
                samples=points)
    (directory/'point_coverage.json').write_text(json.dumps(data, indent=2, allow_nan=False), encoding='utf-8')
    columns = ['frame','tx','rx','status','sionna_x','sionna_y','sionna_z','differt_x','differt_y','differt_z',
               'sionna_gain_db','differt_gain_db','delta_db','sionna_paths','differt_paths','plot_eligible']
    with (directory/'point_coverage.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction='ignore'); writer.writeheader()
        for p in points:
            writer.writerow({**p, **{engine+'_'+axis: p[engine+'_position'][i] for engine in ('sionna','differt') for i,axis in enumerate('xyz')}})
    esc = lambda value: html.escape(str(value), quote=True)
    eligible = [p for p in points if p['plot_eligible']]
    gains = [p[k] for p in eligible for k in ('sionna_gain_db', 'differt_gain_db') if p[k] is not None]
    lo,hi = (min(gains), max(gains)) if gains else (-1., 0.)
    if hi-lo < .01: lo,hi = lo-.5,hi+.5
    delta = max([abs(p['delta_db']) for p in eligible if p['delta_db'] is not None]+[.001])
    groups = {}
    for p in eligible:
        groups.setdefault((p['frame'], p['tx'], p['sionna_position'][2]), []).append(p)
    body = []
    for (frame,tx,z), group in sorted(groups.items()):
        body.append(f'<section><h2>Frame {frame} · {esc(tx)} · receiver Z = {z:.3f} m</h2><div class="plots">')
        for label,key,low,high in [('Sionna','sionna_gain_db',lo,hi),('DiffeRT','differt_gain_db',lo,hi),('DiffeRT − Sionna','delta_db',-delta,delta)]:
            gradient = '#3167a9, #f8f8f8, #b6313b' if key == 'delta_db' else '#253585, #f5d23c'
            body.append('<div><h3>'+label+'</h3>'+_svg(group,key,low,high)+f'<div class="scale" style="background:linear-gradient(to right,{gradient})"></div><p>{low:.5g} to {high:.5g} dB</p></div>')
        body.append('</div></section>')
    timing = []
    for engine, study in [('Sionna',left),('DiffeRT',right)]:
        seconds = study.get('execution',{}).get('wall_seconds_including_export_import')
        timing.append(engine+': '+(f'{seconds:.3f} s' if seconds is not None else 'unrecorded'))
    page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Shared point coverage</title><style>
body{margin:0;padding:32px;background:#f4f6fa;color:#192b3b;font:15px system-ui,sans-serif}main{max-width:1300px;margin:auto}section{background:white;padding:24px;border:1px solid #dbe3eb;border-radius:12px;margin:24px 0}p{line-height:1.6}a{color:#165aa7}.plots{display:grid;grid-template-columns:repeat(3,1fr);gap:24px}svg{width:100%;font-size:12px}.scale{height:12px;margin:0 30px}h3,.plots p{text-align:center}@media(max-width:800px){.plots{grid-template-columns:1fr}}
</style><main><p>RADIO WORKFLOW · POINT RECEIVERS</p><h1>Shared point coverage</h1><p>Incoherent path-power sum for the first antenna pair. Each dot is a receiver; no interpolation or area averaging. The black cross marks the transmitter's XY position. Hover a dot for coordinates, gains and path counts.</p><p>Both gain plots use the same scale. Gray means unavailable (including no paths). Only links with matched captured inputs and verified geometry are plotted; Δ also requires a gain in both engines. Equal inputs do not imply equal physical models.</p><p>'''+str(len(eligible))+' of '+str(len(points))+''' links plotted. All links, including unverified inputs, are retained in the exports.</p><p><a href="comparison.html">Path metrics and input checks</a> · <a href="point_coverage.csv">Point CSV</a> · <a href="point_coverage.json">Point JSON</a></p><p>End-to-end elapsed time (export, worker startup, tracing and import): '''+esc(' · '.join(timing))+'''. These are single runs, not steady-state kernel benchmarks.</p>'''+(''.join(body) or '<section>No verified receiver positions available for plotting.</section>')+'</main></html>'
    (directory/'point_coverage.html').write_text(page, encoding='utf-8')
    return data

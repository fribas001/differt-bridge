"""Portable, bounded depth-sweep plans and auditable workflow benchmark reports."""
import csv
import hashlib
import html
import json
import math
from pathlib import Path
import statistics

ENGINES = ('sionna', 'differt')


def plan(first, last, repeats, seed, vary_seed=False):
    if any(type(v) is not int for v in (first, last, repeats, seed)):
        raise ValueError('Depth, repeats and seed must be integers')
    if not 0 <= first <= last <= 6 or not 1 <= repeats <= 10:
        raise ValueError('Use depths 0–6 in ascending order and 1–10 repeats')
    if (last-first+1)*repeats > 30:
        raise ValueError('A benchmark is limited to 30 paired runs')
    if not 0 <= seed <= 2147483647-(repeats-1 if vary_seed else 0):
        raise ValueError('Seed is outside the supported integer range')
    # Traverse all depths per repeat. Each depth gets both engine orders when
    # there are at least two repeats, even for an even number of depths.
    return [dict(index=r*(last-first+1)+d-first+1, depth=d, repeat=r+1,
                 seed=seed+r if vary_seed else seed,
                 engine_order=list(ENGINES if (r+d-first)%2 == 0 else reversed(ENGINES)))
            for r in range(repeats) for d in range(first,last+1)]


def stats(values):
    values = [v for v in values if isinstance(v, (int,float)) and math.isfinite(v)]
    return dict(n=len(values), median=statistics.median(values) if values else None,
                minimum=min(values) if values else None, maximum=max(values) if values else None)


def fingerprint(study):
    """Within one engine, exclude only planned sweep inputs and display/run IDs."""
    records = []
    for r in study['records']:
        values = {k:v for k,v in r['values'].items()
                  if k not in ('solver/max_depth','solver/seed','solver/sim_numeric_id')}
        records.append(dict(frame=r['frame'],tx=r['tx'],rx=r['rx'],values=values))
    payload = dict(context=study.get('context'), geometry=study.get('geometry_evidence'),
                   bridge=study.get('bridge_version'), records=sorted(records,key=lambda r:(r['frame'],r['tx'],r['rx'])))
    return hashlib.sha256(json.dumps(payload,sort_keys=True,allow_nan=False).encode()).hexdigest()


def collect(folder, spec, baseline, expected_frame):
    folder = Path(folder)
    report = json.loads((folder/'comparison.json').read_text(encoding='utf-8'))
    coverage = json.loads((folder/'point_coverage.json').read_text(encoding='utf-8'))
    issues = []
    signatures = {}
    for engine in ENGINES:
        study = json.loads((folder/(engine+'.study.json')).read_text(encoding='utf-8'))
        signatures[engine] = fingerprint(study)
        if baseline and baseline.get(engine) != signatures[engine]:
            issues.append(engine+': scene or non-sweep inputs changed since the first run')
        if not study['records'] or any(r['frame'] != expected_frame or
                r['values'].get('solver/max_depth') != spec['depth'] or
                r['values'].get('solver/seed') != spec['seed'] for r in study['records']):
            issues.append(engine+': captured frame/depth/seed differs from the plan')
    if not report['pairs'] or any(p['status'] != 'matched_inputs' for p in report['pairs']):
        issues.append('One or more links need input review')
    samples = coverage['samples']
    gains = [abs(p['delta_db']) for p in samples if p['plot_eligible'] and p['delta_db'] is not None]
    counts = {}
    timing = {}
    for engine in ENGINES:
        counts[engine] = sum(p[engine+'_paths'] for p in samples if p[engine+'_paths'] is not None)
        timing[engine] = coverage['execution'].get(engine,{}).get('wall_seconds_including_export_import')
        if not isinstance(timing[engine],(float,int)) or not math.isfinite(timing[engine]) or timing[engine] <= 0:
            timing[engine] = None
            issues.append(engine+': missing elapsed time')
    diagnostics = json.loads((folder/'path_diagnostics.json').read_text(encoding='utf-8'))
    return dict(**spec, eligible=not issues, issues=issues, signatures=signatures,
        run_ids=report['run_ids'], links=len(report['pairs']), timing_seconds=timing,
        path_totals=counts, no_path_links={e:sum(p[e+'_paths']==0 for p in samples) for e in ENGINES},
        path_count_differences=sum(p['sionna_paths']!=p['differt_paths'] for p in samples),
        compared_gain_links=len(gains), max_absolute_gain_delta_db=max(gains,default=None),
        mean_absolute_gain_delta_db=statistics.mean(gains) if gains else None,
        route_counts=diagnostics['counts'], samples=samples)


def summarize(runs):
    groups = []
    for depth in sorted({r['depth'] for r in runs}):
        all_runs = [r for r in runs if r['depth']==depth]
        accepted = [r for r in all_runs if r['eligible']]
        engines = {}
        for engine in ENGINES:
            links = {}
            for r in accepted:
                for s in r['samples']:
                    links.setdefault((s['frame'],s['tx'],s['rx']),[]).append(s)
            gain_spans = []
            changed = 0
            for samples in links.values():
                counts = [s[engine+'_paths'] for s in samples]
                changed += len(counts)>1 and len(set(counts))>1
                gains = [s[engine+'_gain_db'] for s in samples]
                # A gain span needs the same link in every accepted repeat and
                # finite gain in all repeats. No-path transitions stay explicit.
                if len(gains)==len(accepted) and len(gains)>1 and all(g is not None and math.isfinite(g) for g in gains):
                    gain_spans.append(max(gains)-min(gains))
            engines[engine] = dict(time_seconds=stats(r['timing_seconds'][engine] for r in accepted),
                path_totals=stats(r['path_totals'][engine] for r in accepted),
                repeated_gain_links=len(gain_spans), max_gain_span_db=max(gain_spans,default=None),
                links_with_changing_path_count=changed if len(accepted)>1 else None)
        groups.append(dict(depth=depth,completed=len(all_runs),eligible=len(accepted),engines=engines,
            max_absolute_gain_delta_db=max((r['max_absolute_gain_delta_db'] for r in accepted
                if r['max_absolute_gain_delta_db'] is not None),default=None)))
    return groups


def write_report(folder, document):
    """Checkpoint after every pair. Incomplete/cancelled runs remain explicit."""
    folder=Path(folder); folder.mkdir(parents=True,exist_ok=True)
    document['summary'] = summarize(document['runs'])
    target=folder/'benchmark.json'
    temporary=target.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(document,indent=2,allow_nan=False),encoding='utf-8')
    temporary.replace(target)
    fields=['index','depth','repeat','seed','first_engine','eligible','sionna_seconds','differt_seconds',
            'sionna_paths','differt_paths','path_count_differences','compared_gain_links','max_absolute_gain_delta_db','issues','report']
    with (folder/'benchmark.csv').open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for r in document['runs']:
            writer.writerow({**{k:r[k] for k in fields if k in r},'first_engine':r['engine_order'][0],
                **{e+'_seconds':r['timing_seconds'][e] for e in ENGINES},
                **{e+'_paths':r['path_totals'][e] for e in ENGINES},'issues':'; '.join(r['issues'])})
    def show(value):
        return '—' if value is None else f'{value:.6g}' if isinstance(value,float) else html.escape(str(value))
    def time_cell(value):
        return f"{show(value['median'])} [{show(value['minimum'])}, {show(value['maximum'])}]"
    rows=''.join('<tr>'+''.join('<td>'+cell+'</td>' for cell in [show(s['depth']),str(s['eligible'])+'/'+str(s['completed']),
        time_cell(s['engines']['sionna']['time_seconds']),time_cell(s['engines']['differt']['time_seconds']),
        show(s['max_absolute_gain_delta_db']),show(s['engines']['sionna']['max_gain_span_db']),
        show(s['engines']['differt']['max_gain_span_db'])])+'</tr>' for s in document['summary'])
    details=''.join('<tr>'+''.join('<td>'+cell+'</td>' for cell in [show(r['index']),show(r['depth']),show(r['repeat']),
        show(r['seed']),show(r['engine_order'][0]),show(r['timing_seconds']['sionna']),show(r['timing_seconds']['differt']),
        show(r['path_totals']['sionna'])+' / '+show(r['path_totals']['differt']),show(r['max_absolute_gain_delta_db']),
        'Included' if r['eligible'] else html.escape('; '.join(r['issues'])),
        '<a href="'+html.escape(r['report'],quote=True)+'">Inspect run</a>'])+'</tr>' for r in document['runs'])
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sionna / DiffeRT depth benchmark</title><style>body{font:15px system-ui;color:#193047;background:#f4f6fa;margin:0;padding:32px}main{max-width:1350px;margin:auto}section{background:white;border:1px solid #d6dfe8;border-radius:12px;padding:24px;margin:24px 0}p{line-height:1.6}table{border-collapse:collapse;width:100%;white-space:nowrap;font-size:14px}th,td{text-align:left;padding:12px;border-bottom:1px solid #d6dfe8}.scroll{overflow:auto}a{color:#165aaa}summary{cursor:pointer}</style><main><p>DIFFERT-BRIDGE · REPEATED WORKFLOW COMPARISON</p><h1>Path depth benchmark</h1>'''
    page+=f"<p><strong>{html.escape(document['status'])}</strong> · {len(document['runs'])} / {len(document['plan'])} paired runs captured. {html.escape(document.get('message',''))}</p>"
    page+='''<p>Elapsed seconds include scene export, fresh worker startup, tracing and Blender import. Every run starts a new worker process; no runs are discarded as warm-up. OS caches, JIT caches and concurrent system load can affect results. Engine order alternates per depth across repeats. These are local workflow measurements, not isolated kernel or hardware rankings.</p><p><a href="benchmark.csv">Run CSV</a> · <a href="benchmark.json">Full JSON and plan</a></p><section><h2>Timing and signal stability</h2><p>Timing: median [minimum, maximum]. Gain difference: largest |DiffeRT − Sionna| among available verified links. Gain span: largest within-engine per-link range across repeated runs at the same depth; unavailable when fewer than two valid repeats exist. Scene/input changes exclude the affected run from these aggregates.</p><div class="scroll"><table><tr><th>Depth</th><th>Included / captured</th><th>Sionna time (s)</th><th>DiffeRT time (s)</th><th>Max gain Δ (dB)</th><th>Sionna span (dB)</th><th>DiffeRT span (dB)</th></tr>'''+rows+'''</table></div></section><section><h2>Every captured run</h2><p>Path totals are Sionna / DiffeRT. Each run links to point coverage, exact path diagnostics and immutable input snapshots. Depth counts enabled path interactions. Increasing depth changes the physical interaction budget; agreement across these depths does not establish convergence or model equivalence. Unavailable/no-path gains are never replaced by zero. DiffeRT deterministic candidate generation does not consume Sionna's random seed.</p><div class="scroll"><table><tr><th>Run</th><th>Depth</th><th>Repeat</th><th>Seed</th><th>First engine</th><th>Sionna (s)</th><th>DiffeRT (s)</th><th>Paths</th><th>Max gain Δ (dB)</th><th>Audit</th><th>Details</th></tr>'''+details+'''</table></div></section><details><summary>Captured environment and protocol</summary><pre>'''+html.escape(json.dumps(document.get('environment',{}),indent=2))+'''</pre></details></main></html>'''
    (folder/'benchmark.html').write_text(page,encoding='utf-8')
    return folder/'benchmark.html'

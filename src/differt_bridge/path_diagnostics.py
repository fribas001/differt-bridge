"""Match captured point paths without depending on backend-specific object IDs."""
from collections import defaultdict, deque
import csv
import html
import itertools
import json
import math
from pathlib import Path

MAX_PATHS = 20000
MAX_POINTS = 1000000
MAX_CANDIDATE_CHECKS = 250000
REQUIRED_COLUMNS = ('frame','pos_idx','path_index','point_order','point_role_id',
                    'interaction_id','num_events','x','y','z')
METRIC_COLUMNS = ('path_gain_db','delay_ns','phase_rad','doppler_hz')


def finite(value):
    return isinstance(value, (int,float)) and math.isfinite(value)


def phase_convention(study):
    explicit=study.get('path_coefficient_convention') or study.get('path_traces',{}).get('coefficient_convention')
    if explicit:return explicit
    if study.get('schema')=='sionna_parameter_study':return 'passband_without_propagation_phase'
    if study.get('schema')=='differt_parameter_study' and str(study.get('bridge_version','')).startswith(('0.1.','0.2.','0.3.','0.4.','0.5.')):
        return 'legacy_baseband_with_propagation_phase'
    return 'unknown'


def unavailable(study, reason):
    return dict(schema='radio_path_traces_v1', run_id=study['run_id'], source='unavailable',
                reason=reason, links=[])


def from_columns(study, columns, max_paths=MAX_PATHS):
    """Read raw saved point attributes, retaining explicit per-link coverage."""
    missing=[name for name in REQUIRED_COLUMNS if name not in columns]
    if missing: return unavailable(study, 'Missing saved attributes: '+', '.join(missing))
    n=len(columns['frame'])
    if any(len(values)!=n for values in columns.values()):
        return unavailable(study, 'Saved attribute lengths differ')
    if n>MAX_POINTS: return unavailable(study, 'Point capture exceeds the 1,000,000-point limit')
    links={}
    for record in study['records']:
        key=(int(record['frame']),int(record['pair']))
        if key in links: return unavailable(study, 'Ambiguous frame/link indices')
        links[key]=dict(frame=key[0],pair=key[1],tx=record['tx'],rx=record['rx'],
            expected_paths=record.get('metrics',{}).get('path_count'), paths=[], issues=[])
    groups={}; dropped=set()
    for i in range(n):
        if not all(finite(columns[name][i]) for name in REQUIRED_COLUMNS):
            return unavailable(study, 'Nonfinite path coordinates or identifiers')
        key=(int(columns['frame'][i]),int(columns['pos_idx'][i]),int(columns['path_index'][i]))
        if key[:2] not in links: return unavailable(study, 'Saved path has no corresponding link summary')
        if key not in groups:
            if len(groups)>=max_paths:
                dropped.add(key[:2]); continue
            groups[key]=[]
        groups[key].append(i)
    for (frame,pair,path_index),indices in sorted(groups.items()):
        link=links[(frame,pair)]
        indices.sort(key=lambda i:columns['point_order'][i])
        first=indices[0]; count=len(indices)
        if ([int(columns['point_order'][i]) for i in indices]!=list(range(count)) or count<2
            or int(columns['point_role_id'][first])!=1 or int(columns['point_role_id'][indices[-1]])!=3
            or any(int(columns['point_role_id'][i])!=2 for i in indices[1:-1])
            or any(int(columns['num_events'][i])!=count-2 for i in indices)):
            link['issues'].append(f'Invalid vertex sequence for path {path_index}'); continue
        path=dict(path_index=path_index,points=[[float(columns[k][i]) for k in ('x','y','z')] for i in indices],
                  interactions=[int(columns['interaction_id'][i]) for i in indices[1:-1]])
        if any(value not in (1,2,4,8) for value in path['interactions']):
            link['issues'].append(f'Unsupported interaction flag in path {path_index}'); continue
        for name in METRIC_COLUMNS:
            value=columns[name][first] if name in columns else None
            path[name]=float(value) if finite(value) else None
        link['paths'].append(path)
    for key,link in links.items():
        expected=link['expected_paths']; count=len(link['paths'])
        if key in dropped: link['issues'].append(f'Capture limited to {max_paths} paths per engine')
        if not finite(expected): link['coverage']='unknown'
        elif count>expected or link['issues']: link['coverage']='incomplete'
        else: link['coverage']='complete' if count==expected else 'subset'
        link['captured_paths']=count
    return dict(schema='radio_path_traces_v1',run_id=study['run_id'],source='embedded_float32_point_attributes',
                coefficient_convention=phase_convention(study),
                links=list(links.values()))


def _index(study, copied=False):
    capture=study.get('path_traces',{})
    if capture.get('run_id')!=study.get('run_id'): return {}
    output={}
    for link in capture.get('links',[]):
        name=lambda value: str(value).removeprefix('DiffeRT_') if copied else str(value)
        key=(int(link['frame']),name(link['tx']),name(link['rx']))
        if key in output: raise ValueError('Ambiguous captured path endpoints')
        paths=link.get('paths',[])
        if len({p['path_index'] for p in paths})!=len(paths):raise ValueError('Duplicate captured path IDs')
        for path in paths:
            if len(path['points'])!=len(path['interactions'])+2 or any(len(p)!=3 or not all(finite(v) for v in p) for p in path['points']):
                raise ValueError('Invalid captured path geometry')
        output[key]=link
    return output


def _match(a,b,tolerance,budget):
    """Maximum-cardinality matching; non-unique local choices stay ambiguous."""
    def cell(path):
        point=path['points'][1 if path['interactions'] else 0]
        return tuple(math.floor(v/tolerance) for v in point)
    buckets=defaultdict(list)
    for j,path in enumerate(b): buckets[(tuple(path['interactions']),cell(path))].append(j)
    adjacency={}; reverse=defaultdict(list); checks=0; errors={}
    for i,path in enumerate(a):
        center=cell(path); candidates=[]
        for offset in itertools.product((-1,0,1),repeat=3):
            key=(tuple(path['interactions']),tuple(x+y for x,y in zip(center,offset)))
            for j in buckets.get(key,[]):
                checks+=1
                if checks>budget:raise ValueError('Candidate matching limit exceeded; narrow the selected result')
                distance=max(math.dist(x,y) for x,y in zip(path['points'],b[j]['points']))
                if distance<=tolerance:
                    candidates.append((distance,j));reverse[j].append(i);errors[(i,j)]=distance
        adjacency[i]=[j for _,j in sorted(candidates)]
    match_a={};match_b={}
    for root in sorted(adjacency,key=lambda i:(len(adjacency[i]),i)):
        queue=deque([root]); seen_a={root}; prev_b={}; found=False
        while queue and not found:
            i=queue.popleft()
            for j in adjacency[i]:
                if j in prev_b:continue
                prev_b[j]=i
                if j not in match_b:
                    while j is not None:
                        i=prev_b[j]; old=match_a.get(i)
                        match_a[i]=j;match_b[j]=i;j=old
                    found=True;break
                owner=match_b[j]
                if owner not in seen_a:seen_a.add(owner);queue.append(owner)
    return match_a,match_b,adjacency,reverse,errors


def compare(left,right,comparison,tolerance_m=.001,budget=MAX_CANDIDATE_CHECKS):
    if not finite(tolerance_m) or not 1e-6<=tolerance_m<=1:
        raise ValueError('Path matching tolerance must be between 0.001 and 1000 mm')
    a,b=_index(left),_index(right,True)
    conventions={name:phase_convention(study) for name,study in [('sionna',left),('differt',right)]}
    phase_comparable=(conventions['sionna']==conventions['differt'] and conventions['sionna'] in
                      ('passband_without_propagation_phase','baseband_with_propagation_phase'))
    rows=[];links=[]
    for pair in comparison['pairs']:
        key=(pair['frame'],pair['tx'],pair['rx']);x,y=a.get(key),b.get(key)
        link={k:pair[k] for k in ('frame','tx','rx','status')}
        link.update(sionna_coverage=x.get('coverage') if x else 'unavailable',differt_coverage=y.get('coverage') if y else 'unavailable')
        for engine,capture in (('sionna',x),('differt',y)):
            link[engine+'_captured']=len(capture['paths']) if capture else None
            link[engine+'_expected']=capture.get('expected_paths') if capture else None
        link['issues']=list((x or {}).get('issues',[]))+list((y or {}).get('issues',[]))
        if pair['status']!='matched_inputs':link['diagnostics']='input_review_required'
        elif x is None or y is None:link['diagnostics']='traces_unavailable'
        else:
            aa,bb=x['paths'],y['paths']
            # Imported snapshots cannot promote an inconsistent capture to complete.
            complete=all(z.get('coverage')=='complete' and len(z['paths'])==z.get('expected_paths') for z in (x,y))
            try:
                ma,mb,adj,rev,errors=_match(aa,bb,tolerance_m,budget)
                link['diagnostics']='complete' if complete else 'captured_subset'
                matches=[(i,ma.get(i)) for i in range(len(aa))]+[(None,j) for j in range(len(bb)) if j not in mb]
                for i,j in matches:
                    p,q=aa[i] if i is not None else None,bb[j] if j is not None else None
                    if p is not None and q is not None:
                        status='matched' if len(adj[i])==len(rev[j])==1 else 'ambiguous_match'
                    elif p is not None:
                        status='ambiguous_sionna' if adj[i] else 'sionna_only' if complete else 'sionna_unmatched_subset'
                    else:
                        status='ambiguous_differt' if rev[j] else 'differt_only' if complete else 'differt_unmatched_subset'
                    row={k:pair[k] for k in ('frame','tx','rx')}
                    row.update(status=status,coverage=link['diagnostics'],sionna=p,differt=q,
                               max_vertex_error_m=errors.get((i,j)),id=len(rows))
                    for metric in METRIC_COLUMNS:
                        av,bv=(p or {}).get(metric),(q or {}).get(metric)
                        value=bv-av if status=='matched' and finite(av) and finite(bv) else None
                        if metric=='phase_rad':
                            value=(value+math.pi)%(2*math.pi)-math.pi if value is not None and phase_comparable else None
                        row['delta_'+metric]=value
                    rows.append(row)
            except ValueError as exc:
                link['diagnostics']='matching_unavailable';link['issues'].append(str(exc))
        links.append(link)
    counts={status:sum(r['status']==status for r in rows) for status in sorted({r['status'] for r in rows})}
    return dict(schema='radio_path_diagnostics_v1',run_ids=comparison['run_ids'],tolerance_m=tolerance_m,
        phase_conventions=conventions,phase_comparable=phase_comparable,
        scope='Ordered vertices and interaction flags; first TX/RX antenna pair; embedded float32 coordinates. Backend object IDs and path indices are not shared identities.',
        capture_sources={engine:study.get('path_traces',{}).get('source','unavailable') for engine,study in [('sionna',left),('differt',right)]},
        counts=counts,links=links,rows=rows)


def write_report(directory,left,right,comparison,tolerance_m=.001):
    directory=Path(directory)
    data=compare(left,right,comparison,tolerance_m)
    (directory/'path_diagnostics.json').write_text(json.dumps(data,indent=2,allow_nan=False),encoding='utf-8')
    fields=['frame','tx','rx','status','coverage','sionna_path_index','differt_path_index','max_vertex_error_m']
    fields += [engine+'_'+metric for metric in METRIC_COLUMNS for engine in ('sionna','differt','delta')]
    with (directory/'path_diagnostics.csv').open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore');writer.writeheader()
        for row in data['rows']:
            flat=dict(row)
            for engine in ('sionna','differt'):
                for name in ('path_index',*METRIC_COLUMNS):flat[engine+'_'+name]=(row[engine] or {}).get(name)
            writer.writerow(flat)
    esc=lambda v:html.escape(str(v),quote=True)
    number=lambda v:'—' if v is None else f'{v:.6g}'
    body=[]
    for row in data['rows']:
        p,q=row['sionna'] or {},row['differt'] or {}
        body.append(f'<tr data-row="{row["id"]}" data-status="{esc(row["status"])}" tabindex="0"><td>{row["frame"]}</td><td>{esc(row["tx"]+" → "+row["rx"])}</td><td>{esc(row["status"])}</td><td>{p.get("path_index","—")} / {q.get("path_index","—")}</td><td>{number(row["delta_path_gain_db"])}</td><td>{number(row["delta_delay_ns"])}</td><td>{number(row["delta_phase_rad"])}</td><td>{number(row["max_vertex_error_m"])}</td></tr>')
    coverage=lambda r,engine: f'{r[engine+"_coverage"]} ({number(r[engine+"_captured"])}/{number(r[engine+"_expected"])})'
    checks=''.join(f'<tr><td>{r["frame"]}</td><td>{esc(r["tx"]+" → "+r["rx"])}</td><td>{esc(r["diagnostics"])}</td><td>{esc(coverage(r,"sionna")+" / "+coverage(r,"differt"))}</td><td>{esc("; ".join(r["issues"]))}</td></tr>' for r in data['links'])
    template=Path(__file__).with_name('path_diagnostics.html').read_text(encoding='utf-8')
    replacements={'__DATA__':json.dumps(data,allow_nan=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026'),
                  '__ROWS__':''.join(body),'__CHECKS__':checks,'__TOLERANCE__':number(tolerance_m*1000),
                  '__COUNTS__':esc('; '.join(f'{k}: {v}' for k,v in data['counts'].items()) or 'No comparable captured paths')}
    replacements['__PHASE_NOTE__']=esc('Phase deltas compare '+data['phase_conventions']['sionna']+'.' if data['phase_comparable'] else
        'Phase deltas are unavailable: coefficient conventions differ or are unknown. DiffeRT-Bridge 0.1–0.5 saved baseband phase; rerun with 0.6 or later for comparison with Sionna paths.a. Raw saved phases are retained.')
    # Replace template markers once, never interpreting marker-like endpoint names.
    import re
    page=re.sub('|'.join(re.escape(k) for k in replacements),lambda m:replacements[m[0]],template)
    (directory/'path_diagnostics.html').write_text(page,encoding='utf-8')
    return data

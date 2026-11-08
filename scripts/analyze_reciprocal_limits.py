"""Exact-boundary and mixed-path measurements, including physical normalization."""
import argparse,json
from pathlib import Path
import numpy as np
from diffraction_reference import stationary_edge,C

read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))

def coincidence(folder):
    cases={c['name']:c for c in read(folder/'cases.json')['cases']};result=[]
    for file in folder.glob('*reciprocal/*_float32.json'):
        for row in read(file)['cases']:
            c=cases[row['name']];meta=c['study']
            if meta['kind']!='boundary':continue
            offsets=meta['offsets_deg'];indices=[offsets.index(x) for x in (-.0001,0.,.0001)]
            fields=[sum(complex(*p['cir']) for p in row['paths'] if p['rx']==i) for i in indices]
            tx=np.asarray(c['tx']);rx=np.asarray(c['receivers'][indices[1]])
            q=stationary_edge(tx,rx,c['canonical_edges'][0]);length=np.linalg.norm(q-tx)+np.linalg.norm(rx-q)
            scale=C/c['frequency_hz']/(4*np.pi*length);error=abs(fields[1]-(fields[0]+fields[2])/2)
            result.append(dict(profile=file.parent.name,name=row['name'],material=meta['material'],absolute_error=error,
                free_space_channel_scale=scale,normalization_length_m=length,normalized_error=error/scale,
                field_values=[[v.real,v.imag] for v in fields],path_counts=[sum(p['rx']==j for p in row['paths']) for j in indices]))
    return result

def mixed(folders):
    pairs=[];blocks=[]
    for folder in folders:
        for file in folder.glob('*reciprocal/*_float32.json'):
            rows={r['name']:r for r in read(file)['cases']}
            for name,a in rows.items():
                if 'block' in name:
                    passed=not any(p['interactions'] in ([1,8],[8,1]) and any(abs(q[2]+3)<1e-6 for q in p['points'][1:-1]) for p in a['paths'])
                    blocks.append(dict(profile=file.parent.name,name=name,passed=passed,remaining_paths=len(a['paths'])));continue
                if '__reverse' in name:continue
                b=rows[name+'__reverse']
                for x in a['paths']:
                    y=next(p for p in b['paths'] if p['interactions']==x['interactions'][::-1])
                    u,v=complex(*x['a']),complex(*y['a'])
                    pairs.append(dict(run=folder.name,profile=file.parent.name,name=name,interactions=x['interactions'],
                        gain_gap_db=float(abs(20*np.log10(abs(v/u)))),relative_complex_error=float(abs(u-v)/max(abs(u),abs(v))),
                        max_reversed_vertex_error_m=float(np.max(np.linalg.norm(np.asarray(x['points'])-np.asarray(y['points'])[::-1],axis=1)))))
    return dict(pairs=pairs,obstacle_controls=blocks,maximum_corrected_sionna_gain_gap_db=max(r['gain_gap_db'] for r in pairs if r['profile']=='sionna-reciprocal'))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--main',type=Path,required=True);ap.add_argument('--mixed',type=Path,required=True);ap.add_argument('--depth-control',type=Path);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'coincidence.json').write_text(json.dumps(coincidence(args.main),indent=2,allow_nan=False),encoding='utf-8')
    (args.output/'mixed_analysis.json').write_text(json.dumps(mixed([args.mixed]+([args.depth_control] if args.depth_control else [])),indent=2,allow_nan=False),encoding='utf-8')

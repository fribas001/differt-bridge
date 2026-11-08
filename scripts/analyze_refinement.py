"""Validate full-wave refinement exclusively against the independent FDFD data."""
import argparse,json
from pathlib import Path
import numpy as np
from analyze_model_errors import read,z,pair,metrics,relative
from line_source_comparison import channel

def analyze(root):
    work=root/'work/maxwell-refinement';refs={};reference_checks=[]
    for file in sorted((work/'fdfd').glob('*_80.json')):
        name=file.stem[:-3];raw={p:read(work/'fdfd'/f'{name}_{p}.json') for p in (40,60,80)}
        u={p:z(r['field']) for p,r in raw.items()}
        assert all(r['sources']==raw[80]['sources'] and r['receivers']==raw[80]['receivers'] for r in raw.values())
        e1=(3600*u[60]-1600*u[40])/2000;e2=(6400*u[80]-3600*u[60])/2800;refs[name]=e2
        reference_checks.append(dict(name=name,grid60_to80=relative(u[60],u[80]),extrapolation_change=relative(e1,e2),max_linear_residual=max(r['linear_residual'] for r in raw.values()),max_reciprocity=max(r['reciprocity_residual'] for r in raw.values()),field=pair(e2),sources=raw[80]['sources'],receivers=raw[80]['receivers']))
    assert len(refs)==8,'Incomplete reference campaign'
    fine=read(work/'final24.json');coarse={r['name']:r for r in read(work/'final16.json')['results']};po={r['name']:r for r in read(work/'physical_optics.json')['results']}
    refinement=[]
    for r in fine['results']:
        name=r['name'];u=z(r['field']);ref=refs[name]
        refinement.append(dict(name=name,**metrics(u,ref),coarse_to_fine=relative(z(coarse[name]['field']),u),raw_forward_rms=relative(z(r['raw_forward']),ref),raw_reverse_rms=relative(z(r['raw_reverse']),ref),raw_reciprocity_rms=r['raw_reciprocity_rms'],physical_optics_rms=relative(z(po[name]['field']),ref),elapsed_seconds=r['elapsed_seconds'],source_count=len(r['sources']),receiver_count=len(r['receivers']),field=r['field']))
    cases={c['name']:c for c in read(root/'work/mre/cases.json')['cases']};receipts=read(root/'work/mre/receipt.json');assert receipts['status']=='passed'
    comparisons=[]
    for receipt in receipts['processes']:
        groups={};profile=receipt['profile']
        for row in read(root/'work/mre'/profile/receipt['output'])['cases']:
            c=cases[row['name']];s=c['study'];name=s['material']+'_'+s['polarization'];i=s['source_index']
            for j in range(len(c['receivers'])):
                u,go,d=channel(c,row,j);ref=refs[name][i,j]
                h=next(r for r in refinement if r['name']==name);refined=z(h['field'])[i,j]
                groups.setdefault(name,[]).append(dict(source=i,receiver=j,angle_deg=s['receiver_angles_deg'][j],prediction=pair(u),reference=pair(ref),refined=pair(refined),go=pair(go),diffracted=pair(d)))
        for name,entries in groups.items():
            a=z([e['prediction'] for e in entries]);b=z([e['reference'] for e in entries]);go=z([e['go'] for e in entries]);h=z([e['refined'] for e in entries])
            comparisons.append(dict(profile=profile,name=name,**metrics(a,b,go),refined_metrics=metrics(h,b),entries=entries))
    controls=[]
    for file in (work/'fdfd_pml').glob('*_60.json'):
        controls.append(dict(name=file.stem,relative_change=relative(z(read(file)['field']),z(read(work/'fdfd'/file.name)['field']))))
    return dict(mode='optional_fullwave_2d',runtime_ray_physics_modified=False,independent_reference='FDFD differential operator with 40/60/80-grid Richardson estimate; BIE output is not its own reference',reference_checks=reference_checks,refinement=refinement,comparisons=comparisons,pml_controls=controls,engine_receipt=receipts)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('root',type=Path);args=ap.parse_args();root=args.root.resolve();r=analyze(root)
    (root/'work/maxwell-refinement/analysis.json').write_text(json.dumps(r,indent=2,allow_nan=False))
    for row in r['refinement']:print(row['name'],'fullwave RMS %',100*row['total_complex_rms'],'PO RMS %',100*row['physical_optics_rms'],'16-24 %',100*row['coarse_to_fine'])

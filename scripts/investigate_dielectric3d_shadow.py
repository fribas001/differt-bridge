"""Audit unfitted local finite-distance candidates before promoting any model."""
import json,sys
from pathlib import Path
import numpy as np
from analyze_dielectric3d import z,pairs,read,metrics

def main(root):
    prior=root/'work/dielectric3d';out=root/'work/d3shadow';cases={c['name']:c for c in read(prior/'cases.json')['cases']}
    references={m:z(read(prior/f'{m}_fem{n}/result.json')['field']) for m,n in [('concrete',48),('lower',32)]}
    rows=[];totals={}
    for engine in ('sionna','differt'):
        raw=read(root/f'work/d3f/{engine}-reciprocal/{engine}_float32.json')['cases']
        for r in raw:
            c=cases[r['name']];s=c['study']
            if s['group']!='primary' or s['source_index']!=0:continue
            n=len(c['receivers']);values={key:np.zeros(n,complex) for key in ('baseline','incident_only','symmetric_endpoints')}
            for path in r['paths']:
                v=complex(*path['cir']);i=path['rx'];f1=f2=1.
                if path['interactions']==[8]:
                    p=np.array(path['points']);a=np.linalg.norm(p[1]-p[0]);b=np.linalg.norm(p[-1]-p[-2]);factor=lambda d:1-1j/(2*np.pi*d)-1/(2*np.pi*d)**2
                    f1=factor(a);f2=factor(b)
                values['baseline'][i]+=v;values['incident_only'][i]+=v*f1;values['symmetric_endpoints'][i]+=v*f1*f2
            ref=references[s['material']][s['height_index']*n:(s['height_index']+1)*n,'xyz'.index(s['rx_axis']),'xyz'.index(s['tx_axis'])]
            mask=np.array(s['angles'])>240.02
            for label,v in values.items():
                rows.append(dict(engine=engine,name=c['name'],candidate=label,field=pairs(v),reference=pairs(ref),shadow_mask=mask.tolist(),metrics=metrics(v[mask],ref[mask])))
                aa,bb=totals.setdefault((engine,label),([],[]));aa.extend(v[mask]);bb.extend(ref[mask])
    aggregates=[dict(engine=e,candidate=c,**metrics(np.array(a),np.array(b))) for (e,c),(a,b) in totals.items()]
    result=dict(status='completed',scope='Unfitted diagnostic only. Endpoint factors are the exact transverse free-dipole factors; multiplying a local UTD field by them does not supply its missing longitudinal/angular derivative or dielectric volume physics.',reference='Previous independently validated FEM48/FEM32 campaign, fixed before this probe',promoted=False,aggregates=aggregates,comparisons=rows)
    (out/'local_candidates.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(aggregates))

if __name__=='__main__':main(Path(sys.argv[1]).resolve())

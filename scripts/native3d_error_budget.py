"""Separate free-space port error, GO near field, and true diffraction residual."""
import json
from pathlib import Path
import numpy as np
from maxwell3d_pec_reference import polar,free_dyadic,free_far_dyadic
from analyze_model_errors import read,z,pair
from analyze_native3d import metrics

def exact_go(source,receiver):
    rs,ps=polar(source);rr,pr=polar(receiver);value=np.zeros(3,complex);margin=np.pi
    for phi,sign in ((ps,1),(-ps,-1)):
        for m in range(-3,4):
            angle=phi+3*np.pi*m;gap=np.pi-abs(pr-angle);margin=min(margin,abs(gap))
            if gap>1e-12:
                image=np.array([-rs*np.sin(angle),rs*np.cos(angle),source[2]])
                value+=sign*free_dyadic(image,receiver)[:,2]
    return 1.5*value,margin

def main(root):
    w=root/'work/native3d';a=read(w/'final_analysis.json');cases={c['name']:c for c in read(root/'work/n3r/cases.json')['cases']};refined={r['name']:r for r in a['refinement']};rows=[];free=[]
    for engine in ('sionna','differt'):
        raw={r['name']:r for r in read(root/f'work/n3f/{engine}-reciprocal/{engine}_float32.json')['cases']}
        for entry in a['updated']:
            if entry['profile']!=engine+'-reciprocal' or entry['name'] not in cases:continue
            c=cases[entry['name']];axis={'x':0,'y':1,'z':2}[c['study']['receiver_axis']]
            if c['study']['group']=='free':
                far=np.array([1.5*free_far_dyadic(c['tx'],r)[axis,2] for r in c['receivers']]);free.append(dict(engine=engine,name=c['name'],native_vs_analytic_far_field_rms=metrics(z(entry['field']),far)['total_complex_rms'],native_vs_full_maxwell_rms=entry['total_complex_rms']));continue
            if c['study']['group']!='sweep' or entry['reference_null']:continue
            v=[];r=[];h=[];indices=[]
            for j,receiver in enumerate(c['receivers']):
                go,margin=exact_go(c['tx'],receiver)
                if margin<1e-4:continue
                indices.append(j);r.append(z(entry['reference'])[j]-go[axis]);h.append(z(refined[c['name']]['field'])[j]-go[axis])
                v.append(sum(complex(*p['cir']) for p in raw[c['name']]['paths'] if p['rx']==j and 8 in p['interactions']))
            rows.append(dict(engine=engine,name=c['name'],samples=len(indices),receiver_indices=indices,native_diffraction=metrics(v,r),hertz_diffraction=metrics(h,r),native=pair(v),reference=pair(r),corrected=pair(h)))
    assert max(r['native_vs_analytic_far_field_rms'] for r in free)<1e-5
    result=dict(status='passed',scope='Diffraction-only field after subtracting exact Maxwell GO images; exclude angles within 1e-4 rad of every GO transition, whose allocation conventions differ.',free_space=free,results=rows)
    (w/'error_budget.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    for r in rows:
        if r['engine']=='sionna' and r['name'] in ('zz_s1_h0_p60','zz_s1_h8_p60','zz_s4_h8_p60','zx_h8','zy_h8'):print(r['name'],r['samples'],100*r['native_diffraction']['total_complex_rms'],100*r['hertz_diffraction']['total_complex_rms'])
    print('free_space',free,flush=True)

if __name__=='__main__':
    import sys
    main(Path(sys.argv[1]).resolve())

"""Join native, corrected, holdout and independent Maxwell evidence."""
import json,hashlib
from pathlib import Path
import numpy as np
from analyze_model_errors import read,z,pair,relative
from analyze_native3d import metrics
from hertz_pec3d import refine

def main(root):
    w=root/'work/native3d';a=read(w/'analysis.json');cases=read(root/'work/n3r/cases.json')['cases'];refs=read(w/'reference_fields.json')['fields']
    selected=[c for c in cases if c['study']['group'] in ('sweep','boundary')]
    (w/'workflow_cases.json').write_text(json.dumps(dict(cases=selected),indent=2),encoding='utf-8')
    (w/'smoke_cases.json').write_text(json.dumps(dict(cases=[selected[8],selected[20],selected[-1]]),indent=2),encoding='utf-8')
    p=refine(selected);product_sha=p['source_sha256'];(w/'primary_refined.json').write_text(json.dumps(p,indent=2),encoding='utf-8')
    fields={r['name']:z(r['field']) for r in p['results']};a['refinement']=[];a['updated']=[]
    for c in selected:
        u=fields[c['name']];ref=z(refs[c['name']]);a['refinement'].append(dict(name=c['name'],study=c['study'],**metrics(u,ref),field=pair(u)))
    for folder,cs,reference in [('n3f',cases,refs),('n3h',read(w/'holdout_cases.json')['cases'],{r['name']:r['reference'] for r in read(w/'holdout_validation.json')['results']})]:
        rec=read(root/'work'/folder/'receipt.json');assert rec['status']=='passed'
        for record in rec['processes']:
            path=root/'work'/folder/record['profile']/record['output'];assert hashlib.sha256(path.read_bytes()).hexdigest()==record['output_sha256']
            rows={r['name']:r for r in read(path)['cases']}
            for c in cs:
                u=[sum(complex(*p['cir']) for p in rows[c['name']]['paths'] if p['rx']==j) for j in range(len(c['receivers']))]
                a['updated'].append(dict(profile=record['profile'],name=c['name'],study=c['study'],**metrics(u,z(reference[c['name']])),field=pair(u),reference=reference[c['name']]))
    a['holdout']=read(w/'holdout_validation.json')['results'];a['hertz_convergence']=read(w/'hertz_candidate.json')['results'];a['opaque_slab']=read(w/'opaque_slab_validation.json')
    a['patch_controls']=[]
    for engine in ('sionna','differt'):
        new={r['name']:r for r in a['updated'] if r['profile']==engine+'-reciprocal'}
        u=z(new['pec_sigma1e+16']['field']);v=z(new['zz_s1_h8_p60']['field'])
        a['patch_controls'].append(dict(engine=engine,conductivity_limit_change=relative(u,v),maxwell_rms=new['pec_sigma1e+16']['total_complex_rms']))
    # Fresh regression campaign: source-only slab change must preserve accepted
    # path topology/geometry and ordinary-material coefficients.
    oldroot=root/'work/dielectric-corrections/final';newroot=root/'work/n3g'
    old={r['name']:r for r in read(oldroot/'sionna-reciprocal/sionna_float32.json')['cases']}
    new=read(newroot/'sionna-reciprocal/sionna_float32.json')['cases'];assert read(newroot/'receipt.json')['status']=='passed'
    maxerr=0.;geometry=True;count=0
    for row in new:
        other=old[row['name']]
        key=lambda p:(p['rx'],tuple(p['interactions']),tuple(np.asarray(p['points']).ravel()))
        p=sorted(row['paths'],key=key);q=sorted(other['paths'],key=key);count+=1
        assert len(p)==len(q),(row['name'],len(p),len(q))
        for x,y in zip(p,q):
            geometry &= x['interactions']==y['interactions'] and x['points']==y['points'] and x['rx']==y['rx']
            maxerr=max(maxerr,abs(complex(*x['cir'])-complex(*y['cir'])))
    a['regression']=dict(cases=count,geometry_identical=bool(geometry),max_absolute_cir_change=maxerr)
    assert geometry and maxerr<1e-7,a['regression']
    # A correction is accepted only if every non-null primary and holdout
    # group improves BOTH installed-profile engines against independent data.
    for r in a['refinement']+a['holdout']:
        if r['reference_null']:continue
        for engine in ('sionna','differt'):
            before=next(v for v in a['updated'] if v['profile']==engine+'-reciprocal' and v['name']==r['name'])
            assert r['total_complex_rms']<before['total_complex_rms'],(r['name'],r['total_complex_rms'],before['total_complex_rms'])
    assert a['opaque_slab']['status']=='passed' and max(c['conductivity_limit_change'] for c in a['patch_controls'])<1e-6
    a.update(status='passed',fix_scope='Sionna opaque-slab phase fix in opt-in reciprocal profile; optional shared canonical 3D PEC Hertz-UTD correction; no global dielectric UTD replacement',total_engine_fixture_executions=168+84+24+len(new),updated_engine_channels=sum(r['samples'] for r in a['updated']),product_source_sha256=product_sha)
    (w/'final_analysis.json').write_text(json.dumps(a,indent=2,allow_nan=False),encoding='utf-8')
    print('FINAL_NATIVE3D_PASS',a['regression'],a['patch_controls'],flush=True)

if __name__=='__main__':
    import sys
    main(Path(sys.argv[1]).resolve())

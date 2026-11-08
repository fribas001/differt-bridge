"""Compare native CIR fields directly with independent 3D Maxwell fields."""
import argparse,hashlib,json,time
from pathlib import Path
import numpy as np
from maxwell3d_pec_reference import wedge_green,electric_z_column,free_dyadic,free_far_dyadic
from analyze_model_errors import read,pair,z,relative

def metrics(a,b):
    a=np.asarray(a);b=np.asarray(b);scale=np.linalg.norm(b)
    mask=(abs(b)>max(float(abs(b).max())*.01,1e-14))&(abs(a)>1e-14)
    ratio=a[mask]/b[mask]
    return dict(samples=a.size,total_complex_rms=float(np.linalg.norm(a-b)/scale) if scale>1e-13 else None,
                max_absolute_error=float(abs(a-b).max()),phase_mask_threshold_db=-40,phase_mask_samples=int(mask.sum()),
                masked_p95_abs_phase_rad=float(np.percentile(abs(np.angle(ratio)),95)) if len(ratio) else None,
                masked_p95_abs_gain_db=float(np.percentile(abs(20*np.log10(abs(ratio))),95)) if len(ratio) else None,
                reference_null=bool(scale<=1e-13))

def exact(c,j):
    st=c['study'];axis={'x':0,'y':1,'z':2}[st['receiver_axis']]
    s=np.asarray(c['tx']);r=np.asarray(c['receivers'][j])
    if 'reverse_of' in st:s,r=r,s
    if st['group']=='free':return 1.5*free_dyadic(s,r)[axis,2]
    if axis==2:return 1.5*wedge_green(s,r)
    return 1.5*electric_z_column(s,r)[axis]

def go_correction(c,paths):
    """Diagnostic: only replace accepted GO fields by exact dipole/image fields.

    All original diffraction paths are retained. This correction is NOT a
    general diffraction fix: near transition boundaries it can break the
    cancellation between GO and UTD. It is evaluated but not installed.
    """
    axis={'x':0,'y':1,'z':2}[c['study']['receiver_axis']];delta=0j
    reverse='reverse_of' in c['study']
    for p in paths:
        if 8 in p['interactions']:continue
        s=np.array(p['points'][0]);r=np.array(p['points'][-1])
        tx=np.eye(3)[axis if reverse else 2];rx=np.eye(3)[2 if reverse else axis]
        if p['interactions']:
            if p['interactions']!=[1]:raise ValueError('Only one planar PEC reflection')
            q=np.asarray(p['points'][1]);normal=np.eye(3)[0 if abs(q[0])<abs(q[1]) else 1]
            s=s-2*np.dot(s,normal)*normal
            tx=2*normal*np.dot(tx,normal)-tx
        delta+=1.5*(rx@(free_dyadic(s,r)-free_far_dyadic(s,r))@tx)
    return delta

def main(root):
    work=root/'work/native3d';receipt=read(root/'work/n3r/receipt.json');assert receipt['status']=='passed'
    cases=read(root/'work/n3r/cases.json')['cases'];validation=read(work/'reference_validation.json');assert validation['status']=='passed'
    cache=work/'reference_fields.json';case_sha=hashlib.sha256((root/'work/n3r/cases.json').read_bytes()).hexdigest()
    source_sha=hashlib.sha256(Path(__file__).with_name('maxwell3d_pec_reference.py').read_bytes()).hexdigest()
    if cache.exists():
        saved=read(cache);assert saved['manifest_sha256']==case_sha and saved['reference_source_sha256']==source_sha
        refs=saved['fields']
    else:
        refs={}
        for c in cases:
            refs[c['name']]=pair([exact(c,j) for j in range(len(c['receivers']))]);print('REFERENCE',c['name'],flush=True)
        cache.write_text(json.dumps(dict(manifest_sha256=case_sha,reference_source_sha256=source_sha,fields=refs),indent=2),encoding='utf-8')
    out=dict(date='2026-11-07',domain='3D point electric dipole; ideal infinite PEC right-angle wedge; z-directed source and z/x/y receiver; SI wavelength 1 m',normalization='1.5 lambda times electric Green dyadic; analytic short-dipole gain, no fit, actual engine CIR including propagation phase',manifest_sha256=case_sha,reference_source_sha256=source_sha,reference_validation=validation,comparisons=[],controls=[],candidate='Exact finite-range GO correction, diagnostic only; diffraction unchanged')
    raw={}
    for rec in receipt['processes']:
        p=root/'work/n3r'/rec['profile']/rec['output'];assert hashlib.sha256(p.read_bytes()).hexdigest()==rec['output_sha256'];raw[rec['profile']]={r['name']:r for r in read(p)['cases']}
        for c in cases:
            row=raw[rec['profile']][c['name']];u=[];go=[];candidate=[]
            for j in range(len(c['receivers'])):
                paths=[p for p in row['paths'] if p['rx']==j]
                a=sum(complex(*p['cir']) for p in paths);g=sum(complex(*p['cir']) for p in paths if 8 not in p['interactions'])
                u.append(a);go.append(g);candidate.append(a+go_correction(c,paths))
            ref=z(refs[c['name']]);u=np.array(u);candidate=np.array(candidate)
            m=metrics(u,ref);cm=metrics(candidate,ref)
            out['comparisons'].append(dict(profile=rec['profile'],name=c['name'],study=c['study'],**m,go_candidate_metrics=cm,entries=[dict(receiver=j,angle_deg=c['study']['angles'][j] if j<len(c['study']['angles']) else None,prediction=pair(a),reference=pair(b),go=pair(g),go_candidate=pair(d)) for j,(a,b,g,d) in enumerate(zip(u,ref,go,candidate))]))
        for axis in ('z','x','y'):
            names=['reciprocity_z'+axis,'reciprocity_z'+axis+'__reverse']
            fields=[sum(complex(*p['cir']) for p in raw[rec['profile']][name]['paths']) for name in names]
            out['controls'].append(dict(profile=rec['profile'],name='reciprocity_z'+axis,relative_error=float(abs(fields[0]-fields[1])/max(abs(fields[0]),abs(fields[1]),1e-20))))
        for test,baseline in [('extent80','zz_s1_h8_p60'),('pec_sigma1e+08','zz_s1_h8_p60'),('pec_sigma1e+16','zz_s1_h8_p60')]:
            rows=[]
            for name in (test,baseline):rows.append(np.array([sum(complex(*p['cir']) for p in raw[rec['profile']][name]['paths'] if p['rx']==j) for j in range(53)]))
            out['controls'].append(dict(profile=rec['profile'],name=test,relative_error=relative(rows[0],rows[1])))
    out['fixture_executions']=len(cases)*len(receipt['processes']);out['unique_channels']=sum(len(c['receivers']) for c in cases)
    out['engine_channels']=out['unique_channels']*len(receipt['processes'])
    (work/'analysis.json').write_text(json.dumps(out,indent=2,allow_nan=False),encoding='utf-8')
    for r in out['comparisons']:
        if r['profile'].endswith('reciprocal') and r['study']['group'] in ('sweep','boundary'):
            print(r['profile'],r['name'],'RMS%',None if r['reference_null'] else round(100*r['total_complex_rms'],4),'GO%',None if r['reference_null'] else round(100*r['go_candidate_metrics']['total_complex_rms'],4),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('root',type=Path);args=ap.parse_args();main(args.root.resolve())

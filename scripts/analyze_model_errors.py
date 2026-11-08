"""Separate numerical reference uncertainty, normalization, and ray-model error."""
import argparse,json
from pathlib import Path
import numpy as np
from line_source_comparison import channel,kernel
from ray_wedge2d import fixture,green
from dielectric_model import coefficient,go_coefficient

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def z(a):
    a=np.asarray(a);return a[...,0]+1j*a[...,1]
def pair(a):return np.stack([np.real(a),np.imag(a)],axis=-1).tolist()
def relative(a,b):return float(np.linalg.norm(a-b)/np.linalg.norm(b))
def metrics(a,b,go=None):
    a,b=np.asarray(a),np.asarray(b)
    # Relative phase/gain metrics become ill-conditioned at field nulls.
    # Report both all samples and the explicit -40 dB reference-amplitude mask.
    mask=abs(b)>abs(b).max()*.01
    ratio=a/b;phase=abs(np.angle(ratio));gain=abs(20*np.log10(abs(ratio)))
    result=dict(samples=a.size,total_complex_rms=relative(a,b),p95_abs_gain_db=float(np.percentile(gain,95)),p95_abs_phase_rad=float(np.percentile(phase,95)),phase_mask_threshold_db=-40,phase_mask_samples=int(mask.sum()),masked_p95_abs_gain_db=float(np.percentile(gain[mask],95)),masked_p95_abs_phase_rad=float(np.percentile(phase[mask],95)),max_absolute_error=float(abs(a-b).max()))
    if go is not None:result['residual_after_ray_go_rms']=float(np.linalg.norm(a-b)/np.linalg.norm(b-go))
    return result

def model(source,receiver,epsilon,pol,policy='incident',mode='symmetric'):
    c=fixture(source,receiver,epsilon,pol);a,_=coefficient(c,'sionna-reciprocal',fresnel_policy=policy)
    si=np.linalg.norm(source);s=np.linalg.norm(receiver);sign=1 if pol=='Ez' else -1
    ud=sign*a*(4*np.pi*np.sqrt(si*s*(si+s)))*kernel(si,s,mode);go=0j
    for face in ('incident','reflection0','reflectionn'):
        r=go_coefficient(c,face)
        if r is not None:go+=sign*r[0]*(4*np.pi*r[1])*green(r[1])
    return go+ud,go,ud

def analyze(root):
    work=root/'work/diffraction-model-errors';out=dict(date='2026-11-07',normalization='symmetric total-distance Hankel closure; legacy retained as sensitivity control',reference_controls=[],sweep=[],policy_holdout=[],distance=[],extra_controls=[])
    old={r['name']:r for r in read(root/'work/dielectric-corrections/maxwell_analysis.json')['results']}
    for f in sorted((work/'bem_controls').glob('control*_48.json')):
        r=read(f);u=z(r['field']);v=z(read(f.with_name(f.name.replace('_48','_24')))['field']);name=r['material']+'_'+r['polarization']
        c=dict(name=name,panels24_to48=relative(v,u),linear_residual=r['linear_residual'],analytic_rms=r.get('analytic_rms_error'))
        if name in old:c['bem48_vs_fdfd_extrapolated']=relative(u,z(old[name]['extrapolated_field']))
        tail=work/'bem_controls'/f'tail_{name}_48.json'
        if tail.exists():c['tail5_to8']=relative(z(read(tail)['field']),u)
        reverse=work/'bem_extra'/f'reverse_{name}.json'
        if reverse.exists():c['reciprocity_rms']=relative(z(read(reverse)['field']).T,u)
        out['reference_controls'].append(c)
    cases={c['name']:c for c in read(root/'work/mer/cases.json')['cases']}
    receipts=read(root/'work/mer/receipt.json');assert receipts['status']=='passed'
    for receipt in receipts['processes']:
        assert receipt['passed'];profile=receipt['profile'];rows=read(root/'work/mer'/profile/receipt['output'])['cases'];groups={}
        for row in rows:
            assert row['status']=='completed';c=cases[row['name']];study=c['study'];name=study['material']+'_'+study['polarization'];i=study['source_index']
            ref=read(work/'bem_sweep'/f'sweep_{name}_36.json');values=z(ref['field'])[i]
            for j,rx in enumerate(c['receivers']):
                u,g,d=channel(c,row,j);legacy=channel(c,row,j,'legacy')[0]
                groups.setdefault(name,[]).append(dict(source=i,receiver=j,angle_deg=study['receiver_angles_deg'][j],prediction=pair(u),legacy=pair(legacy),reference=pair(values[j]),go=pair(g),diffracted=pair(d)))
        for name,entries in groups.items():
            u=z([e['prediction'] for e in entries]);ref=z([e['reference'] for e in entries]);go=z([e['go'] for e in entries]);legacy=z([e['legacy'] for e in entries])
            raw=read(work/'bem_sweep'/f'sweep_{name}_36.json');b24=z(read(work/'bem_sweep'/f'sweep_{name}_24.json')['field']);b16=z(read(work/'bem_sweep'/f'sweep_{name}_16.json')['field'])
            out['sweep'].append(dict(profile=profile,name=name,**metrics(u,ref,go),legacy_total_rms=relative(legacy,ref),normalization_change_rms=relative(u,legacy),reference16_to24=relative(b16,b24),reference24_to36=relative(b24,z(raw['field'])),sources=raw['sources'],receivers=raw['receivers'],entries=entries))
    for f in sorted((work/'bem_sweep').glob('*36.json')):
        r=read(f);ref=z(r['field']);eps=complex(*r['epsilon']);pol=r['polarization']
        for policy in ('incident','mean_cosine','angle_bisector','geometric_cosine'):
            values=np.array([[model(s,d,eps,pol,policy)[0] for d in r['receivers']] for s in r['sources']])
            out['policy_holdout'].append(dict(name=r['material']+'_'+pol,policy=policy,total_complex_rms=relative(values,ref)))
    for f in sorted((work/'bem_distance').glob('*24.json')):
        r=read(f);ref=z(r['field']);values=np.array([[model(s,d,complex(*r['epsilon']),r['polarization'])[0] for d in r['receivers']] for s in r['sources']]);coarse=z(read(f.with_name(f.name.replace('_24','_16')))['field'])
        out['distance'].append(dict(name=r['material']+'_'+r['polarization'],scale=int(r['group'][5:]),**metrics(values,ref),reference16_to24=relative(coarse,ref)))
    for f in sorted((work/'bem_extra').glob('*.json')):
        if f.name.startswith('reverse'):continue
        r=read(f);name=f.stem.split('_',1)[1];ref=z(read(work/'bem_sweep'/f'sweep_{name}_36.json')['field'])
        out['extra_controls'].append(dict(name=f.stem,rms_change=relative(z(r['field']),ref)))
    out['engine_receipt']=receipts
    return out

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('root',type=Path);args=ap.parse_args();result=analyze(args.root)
    target=args.root/'work/diffraction-model-errors/analysis.json';target.write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    for row in result['sweep']:print(row['profile'],row['name'],round(100*row['total_complex_rms'],4),'%')
    for row in result['distance']:print(row['name'],row['scale'],round(100*row['total_complex_rms'],4),'%')

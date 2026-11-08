"""Audit native 3D dielectric channels against independently solved Maxwell fields."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from maxwell3d_pec_reference import free_dyadic

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def z(v):v=np.asarray(v);return v[...,0]+1j*v[...,1]
def pairs(v):return np.stack([np.real(v),np.imag(v)],-1).tolist()
def rel(a,b):return float(np.linalg.norm(a-b)/max(np.linalg.norm(b),1e-30))
def channel(row,n):
    a=np.zeros(n,complex)
    for p in row['paths']:a[p['rx']]+=complex(*p['cir'])
    return a
def metrics(a,b):
    peak=float(abs(b).max());valid=(abs(b)>max(peak*1e-3,1e-9))&(abs(a)>max(peak*1e-5,1e-12))
    phase=np.rad2deg(np.angle(a[valid]*np.conj(b[valid])))
    return dict(complex_rms=rel(a,b) if peak>1e-9 else None,maximum_absolute_error=float(abs(a-b).max()),reference_peak=peak,
                phase_samples=int(valid.sum()),phase_median_abs_deg=float(np.median(abs(phase))) if len(phase) else None,
                phase_p95_abs_deg=float(np.percentile(abs(phase),95)) if len(phase) else None,null=peak<=1e-9)

def main(root):
    folder=root/'work/dielectric3d';cases={c['name']:c for c in read(folder/'cases.json')['cases']};nr=36
    refs={m:read(folder/f'{m}_fem{n}/result.json') for m,n in [('concrete',48),('lower',32)]}
    fields={m:z(v['field']) for m,v in refs.items()};conv=[]
    for material in ('concrete','lower'):
        names=([f'{material}_fem24',f'{material}_fem32',f'{material}_fem48',f'{material}_bem16',f'{material}_bem32r',f'{material}_fem24q8'] if material=='concrete' else ['lower_fem24','lower_fem32','lower_bem16r','lower_bem32r'])
        for name in names:
            p=folder/name/'result.json'
            if not p.exists():continue
            v=read(p);a=z(v['field']);b=fields[material]
            conv.append(dict(name=name,material=material,relative_to_selected=rel(a,b),by_height=[rel(a[h*nr:(h+1)*nr],b[h*nr:(h+1)*nr]) for h in range(3)],sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    rows=[];raw={};reciprocity=[];geometry=[];boundaries=[]
    for foldername,profiles,stage in [('d3r',['sionna-native','differt-native','sionna-reciprocal','differt-reciprocal'],'before'),('d3f',['sionna-reciprocal','differt-reciprocal'],'after')]:
        for profile in profiles:
            engine=profile.split('-')[0];p=root/f'work/{foldername}/{profile}/{engine}_float32.json';data=read(p);raw[stage,profile]={r['name']:r for r in data['cases']}
            all_a=[];all_b=[]
            for row in data['cases']:
                c=cases[row['name']];s=c['study'];a=channel(row,len(c['receivers']))
                if s['group']!='primary':continue
                b=fields[s['material']][s['height_index']*nr:(s['height_index']+1)*nr,'xyz'.index(s['rx_axis']),s['source_index']*3+'xyz'.index(s['tx_axis'])]
                diagnostic=a.copy();shadow=[];distant=[]
                for j,r in enumerate(c['receivers']):
                    paths=[p for p in row['paths'] if p['rx']==j];los=[p for p in paths if not p['interactions']]
                    # Geometrical shadow of the canonical solid quadrant, away
                    # from the 240-degree boundary. Do not infer visibility from
                    # missing zero-polarization paths in either engine.
                    shadow.append(s['source_index']==0 and s['angles'][j]>240.02)
                    distant.append(float(np.linalg.norm(np.array(r)-c['tx']))>=1.)
                    if los:diagnostic[j]+=1.5*free_dyadic(c['tx'],r)['xyz'.index(s['rx_axis']),'xyz'.index(s['tx_axis'])]-sum(complex(*p['cir']) for p in los)
                entry=dict(name=c['name'],stage=stage,profile=profile,study=s,field=pairs(a),reference=pairs(b),exact_los_diagnostic=pairs(diagnostic),shadow_mask=shadow,distance_at_least_wavelength_mask=distant,**metrics(a,b));rows.append(entry);all_a.extend(a);all_b.extend(b)
                # Three-point angular stencil: a large midpoint defect is a boundary spike.
                for angle in (120.,210.,240.):
                    j=s['angles'].index(angle);delta=a[j]-(a[j-1]+a[j+1])/2;refdelta=b[j]-(b[j-1]+b[j+1])/2
                    boundaries.append(dict(stage=stage,profile=profile,name=c['name'],angle=angle,midpoint_defect_absolute=float(abs(delta)),maxwell_midpoint_defect_absolute=float(abs(refdelta)),normalized_defect=float(abs(delta)/abs(b).max()) if abs(b).max()>1e-9 else None))
            print(stage,profile,metrics(np.array(all_a),np.array(all_b)),flush=True)
            for name,row in raw[stage,profile].items():
                if not name.startswith('reciprocity_') or name.endswith('__reverse'):continue
                fw=channel(row,1)[0];rv=channel(raw[stage,profile][name+'__reverse'],1)[0]
                reciprocity.append(dict(stage=stage,profile=profile,name=name,forward=pairs(fw),reverse=pairs(rv),absolute_error=float(abs(fw-rv)),relative_error=float(abs(fw-rv)/max(abs(fw),abs(rv),1e-9))))
    for profile in ('sionna-reciprocal','differt-reciprocal'):
        for name,before in raw['before',profile].items():
            after=raw['after',profile][name]
            def key(p):return (p['rx'],tuple(p['interactions']),tuple(x for q in p['points'] for x in q))
            aa=sorted(key(p) for p in before['paths']);bb=sorted(key(p) for p in after['paths'])
            geometry.append(dict(profile=profile,name=name,matched=aa==bb,before=len(aa),after=len(bb)))
    aggregates=[]
    for stage,profile in raw:
        sub=[r for r in rows if r['stage']==stage and r['profile']==profile]
        for material in ('all','concrete','lower'):
            subset=[r for r in sub if material=='all' or r['study']['material']==material]
            a=np.concatenate([z(r['field']) for r in subset]);b=np.concatenate([z(r['reference']) for r in subset])
            diag=np.concatenate([z(r['exact_los_diagnostic']) for r in subset]);shadow=np.concatenate([r['shadow_mask'] for r in subset]);distant=np.concatenate([r['distance_at_least_wavelength_mask'] for r in subset])
            aggregates.append(dict(stage=stage,profile=profile,material=material,channels=len(a),**metrics(a,b),exact_los_diagnostic=metrics(diag,b),shadow_channels=int(shadow.sum()),shadow=metrics(a[shadow],b[shadow]),distant_channels=int(distant.sum()),distance_at_least_wavelength=metrics(a[distant],b[distant])))
    result=dict(status='analyzed',scope='Full complex point-dipole total channels, solid infinite dielectric quadrant, lambda=1; two source angles, radius 1.5 lambda, receiver radius 2 lambda, heights 0/1/3 lambda. No fitted phase, gain, PEC substitution or 2D spreading conversion.',
                reference_files={m:f'{m}_fem{n}/result.json' for m,n in [('concrete',48),('lower',32)]},convergence=conv,aggregates=aggregates,comparisons=rows,reciprocity=reciprocity,boundaries=boundaries,geometry=geometry,
                limitations=['Native fields use finite 160-lambda faces and local 10-lambda slabs with refraction disabled; the full-wave solid quadrant includes internal waves and coupling between both faces.',
                             'The 3D fields retain all Fourier-z wavenumbers and full vector coupling, but geometry is translationally invariant along a straight infinite edge. Finite-edge endpoints and arbitrary 3D objects are outside this validation.',
                             'Reported total-channel errors are not isolated errors in diffraction coefficients. No exact dielectric GO subtraction has been validated.',
                             'Convergence differences are empirical uncertainty indicators, not certified error bounds. Relative phase is excluded at reference nulls.'])
    (folder/'analysis.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    print('Geometry unchanged',sum(g['matched'] for g in geometry),'/',len(geometry))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('root',type=Path);a=ap.parse_args();main(a.root.resolve())

"""Compare unchanged companion fields with independently refined Maxwell data."""
import json, sys
from pathlib import Path
import numpy as np
from analyze_dielectric3d import read, z, pairs, metrics, rel
from investigate_dielectric3d_polarization import TARGET, save, sha

def reference(row,folder):
    d=read(folder/'result.json');f=z(d['field']);ports=d['ports'];tx='xyz'.index(row['study']['tx_axis']);rx='xyz'.index(row['study']['rx_axis'])
    col=ports['sources'].index(row['tx'])*len(ports['axes'])+ports['axes'].index(tx)
    return np.array([f[ports['receivers'].index(v),rx,col] for v in row['receivers']])

def main(root):
    w=root/'work/d3pol';plan=read(w/'study_plan.json');old=read(root/'work/d3weak/analysis.json');r=plan['row'];mask=np.array(r['shadow_mask']);prod=z(r['field'])
    refs={n:reference(r,root/f'work/d3shadow/holdout_b_fem{n}') for n in (32,48)}
    refs[64]=reference(r,w/'holdout_b_fem64q8')
    for n in (80,96):refs[n]=reference(r,w/f'target_fem{n}q8_lowmem')
    q12=reference(r,w/'target_fem48q12')
    series=[];previous=None
    for n,b in refs.items():
        series.append(dict(resolution=n,label=f'FEM{n}' if n<=64 else f'FEM{n} q<7 / FEM64 tail',field=pairs(b),companion=metrics(prod[mask],b[mask]),
            standard=metrics(z(r['standard'])[mask],b[mask]),
            mesh_change=metrics(previous[mask],b[mask]) if previous is not None else None))
        previous=b
    extrap=[]
    for lo,hi in ((32,64),(48,80),(48,96),(64,96),(80,96)):
        ratio=(hi/lo)**2;v=(ratio*refs[hi]-refs[lo])/(ratio-1)
        extrap.append(dict(coarse=lo,fine=hi,assumed_order=2,field=pairs(v),
            companion=metrics(prod[mask],v[mask]),distance_from_fine=rel(v[mask],refs[hi][mask])))
    phase_floor=max(float(abs(refs[96]).max())*1e-3,1e-9)
    companion_phase_floor=max(float(abs(refs[96]).max())*1e-5,1e-12)
    ports=[dict(angle_deg=angle,strict_shadow=bool(mask[i]),reference_magnitude=float(abs(refs[96][i])),
        relative_complex_error=float(abs(prod[i]-refs[96][i])/abs(refs[96][i])) if abs(refs[96][i])>1e-12 else None,
        magnitude_difference_db=float(20*np.log10(abs(prod[i])/abs(refs[96][i]))) if min(abs(prod[i]),abs(refs[96][i]))>1e-12 else None,
        phase_difference_deg=float(np.rad2deg(np.angle(prod[i]*np.conj(refs[96][i])))) if abs(refs[96][i])>phase_floor and abs(prod[i])>companion_phase_floor else None)
        for i,angle in enumerate(r['study']['angles'])]
    target=dict(name=TARGET,angles=r['study']['angles'],shadow_mask=r['shadow_mask'],field=r['field'],standard=r['standard'],port_metrics=ports,
        selected_reference=pairs(refs[96]),selected_reference_label='FEM96 q<7 / FEM64 tail',series=series,
        tail_audit=read(w/'target_fem96q8_lowmem/result.json'),
        spectral_change=metrics(q12[mask],refs[48][mask]),spectral_reference=pairs(q12),
        extrapolation_diagnostics=extrap,
        extrapolation_scope='Independent FEM-only order-2 estimates; diagnostics, not selected references or certified bounds.')
    rows=[];changes=[];prior_labels={}
    for material,folder in [('concrete','d3shadow/concrete_fem64'),('lower','d3shadow/lower_fem48'),('holdout_a','d3shadow/holdout_a_fem48'),('holdout_b','d3shadow/holdout_b_fem48'),('new_a','d3weak/new_a_fem48'),('new_b','d3weak/new_b_fem48')]:
        cfg=read(root/'work'/folder/'config.json');prior_labels[material]=f'FEM{cfg["resolution"]}/order{cfg["order"]} (prior)'
    for original in old['comparisons']:
        row=dict(original);material=row['material'];b=z(row['reference']);coarse=z(row['coarse_reference']);label=prior_labels[material]
        folder=w/f'{material}_fem64q8'
        if (folder/'result.json').exists():
            coarse=b;b=reference(row,folder);label='FEM64/order8'
        if row['name']==TARGET:
            coarse=refs[80];b=refs[96];label='FEM96 q<7 / FEM64 tail'
        elif row['name']==old['weak']['name']:
            # This was the finer target reference in the preceding report.
            assert np.allclose(b[np.array(row['shadow_mask'])],z(old['weak']['reference']),rtol=1e-9,atol=1e-12)
        p=z(row['field']);standard=z(row['standard']);m=np.array(row['shadow_mask'])
        row.update(reference=pairs(b),coarse_reference=pairs(coarse),reference_label=label,
            previous_reference=original['reference'],previous_shadow=original['shadow_refined'],
            refined_metrics=metrics(p,b),standard_metrics=metrics(standard,b),
            shadow_refined=metrics(p[m],b[m]) if m.any() else None,shadow_standard=metrics(standard[m],b[m]) if m.any() else None,
            reference_shadow_change=metrics(coarse[m],b[m]) if m.any() else None)
        rows.append(row)
    groups=[r for r in rows if r['engine']=='sionna' and r['shadow_refined'] and r['shadow_refined']['complex_rms'] is not None]
    groups.sort(key=lambda r:r['shadow_refined']['complex_rms'],reverse=True)
    aggregates=[]
    for campaign in ('primary','holdout','fresh'):
        rr=[r for r in rows if r['engine']=='sionna' and r['campaign']==campaign]
        for material in ('all',*dict.fromkeys(r['material'] for r in rr)):
            sub=[r for r in rr if material=='all' or r['material']==material];m=np.concatenate([r['shadow_mask'] for r in sub]);p=np.concatenate([z(r['field']) for r in sub]);b=np.concatenate([z(r['reference']) for r in sub]);prior=np.concatenate([z(r['previous_reference']) for r in sub])
            aggregates.append(dict(campaign=campaign,material=material,channels=len(p),shadow_channels=int(m.sum()),
                current=metrics(p[m],b[m]),previous=metrics(p[m],prior[m]),reference_change=rel(prior[m],b[m])))
    boundaries=[]
    for row in rows:
        if row['engine']!='sionna' or row['campaign']=='primary':continue
        boundary=np.rad2deg((np.arctan2(row['tx'][1],row['tx'][0])-np.pi/2)%(2*np.pi))+180
        ix=np.where(abs(np.array(row['study']['angles'])-boundary)<.011)[0];assert len(ix)==3
        b=z(row['reference'])[ix];p=z(row['field'])[ix];scale=max(np.linalg.norm(b)/np.sqrt(3),1e-12)
        boundaries.append(dict(name=row['name'],reference_label=row['reference_label'],field_rms=rel(p,b),
            span_error=float(abs((p[-1]-p[0])-(b[-1]-b[0]))/scale),finite=bool(np.isfinite(p).all() and np.isfinite(b).all()),reference_rms=float(scale)))
    # Reference refinement is evaluated without using BIE values to estimate its limit.
    increments=[rel(refs[a][mask],refs[b][mask]) for a,b in ((32,48),(48,64),(64,80),(80,96))]
    mode_controls=read(w/'probe_analysis.json');analytic=read(w/'analytic_controls.json')
    checks=[dict(name='production sources unchanged',passed=all(sha(Path(__file__).with_name(k))==v for k,v in plan['source_hashes'].items())),
       dict(name='target reference mesh increments contract',passed=all(a>b for a,b in zip(increments,increments[1:]))),
       dict(name='target agreement improves with independent reference refinement',passed=series[-1]['companion']['complex_rms']<series[1]['companion']['complex_rms']),
       dict(name='spectral control below 0.1 percent',passed=target['spectral_change']['complex_rms']<.001),
       dict(name='modal controls passed',passed=mode_controls['status']=='passed'),
       dict(name='analytic Maxwell controls passed',passed=analytic['status']=='passed'),
       dict(name='reference sparse solver equivalent to standard factorization',passed=read(w/'linear_solver_validation.json')['status']=='passed'),
       dict(name='all shadow-boundary stencils finite',passed=all(v['finite'] for v in boundaries))]
    result=dict(status='passed' if all(c['passed'] for c in checks) else 'failed',target=target,comparisons=rows,
       summary=aggregates,worst_group=dict(name=groups[0]['name'],metrics=groups[0]['shadow_refined'],reference_label=groups[0]['reference_label']),
       boundaries=dict(stencils=len(boundaries),rows=boundaries,maximum_span_error=max(v['span_error'] for v in boundaries if v['reference_rms']>1e-9),
          maximum_field_rms=max(v['field_rms'] for v in boundaries if v['reference_rms']>1e-9)),
       reciprocity=old['reciprocity'],checks=checks,production_changed=False,
       scope='Reference refinement of the existing optional shared infinite-dielectric-wedge companion. No native ray-tracer or production-field change.')
    save(w/'analysis.json',result)
    print(json.dumps(dict(status=result['status'],target=[dict(resolution=v['resolution'],rms=v['companion']['complex_rms'],mesh_change=v['mesh_change']) for v in series],worst=result['worst_group'])),flush=True)
    assert result['status']=='passed'

if __name__=='__main__':main(Path(sys.argv[1]).resolve())

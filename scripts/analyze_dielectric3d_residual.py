"""Attribute remaining error with independent refinement in both solvers."""
import sys
from pathlib import Path
import numpy as np
from analyze_dielectric3d import read,z,pairs,metrics,rel
from investigate_dielectric3d_polarization import save,sha

def field_for(row,result,kind='field'):
    cfg=result.get('config',result);ports=cfg['ports'];field=z(result[kind]);tx='xyz'.index(row['study']['tx_axis']);rx='xyz'.index(row['study']['rx_axis'])
    col=ports['sources'].index(row['tx'])*len(ports['axes'])+ports['axes'].index(tx)
    return np.array([field[ports['receivers'].index(r),rx,col] for r in row['receivers']])

def main(root):
    w=root/'work/d3res';old=read(root/'work/d3pol/analysis.json');name=old['target']['name'];r=next(r for r in old['comparisons'] if r['name']==name and r['engine']=='sionna');mask=np.array(r['shadow_mask']);p=z(r['field'])
    plan=read(w/'plan.json');resource=read(w/'resource_validation.json');sampling=read(w/'sampling_assessment.json')
    assert resource['status']==sampling['status']==read(w/'resource_selection.json')['status']==read(w/'offgrid_validation.json')['status']=='passed'
    refs={v['resolution']:z(v['field']) for v in old['target']['series']};fine={n:read(w/f'fem{n}_bounded/result.json') for n in (112,128)}
    for n,b in fine.items():assert b['status']=='completed';refs[n]=field_for(r,b)
    from synthesize_dielectric3d_residual_heights import derive
    expanded={n:derive(root,n) for n in fine}
    bie=read(w/'bie64_full/result.json');assert bie['status']=='completed';b64=field_for(r,bie);candidate=2*b64-z(r['standard'])
    series=[];previous=None
    for n,b in refs.items():
        series.append(dict(resolution=n,label=f'FEM{n}' if n<=64 else f'FEM{n} q<7 / FEM64 tail',field=pairs(b),
            companion=metrics(p[mask],b[mask]),candidate=metrics(candidate[mask],b[mask]),bie64=metrics(b64[mask],b[mask]),
            mesh_change=metrics(previous[mask],b[mask]) if previous is not None else None));previous=b
    recoveries=[]
    for n,b in fine.items():
        cube=field_for(r,b,'cubic');recoveries.append(dict(resolution=n,field=pairs(cube),sampling_change=metrics(cube[mask],refs[n][mask]),
            companion=metrics(p[mask],cube[mask]),candidate=metrics(candidate[mask],cube[mask])))
    extras=[]
    for lo,hi in ((64,128),(80,128),(96,112),(96,128),(112,128)):
        ratio=(hi/lo)**2;b=(ratio*refs[hi]-refs[lo])/(ratio-1)
        extras.append(dict(coarse=lo,fine=hi,assumed_order=2,field=pairs(b),distance_from_fine=rel(b[mask],refs[hi][mask]),
            companion=metrics(p[mask],b[mask]),candidate=metrics(candidate[mask],b[mask])))
    rows=[]
    for original in old['comparisons']:
        row=dict(original);b=z(row['reference']);coarse=z(row.get('coarse_reference',row['reference']));label=row['reference_label'];trial=None;reference_updated=False
        if row['material']=='holdout_b':
            trial=2*field_for(row,bie)-z(row['standard'])
            cfg=expanded[128]['config']['ports']
            if row['tx'] in cfg['sources'] and 'xyz'.index(row['study']['tx_axis']) in cfg['axes'] and all(x in cfg['receivers'] for x in row['receivers']):
                b=field_for(row,expanded[128]);coarse=field_for(row,expanded[112]);label='FEM128 q<7 / FEM64 tail';reference_updated=True
        m=np.array(row['shadow_mask']);v=z(row['field'])
        row.update(previous_reference=row['reference'],previous_shadow=row['shadow_refined'],reference=pairs(b),coarse_reference=pairs(coarse),reference_label=label,
            shadow_refined=metrics(v[m],b[m]) if m.any() else None,refined_metrics=metrics(v,b),
            reference_updated_this_study=reference_updated,
            reference_shadow_change=(metrics(coarse[m],b[m]) if m.any() else None) if reference_updated else original.get('reference_shadow_change'),
            candidate=pairs(trial) if trial is not None else None,candidate_shadow=metrics(trial[m],b[m]) if trial is not None and m.any() else None)
        rows.append(row)
    groups=[r for r in rows if r['engine']=='sionna' and r['shadow_refined'] and r['shadow_refined']['complex_rms'] is not None];groups.sort(key=lambda r:r['shadow_refined']['complex_rms'],reverse=True)
    trials=[r for r in groups if r['candidate_shadow'] and r['candidate_shadow']['complex_rms'] is not None]
    boundaries=[]
    for row in rows:
        if row['engine']!='sionna' or row['campaign']=='primary':continue
        boundary=np.rad2deg((np.arctan2(row['tx'][1],row['tx'][0])-np.pi/2)%(2*np.pi))+180;ix=np.where(abs(np.array(row['study']['angles'])-boundary)<.011)[0];assert len(ix)==3
        b=z(row['reference'])[ix];v=z(row['field'])[ix];scale=max(np.linalg.norm(b)/np.sqrt(3),1e-12)
        trial=z(row['candidate'])[ix] if row['candidate'] is not None else None
        boundaries.append(dict(name=row['name'],reference_label=row['reference_label'],field_rms=rel(v,b),span_error=float(abs((v[-1]-v[0])-(b[-1]-b[0]))/scale),reference_rms=float(scale),
            candidate_field_rms=rel(trial,b) if trial is not None else None,candidate_span_error=float(abs((trial[-1]-trial[0])-(b[-1]-b[0]))/scale) if trial is not None else None,
            finite=bool(np.isfinite(b).all() and np.isfinite(v).all() and (trial is None or np.isfinite(trial).all()))))
    controls=[]
    d=read(root/'work/d3pol/diagnostics.json');ri=[bie['ports']['receivers'].index(v) for v in d['receivers']];col=bie['ports']['sources'].index(d['source'])*3+2
    for i in (5,10,20,26):
        a=np.load(w/'bie64_full'/f'mode_{i:03d}.npz')['field'][ri,:,col,None];b=np.load(root/'work/d3pol/bie64'/f'mode_{i:03d}.npz')['field'];err=rel(a,b);assert err<1e-9;controls.append(dict(index=i,error=err))
    from dielectric3d_synthesis import quadrature
    nodes,weights=quadrature(8);dz=np.asarray(d['receivers'])[:,2]-d['source'][2];modal=[];terms=[]
    for i,q in enumerate(nodes):
        item=next(v for v in d['modes'] if v['index']==i);current=z(item['fields']['converged']);standard=z(item['fields']['bie32'])
        f128=np.load(w/'fem128_bounded'/f'mode_{i:03d}.npz')['field'][:,0,0];f112=np.load(w/'fem112_bounded'/f'mode_{i:03d}.npz')['field'][:,0,0]
        bb=np.load(w/'bie64_full'/f'mode_{i:03d}.npz')['field'][ri,0,col];trial=2*bb-standard;factor=1.5*weights[i]/np.pi*1j*np.sin(q*dz)
        v=dict(current=factor*(current-f128),candidate=factor*(trial-f128),reference=factor*(f112-f128));terms.append(v)
        modal.append(dict(index=i,q=pairs(q),norms={k:float(np.linalg.norm(value[mask])) for k,value in v.items()}))
    assert np.allclose(sum(v['current'] for v in terms),p-refs[128],rtol=1e-8,atol=1e-12)
    assert np.allclose(sum(v['candidate'] for v in terms),candidate-refs[128],rtol=1e-8,atol=1e-12)
    tails=[]
    for i in (32,40):
        v=np.load(w/'fem128tail'/f'mode_{i:03d}.npz')['field'][:,0,0];base=np.load(w/'fem128_bounded'/f'mode_{i:03d}.npz')['field'][:,0,0]
        factor=1.5*weights[i]/np.pi*1j*np.sin(nodes[i]*dz)
        tails.append(dict(index=i,q=pairs(nodes[i]),relative_modal_change=rel(v[mask],base[mask]),weighted_change_relative_to_target=float(np.linalg.norm((factor*(v-base))[mask])/np.linalg.norm(refs[128][mask]))))
    intervals=[]
    extended_tails=[];xy=[v[:2] for v in d['receivers']]
    for row in rows:
        if row['engine']!='sionna' or not row['reference_updated_this_study']:continue
        indices=[xy.index(v[:2]) for v in row['receivers']];axis='xyz'.index(row['study']['rx_axis']);m=np.array(row['shadow_mask']);rr=z(row['reference'])
        for i in (32,40):
            v=np.load(w/'fem128tail'/f'mode_{i:03d}.npz')['field'][indices,axis,0];base=np.load(w/'fem128_bounded'/f'mode_{i:03d}.npz')['field'][indices,axis,0]
            dz2=np.asarray(row['receivers'])[:,2]-row['tx'][2];factor=1.5*weights[i]/np.pi*(np.cos(nodes[i]*dz2) if axis==2 else 1j*np.sin(nodes[i]*dz2))
            error=float(np.linalg.norm((factor*(v-base))[m])/np.linalg.norm(rr[m]))
            extended_tails.append(dict(name=row['name'],index=i,weighted_change_relative_to_target=error))
    for j,(left,right) in enumerate(zip([0,2,4,5.5,7,9,12,16],[2,4,5.5,7,9,12,16,24])):
        intervals.append(dict(q_range=[left,right],norms={key:float(np.linalg.norm(sum(v[key] for v in terms[j*8:(j+1)*8])[mask])) for key in ('current','candidate','reference')}))
    increments=[rel(refs[lo][mask],refs[hi][mask]) for lo,hi in ((80,96),(96,112),(112,128))]
    checks=[dict(name='original kernel sources preserved',passed=all(sha(Path(__file__).with_name(n))==digest for n,digest in plan['sources'].items())),
        dict(name='final mesh increments contract',passed=all(a>b for a,b in zip(increments,increments[1:]))),
        dict(name='independent primary analytic controls pass',passed=sampling['status']=='passed'),
        dict(name='Fourier height reuse matches every old mode and full synthesis',passed=read(w/'height_synthesis_validation.json')['status']=='passed'),
        dict(name='tail probes pass at every refined height and receive polarization',passed=max(v['weighted_change_relative_to_target'] for v in extended_tails)<1e-5),
        dict(name='FEM128 tail controls below 0.001 percent of target norm',passed=max(v['weighted_change_relative_to_target'] for v in tails)<1e-5),
        dict(name='all retained boundary samples finite',passed=all(v['finite'] for v in boundaries)),
        dict(name='same BIE64 modal fields reproduced in full-vector sweep',passed=max(v['error'] for v in controls)<1e-9)]
    result=dict(status='passed' if all(v['passed'] for v in checks) else 'failed',production_changed=False,checks=checks,
        target=dict(name=name,series=series,angles=r['study']['angles'],shadow_mask=r['shadow_mask'],field=r['field'],candidate=pairs(candidate),bie64=pairs(b64),
            selected_reference=pairs(refs[128]),selected_reference_label='FEM128 q<7 / FEM64 tail; original recovery',sampling_diagnostics=recoveries,
            extrapolation_diagnostics=extras,sampling_accepted=False,selection='Original recovery retained; cubic evaluated independently against analytic controls and reported separately.'),
        comparisons=rows,worst_group=dict(name=groups[0]['name'],metrics=groups[0]['shadow_refined'],reference_label=groups[0]['reference_label']),
        candidate_summary=dict(groups=len(trials),improved=sum(v['candidate_shadow']['complex_rms']<v['shadow_refined']['complex_rms'] for v in trials),
            scope='Research-only fixed 2*BIE64-BIE32, one material, all old holdout-b ports. No fitted coefficient or native export change. Default remains 16/32.'),
        boundaries=dict(stencils=len(boundaries),rows=boundaries,maximum_span_error=max(v['span_error'] for v in boundaries if v['reference_rms']>1e-9),maximum_field_rms=max(v['field_rms'] for v in boundaries if v['reference_rms']>1e-9),
            candidate_stencils=sum(v['candidate_field_rms'] is not None for v in boundaries),candidate_maximum_span_error=max(v['candidate_span_error'] for v in boundaries if v['reference_rms']>1e-9 and v['candidate_span_error'] is not None),
            candidate_maximum_field_rms=max(v['candidate_field_rms'] for v in boundaries if v['reference_rms']>1e-9 and v['candidate_field_rms'] is not None)),
        modal_controls=controls,tail_controls=tails,extended_tail_controls=extended_tails,height_reconstruction=read(w/'height_synthesis_validation.json'),modal_diagnosis=dict(rows=modal,intervals=intervals,scope='Weighted coherent residual contributions; interval norms do not add because fields interfere.'),
        reciprocity=old['reciprocity'],scope='Canonical infinite solid dielectric quadrant, shared full-wave companion, single frequency. Independent reference refinement, not a general native UTD correction.')
    save(w/'analysis.json',result);print(result['status'],'target',series[-1]['companion'],'candidate',series[-1]['candidate'],'worst',result['worst_group'],flush=True);assert result['status']=='passed'

if __name__=='__main__':main(Path(sys.argv[1]).resolve())

"""Audit the frozen spatial extrapolation against old and unseen FEM fields."""
import hashlib,json,sys
from pathlib import Path
import numpy as np
from analyze_dielectric3d import read,z,pairs,metrics,rel,channel
from dielectric3d_refinement import refine

def main(root):
    w=root/'work/d3weak';prior=read(root/'work/d3shadow/analysis.json');rows=[];reference_checks=list(prior['reference_checks'])
    products={m:read(w/f'{m}_converged.json') for m in ('concrete','lower','holdout_a','holdout_b','new_a','new_b','reciprocity')}
    for p in products.values():
        assert p['status']=='completed' and not p['reference_used'] and p['extrapolation']==dict(order=1,weights=[-1.,2.],fitted=False)
        for name,digest in p['source_hashes'].items():assert hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()==digest
    predicted={m:{r['name']:z(r['field']) for r in p['results']} for m,p in products.items()}
    def add(row,prediction,standard):
        b=z(row['reference']);mask=np.array(row['shadow_mask']);row=dict(row,field=pairs(prediction),standard=pairs(standard),standard_metrics=metrics(standard,b),refined_metrics=metrics(prediction,b),shadow_standard=metrics(standard[mask],b[mask]) if mask.any() else None,shadow_refined=metrics(prediction[mask],b[mask]) if mask.any() else None)
        rows.append(row)
    for r in prior['comparisons']:add(r,predicted[r['material']][r['name']],z(r['field']))
    raw={e:{r['name']:r for r in read(root/f'work/d3wr/{e}-reciprocal/{e}_float32.json')['cases']} for e in ('sionna','differt')}
    for material in ('new_a','new_b'):
        cases=read(w/f'{material}_cases.json')['cases'];fr=read(w/f'{material}_fem48/result.json');cr=read(w/f'{material}_fem32/result.json');ff,cf=z(fr['field']),z(cr['field'])
        standard=refine(cases,w/f'{material}_converged_modes/fine32',panels=32);(w/f'{material}_standard.json').write_text(json.dumps(standard,indent=2),encoding='utf-8');standard={r['name']:z(r['field']) for r in standard['results']}
        fine=[];coarse=[];ms=[]
        for c in cases:
            st=c['study'];tx='xyz'.index(st['tx_axis']);rx='xyz'.index(st['rx_axis']);si=fr['ports']['sources'].index(c['tx']);ci=cr['ports']['sources'].index(c['tx'])
            b=np.array([ff[fr['ports']['receivers'].index(v),rx,si*3+tx] for v in c['receivers']]);bc=np.array([cf[cr['ports']['receivers'].index(v),rx,ci*3+tx] for v in c['receivers']])
            boundary=np.rad2deg((np.arctan2(c['tx'][1],c['tx'][0])-np.pi/2)%(2*np.pi))+180.02;mask=np.array(st['angles'])>boundary;fine.extend(b);coarse.extend(bc);ms.extend(mask)
            for e in raw:
                ray=channel(raw[e][c['name']],len(c['receivers']));r=dict(campaign='fresh',material=material,engine=e,name=c['name'],study=st,tx=c['tx'],receivers=c['receivers'],shadow_mask=mask.tolist(),ray=pairs(ray),reference=pairs(b),coarse_reference=pairs(bc),ray_metrics=metrics(ray,b),shadow_ray=metrics(ray[mask],b[mask]),reference_shadow_change=metrics(bc[mask],b[mask]))
                add(r,predicted[material][c['name']],standard[c['name']])
        fine,coarse,ms=np.array(fine),np.array(coarse),np.array(ms)
        reference_checks.append(dict(campaign='fresh',material=material,full_change=rel(coarse,fine),shadow_change=rel(coarse[ms],fine[ms]),fine_sha256=hashlib.sha256((w/f'{material}_fem48/result.json').read_bytes()).hexdigest()))
    summary=[];gates=[]
    for campaign in ('primary','holdout','fresh'):
        for e in ('sionna','differt'):
            for m in ['all',*dict.fromkeys(r['material'] for r in rows if r['campaign']==campaign)]:
                rr=[r for r in rows if r['campaign']==campaign and r['engine']==e and (m=='all' or r['material']==m)];mask=np.concatenate([r['shadow_mask'] for r in rr]);b=np.concatenate([z(r['reference']) for r in rr]);p=np.concatenate([z(r['field']) for r in rr]);old=np.concatenate([z(r['standard']) for r in rr]);ray=np.concatenate([z(r['ray']) for r in rr])
                s=dict(campaign=campaign,engine=e,material=m,channels=len(b),shadow_channels=int(mask.sum()),ray=metrics(ray,b),standard=metrics(old,b),refined=metrics(p,b),shadow_ray=metrics(ray[mask],b[mask]),shadow_standard=metrics(old[mask],b[mask]),shadow_refined=metrics(p[mask],b[mask]));summary.append(s)
                gates.append(dict(kind='material_and_aggregate',campaign=campaign,engine=e,material=m,passed=s['shadow_refined']['complex_rms']<.05 and (campaign=='fresh' or s['shadow_refined']['complex_rms']<=s['shadow_standard']['complex_rms']+.002)))
    r=next(r for r in rows if r['engine']=='sionna' and r['name']=='holdout_b_s1_yz_h0.7');mask=np.array(r['shadow_mask']);b64=z(read(w/'weak_fem64q8/result.json')['field'])[:,2,0];b12=z(read(w/'weak_fem48q12/result.json')['field'])[:,2,0];b48=z(r['reference'])[mask];p=z(r['field'])[mask];old=z(r['standard'])[mask]
    weak=dict(name=r['name'],angles=np.array(r['study']['angles'])[mask].tolist(),reference=pairs(b64),field=pairs(p),standard=pairs(old),baseline_vs_fem64=metrics(old,b64),corrected_vs_fem64=metrics(p,b64),corrected_vs_fem48=metrics(p,b48),reference_spatial_change=rel(b48,b64),reference_spectral_change=rel(b12,b48),scope='FEM64/order8 is the selected weak-port reference. FEM48/order12 versus FEM48/order8 isolates spectral quadrature; FEM48/order8 versus FEM64/order8 isolates mesh refinement.')
    gates.append(dict(kind='target',passed=weak['corrected_vs_fem64']['complex_rms']<.05 and weak['corrected_vs_fem64']['complex_rms']<weak['baseline_vs_fem64']['complex_rms']/3))
    # Separate reversed-source solves, without a completed-channel projection.
    rc=read(root/'work/d3shadow/reciprocity_cases.json')['cases'];f=np.zeros((3,3),complex);rev=f.copy()
    for c in rc:
        st=c['study'];a=rev if 'reverse_of' in st else f;a['xyz'.index(st['rx_axis']),'xyz'.index(st['tx_axis'])]=predicted['reciprocity'][c['name']][0]
    reciprocity=dict(relative_error=rel(f,rev.T),forward=pairs(f),reverse=pairs(rev),averaged=False);gates.append(dict(kind='reciprocity',passed=reciprocity['relative_error']<.01))
    boundaries=[]
    for r in rows:
        if r['engine']!='sionna' or r['campaign']=='primary':continue
        boundary=np.rad2deg((np.arctan2(r['tx'][1],r['tx'][0])-np.pi/2)%(2*np.pi))+180;angles=np.array(r['study']['angles']);ix=np.where(abs(angles-boundary)<.011)[0];assert len(ix)==3
        b=z(r['reference'])[ix];a=z(r['field'])[ix];old=z(r['standard'])[ix];scale=max(np.linalg.norm(b)/np.sqrt(3),1e-12)
        boundaries.append(dict(name=r['name'],campaign=r['campaign'],reference_rms=float(scale),field_rms=rel(a,b),standard_rms=rel(old,b),span_error=float(abs((a[-1]-a[0])-(b[-1]-b[0]))/scale),finite=bool(np.isfinite(a).all())))
    active=[v for v in boundaries if v['reference_rms']>1e-9];boundary_summary=dict(stencils=len(boundaries),maximum_field_rms=max(v['field_rms'] for v in active),maximum_span_error=max(v['span_error'] for v in active),rows=boundaries)
    gates.append(dict(kind='boundaries',passed=all(v['finite'] for v in boundaries) and boundary_summary['maximum_span_error']<.001))
    passed=all(g['passed'] for g in gates);result=dict(status='passed' if passed else 'failed',comparisons=rows,summary=summary,weak=weak,reciprocity=reciprocity,boundaries=boundary_summary,reference_checks=reference_checks,gates=gates,scope='Fixed 2*BIE32-BIE16 optional shared field. Native UTD and installed runtime/extension files unchanged; no Maxwell reference lookup in production.')
    (w/'analysis.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(dict(status=result['status'],weak=weak,reciprocity=reciprocity['relative_error'],boundaries={k:v for k,v in boundary_summary.items() if k!='rows'},summary=[s for s in summary if s['engine']=='sionna' and s['material']=='all'])),flush=True)
    if not passed:raise SystemExit('Declared acceptance gate failed; do not promote')

if __name__=='__main__':main(Path(sys.argv[1]).resolve())

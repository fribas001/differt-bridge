"""Assess the frozen optional BIE solver against independent FEM and fresh holdouts."""
import json,hashlib,sys
from pathlib import Path
import numpy as np
from analyze_dielectric3d import read,z,pairs,metrics,channel,rel

def safe_metrics(a,b):return metrics(a,b) if len(b) else None
def main(root):
    work=root/'work/d3shadow';rows=[];reference_checks=[];sourcefiles={};summary=[]
    for campaign,materials,rayfolder in [('primary',['concrete','lower'],'d3f'),('holdout',['holdout_a','holdout_b'],'d3sh')]:
        cases=read(work/(campaign+'_cases.json'))['cases'];raw={engine:{r['name']:r for r in read(root/f'work/{rayfolder}/{engine}-reciprocal/{engine}_float32.json')['cases']} for engine in ('sionna','differt')}
        for material in materials:
            if material=='concrete':fine=work/'concrete_fem64/result.json';coarse=root/'work/dielectric3d/concrete_fem48/result.json'
            elif material=='lower':fine=work/'lower_fem48/result.json';coarse=root/'work/dielectric3d/lower_fem32/result.json'
            else:fine=work/f'{material}_fem48/result.json';coarse=work/f'{material}_fem32/result.json'
            fr,cr=read(fine),read(coarse);ff,cf=z(fr['field']),z(cr['field']);product=read(work/(material+'_standard_product.json'))
            assert product['status']=='completed' and not product['reference_used'] and not product['native_exports_modified']
            for name,digest in product['source_hashes'].items():assert hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest()==digest
            predicted={r['name']:z(r['field']) for r in product['results']};allfine=[];allcoarse=[];shadowfine=[];shadowcoarse=[]
            for c in (c for c in cases if c['study']['material']==material):
                st=c['study'];si=fr['ports']['sources'].index(c['tx']);cis=cr['ports']['sources'].index(c['tx']);tx='xyz'.index(st['tx_axis']);rx='xyz'.index(st['rx_axis'])
                b=np.array([ff[fr['ports']['receivers'].index(r),rx,si*3+tx] for r in c['receivers']]);bc=np.array([cf[cr['ports']['receivers'].index(r),rx,cis*3+tx] for r in c['receivers']])
                sourcephi=np.rad2deg((np.arctan2(c['tx'][1],c['tx'][0])-np.pi/2)%(2*np.pi));mask=np.array(st['angles'])>sourcephi+180.02
                pred=predicted[c['name']];allfine.extend(b);allcoarse.extend(bc);shadowfine.extend(b[mask]);shadowcoarse.extend(bc[mask])
                for engine in raw:
                    ray=channel(raw[engine][c['name']],len(c['receivers']));rows.append(dict(campaign=campaign,material=material,engine=engine,name=c['name'],study=st,tx=c['tx'],receivers=c['receivers'],shadow_mask=mask.tolist(),ray=pairs(ray),field=pairs(pred),reference=pairs(b),coarse_reference=pairs(bc),ray_metrics=metrics(ray,b),refined_metrics=metrics(pred,b),shadow_ray=safe_metrics(ray[mask],b[mask]),shadow_refined=safe_metrics(pred[mask],b[mask]),reference_shadow_change=safe_metrics(bc[mask],b[mask])))
            reference_checks.append(dict(campaign=campaign,material=material,fine=str(fine.relative_to(root)),coarse=str(coarse.relative_to(root)),full_change=rel(np.array(allcoarse),np.array(allfine)),shadow_change=rel(np.array(shadowcoarse),np.array(shadowfine)),fine_sha256=hashlib.sha256(fine.read_bytes()).hexdigest()))
    for campaign in ('primary','holdout'):
        for engine in ('sionna','differt'):
            for material in ['all',*dict.fromkeys(r['material'] for r in rows if r['campaign']==campaign)]:
                rr=[r for r in rows if r['campaign']==campaign and r['engine']==engine and (material=='all' or r['material']==material)]
                a=np.concatenate([z(r['ray']) for r in rr]);p=np.concatenate([z(r['field']) for r in rr]);b=np.concatenate([z(r['reference']) for r in rr]);mask=np.concatenate([r['shadow_mask'] for r in rr])
                summary.append(dict(campaign=campaign,engine=engine,material=material,channels=len(a),shadow_channels=int(mask.sum()),ray=metrics(a,b),refined=metrics(p,b),shadow_ray=metrics(a[mask],b[mask]),shadow_refined=metrics(p[mask],b[mask])))
    gates=[dict(campaign=r['campaign'],engine=r['engine'],material=r['material'],shadow_below_five_percent=r['shadow_refined']['complex_rms']<.05,shadow_at_least_threefold_improvement=r['shadow_refined']['complex_rms']<r['shadow_ray']['complex_rms']/3) for r in summary]
    passed=all(g['shadow_below_five_percent'] and g['shadow_at_least_threefold_improvement'] for g in gates)
    result=dict(status='passed' if passed else 'failed',scope='Shared optional coupled solid-wedge BIE field versus independent FEM. Native UTD coefficients and exports unchanged. No fitting or reference-file lookup in the production solver.',comparisons=rows,summary=summary,reference_checks=reference_checks,gates=gates,primary_reference_revised=True,old_shadow_rms=.33083037334451615)
    (work/'analysis.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(dict(status=result['status'],summary=[r for r in summary if r['material']=='all'],reference_checks=reference_checks)),flush=True)
    if not passed:raise SystemExit('Full-wave correction failed its declared validation gates')

if __name__=='__main__':main(Path(sys.argv[1]).resolve())

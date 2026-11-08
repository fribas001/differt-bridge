"""Compare the retained 32/48-panel concrete product runs against FEM64."""
import json,sys
from pathlib import Path
import numpy as np
from analyze_dielectric3d import read,z,rel

def main(root):
    work=root/'work/d3shadow';cases=read(work/'concrete_cases.json')['cases'];ref=read(work/'concrete_fem64/result.json');ff=z(ref['field'])
    standard={r['name']:z(r['field']) for r in read(work/'concrete_standard_product.json')['results']}
    fine={r['name']:z(r['field']) for r in read(work/'concrete_product.json')['results']};p=[];q=[];b=[];masks=[]
    for c in cases:
        st=c['study'];si=ref['ports']['sources'].index(c['tx']);tx='xyz'.index(st['tx_axis']);rx='xyz'.index(st['rx_axis'])
        values=[ff[ref['ports']['receivers'].index(v),rx,si*3+tx] for v in c['receivers']]
        boundary=np.rad2deg((np.arctan2(c['tx'][1],c['tx'][0])-np.pi/2)%(2*np.pi))+180.02
        p.extend(standard[c['name']]);q.extend(fine[c['name']]);b.extend(values);masks.extend(np.array(st['angles'])>boundary)
    p,q,b,mask=np.array(p),np.array(q),np.array(b),np.array(masks)
    result=dict(status='completed',material='concrete',standard_panels=32,fine_panels=48,reference_resolution=64,
        total_standard_rms=rel(p,b),total_fine_rms=rel(q,b),total_resolution_change=rel(p,q),
        shadow_standard_rms=rel(p[mask],b[mask]),shadow_fine_rms=rel(q[mask],b[mask]),shadow_resolution_change=rel(p[mask],q[mask]),
        scope='Unfitted resolution control on the primary concrete population. Both product fields use order 8; agreement is empirical, not a certified error bound or a holdout-resolution study.')
    (work/'resolution_validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))

if __name__=='__main__':main(Path(sys.argv[1]).resolve())

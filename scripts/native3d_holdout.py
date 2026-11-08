"""Unfitted angular, range, height and boundary holdout for Hertz-UTD."""
import json
from pathlib import Path
import numpy as np
from native3d_cases import case,point
from hertz_pec3d import refine,vector
from analyze_native3d import exact,metrics
from analyze_model_errors import pair,z

def main(root):
    w=root/'work/native3d';cases=[]
    for phi,scale,height in ((117.,.7,-3.),(153.,1.7,5.),(238.,2.3,-4.)):
        for axis in ('z','x','y'):
            c=case(f'hold_p{phi:g}_{axis}',phi,scale,height,axis,angles=np.arange(7.,266.,7.))
            c['tx']=point(phi,2.2*scale,-.3*scale)
            c['receivers']=[point(a,4.7*scale,(height-.3)*scale) for a in c['study']['angles']]
            c['study']['group']='holdout';cases.append(c)
    # A fresh exact transition with much narrower two-sided offsets.
    for axis in ('z','x','y'):
        c=case('hold_boundary_'+axis,47.,1.3,-4.,axis,angles=[227+d for d in (-.02,-.00001,-.000001,0.,.000001,.00001,.02)])
        c['study']['group']='holdout_boundary';cases.append(c)
    manifest=w/'holdout_cases.json';manifest.write_text(json.dumps(dict(cases=cases),indent=2),encoding='utf-8')
    product=refine(cases);(w/'holdout_refined.json').write_text(json.dumps(product,indent=2),encoding='utf-8')
    rows=[]
    for c,row in zip(cases,product['results']):
        ref=np.array([exact(c,j) for j in range(len(c['receivers']))]);axis={'x':0,'y':1,'z':2}[c['study']['receiver_axis']]
        coarse=np.array([1.5*vector(c['tx'],r,h=5e-4)[axis] for r in c['receivers']]);fine=z(row['field'])
        rows.append(dict(name=c['name'],study=c['study'],**metrics(fine,ref),step_refinement=float(np.linalg.norm(coarse-fine)/np.linalg.norm(ref)),field=row['field'],reference=pair(ref)))
        print(c['name'],100*rows[-1]['total_complex_rms'],flush=True)
    (w/'holdout_validation.json').write_text(json.dumps(dict(status='measured',results=rows),indent=2),encoding='utf-8')

if __name__=='__main__':
    import sys
    main(Path(sys.argv[1]).resolve())

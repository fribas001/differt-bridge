"""Diagnostic evaluation of uniform Hertz-UTD; no engine installation."""
import json
from pathlib import Path
import numpy as np
from scipy.special import erfcx
from analyze_model_errors import read,pair,z
from analyze_native3d import metrics

from hertz_pec3d import potential,vector

def main(root):
    work=root/'work/native3d';cases=read(root/'work/n3r/cases.json')['cases'];refs=read(work/'reference_fields.json')['fields'];rows=[]
    for c in cases:
        if c['study']['group'] not in ('sweep','boundary'):continue
        axis={'x':0,'y':1,'z':2}[c['study']['receiver_axis']]
        if axis!=2 and c['study']['height']==0:continue
        values=np.array([1.5*vector(c['tx'],r)[axis] for r in c['receivers']]);fine=np.array([1.5*vector(c['tx'],r,h=2.5e-4)[axis] for r in c['receivers']])
        ref=z(refs[c['name']]);m=metrics(fine,ref)
        rows.append(dict(name=c['name'],**m,step_refinement=float(np.linalg.norm(fine-values)/np.linalg.norm(ref)),field=pair(fine)))
        print(c['name'],100*m['total_complex_rms'],rows[-1]['step_refinement'],flush=True)
    (work/'hertz_candidate.json').write_text(json.dumps(dict(status='diagnostic_only',candidate='differentiate scalar UTD Hertz potential',results=rows),indent=2),encoding='utf-8')

if __name__=='__main__':
    import sys
    main(Path(sys.argv[1]).resolve())

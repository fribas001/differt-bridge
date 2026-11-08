"""Diagnostic GO substitution; deliberately not installed as a wedge model."""
import json,sys
from pathlib import Path
import numpy as np
from halfspace_reference import reflected,go_reflected
from analyze_model_errors import read,z,relative,model
from ray_wedge2d import fixture
from dielectric_model import go_coefficient

root=Path(sys.argv[1]);work=root/'work/dielectric-corrections';rows=[]
for row in read(work/'maxwell_analysis.json')['results']:
    if row['name'].startswith(('free','pec')):continue
    raw=read(work/'maxwell'/(row['name']+'_80.json'));eps=complex(*raw['epsilon']);pol=raw['polarization'];ref=z(row['extrapolated_field'])
    base=np.empty_like(ref);changed=np.empty_like(ref);deltas=[]
    for i,s in enumerate(raw['sources']):
        for j,r in enumerate(raw['receivers']):
            base[i,j]=model(s,r,eps,pol,mode='legacy')[0];delta=0j;c=fixture(s,r,eps,pol)
            for face,axis in [('reflection0',0),('reflectionn',1)]:
                if go_coefficient(c,face) is not None:delta+=reflected(s,r,eps,pol,axis)-go_reflected(s,r,eps,pol,axis)
            changed[i,j]=base[i,j]+delta;deltas.append(abs(delta))
    rows.append(dict(name=row['name'],baseline_rms=relative(base,ref),exact_plane_GO_control_rms=relative(changed,ref),largest_reflection_delta=max(deltas)))
(root/'work/diffraction-model-errors/plane_reflection_control.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')

"""Check the new field solve on the earlier independent Maxwell boundary probes."""
import json,sys
from pathlib import Path
import numpy as np
from canonical_maxwell_refinement import CanonicalRefiner
from analyze_model_errors import read,z,pair,relative

root=Path(sys.argv[1]);original=root/'work/dielectric-corrections';target=root/'work/maxwell-refinement/boundary.json'
solver=CanonicalRefiner(24);rows=[]
for record in read(original/'maxwell_boundary_analysis.json')['results']:
    raw=read(original/'maxwell_boundary'/(record['name']+'_80.json'));eps=complex(*raw['epsilon']);u,f,r,meta=solver.solve(raw['sources'],raw['receivers'],eps,raw['polarization']);ref=z(record['extrapolated_field'])
    # Nine receivers are three triplets on opposite sides of GO boundaries.
    jump=np.max(abs(u[:,2::3]-u[:,0::3]))/np.max(abs(u))
    rows.append(dict(name=record['name'],**meta,field=pair(u),reference=pair(ref),rms_error=relative(u,ref),small_offset_triplet_span=float(jump),sources=raw['sources'],receivers=raw['receivers']))
target.write_text(json.dumps(dict(scope='Independent earlier FDFD near/exact-boundary probes; finite smooth field, no GO switching rule in full-wave mode',results=rows),indent=2))

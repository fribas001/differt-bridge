"""Independent validation ports, snapped to a shared FDFD convergence lattice."""
import copy,json
from pathlib import Path
import numpy as np
from run_model_error_reference import SWEEP_SOURCES,SWEEP_RECEIVERS,SWEEP_MATERIALS
from ray_wedge2d import fixture

SOURCES=np.round(SWEEP_SOURCES*20)/20
RECEIVERS=np.round(SWEEP_RECEIVERS*20)/20
MATERIALS=SWEEP_MATERIALS
DOMAIN=dict(dimension=2,source_type='line',material_domain='solid_quadrant',exterior_angle_deg=270)

def cases():
    result=[]
    for name,eps in MATERIALS.items():
        for pol in ('Ez','Hz'):
            for i,s in enumerate(SOURCES):
                c=fixture(s,RECEIVERS[0],eps,pol,f'{name}_{pol}_source{i}')
                c['receivers']=[[*map(float,r),0.] for r in RECEIVERS]
                c['solver'].update(los=True,specular_reflection=True)
                c['maxwell_domain']=copy.deepcopy(DOMAIN)
                angle=lambda r:float((np.rad2deg(np.arctan2(r[1],r[0]))-90)%360)
                c['study']=dict(kind='canonical_maxwell_refinement',material=name,polarization=pol,source_index=i,source_angle_deg=angle(s),receiver_angles_deg=[angle(r) for r in RECEIVERS],epsilon=[eps.real,eps.imag])
                c['expected']='Native point-source rays plus a separately labelled solid-wedge 2D line-source refinement; no 3D Maxwell claim.'
                result.append(c)
    return result

if __name__=='__main__':
    import sys
    p=Path(sys.argv[1]);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(dict(cases=cases()),indent=2))

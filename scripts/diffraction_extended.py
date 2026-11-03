"""Additional physical limits, antenna patterns and reflection boundaries."""
import copy
import json
import math
from pathlib import Path
from diffraction_cases import base,benchmark_cases,f32


def extended():
    cases=[]
    for name in ('dipole','hw_dipole','tr38901'):
        c=base('antenna_'+name);c.update(category='antenna_patterns',pattern=name,tx=[-4.,4.,-3.],receivers=[[4.,-2.,5.]])
        cases.append(c)
    for s in (.5,1.):
        c=base('roughness_'+str(s).replace('.','_'));c['category']='material';c['material']['scattering_coefficient']=s;cases.append(c)
    c=base('zero_material_contrast');c['category']='material_limit';c['material'].update(relative_permittivity=1.,conductivity=0.)
    c['expected']='Physical zero-contrast limit has no edge-scattered field; empirical wedge models may fail this limit';cases.append(c)
    offsets=[-.1,-.01,-.001,-.0001,0,.0001,.001,.01,.1]
    for pol in ('V','H'):
        c=base('reflection_boundary_'+pol.lower());c.update(category='reflection_boundary',tx_pol=pol,rx_pol=pol,
            receivers=[[f32(5*math.cos(math.radians(225+a))),f32(5*math.sin(math.radians(225+a))),0.] for a in offsets],boundary_offsets_deg=offsets)
        c['solver']['specular_reflection']=True;c['expected']='Coherent reflection plus diffraction across reflected shadow boundary; LoS excluded consistently'
        cases.append(c)
        metal=copy.deepcopy(c);metal['name']='reflection_boundary_pec_'+pol.lower()
        metal['material'].update(relative_permittivity=1.,conductivity=f32(1e10));cases.append(metal)
    for sign in (-1,1):
        c=base('receiver_shift_'+('minus' if sign<0 else 'plus'));c.update(category='local_position_sensitivity',receivers=[[4.,f32(-2.+sign*.001),0.]])
        cases.append(c)
    # Stable geometry gradients are probed with +/-1 mm endpoint displacements.
    return cases


if __name__=='__main__':
    import sys
    Path(sys.argv[1]).write_text(json.dumps(dict(schema='diffraction_cases_v1',cases=extended()),indent=2))

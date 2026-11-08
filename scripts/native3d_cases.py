"""Native 3D electric-dipole tests; identical float32 inputs in both engines."""
import copy,json
from pathlib import Path
import numpy as np
from diffraction_cases import base,wedge,f32
from diffraction_reference import C

ANGLES=np.arange(5,270,5.)
def point(phi,r,z):
    a=np.deg2rad(90+phi)
    return [f32(r*np.cos(a)),f32(r*np.sin(a)),f32(z)]

def case(name,phi=60.,scale=1.,height=0.,axis='z',angles=ANGLES):
    c=base(name);c['frequency_hz']=C;c['pattern']='dipole'
    c['material'].update(relative_permittivity=1.,conductivity=f32(1e12),thickness=10.)
    c['tx']=point(phi,3*scale,0.)
    c['receivers']=[point(a,4*scale,height*scale) for a in angles]
    c['meshes']=[wedge(length=160,height=160)]
    c['canonical_edges'][0]['half_length']=160.
    c['solver'].update(los=True,specular_reflection=True)
    c['rx_orientation']={'z':[0.,0.,0.],'x':[0.,np.pi/2,0.],'y':[np.pi/2,np.pi/2,0.]}[axis]
    c['study']=dict(kind='native3d',scale=scale,height=height,source_angle=phi,receiver_axis=axis,angles=list(map(float,angles)),group='sweep')
    c['expected']='Native point-electric-dipole total channel versus exact infinite PEC wedge Maxwell field; no 2D conversion.'
    return c

def cases():
    out=[]
    for scale in (.5,1.,4.):
        for height in (0.,2.,8.):
            for phi in (30.,60.):
                out.append(case(f'zz_s{scale:g}_h{height:g}_p{phi:g}',phi,scale,height))
    for axis in ('x','y'):
        for height in (0.,2.,8.):out.append(case(f'z{axis}_h{height:g}',60.,1.,height,axis))
    for phi,center,label in ((30.,210.,'shadow'),(60.,120.,'reflection0'),(120.,240.,'reflectionn')):
        angles=[center+d for d in (-1.,-.1,-.01,-.001,-.0001,0.,.0001,.001,.01,.1,1.)]
        for height in (0.,8.):
            c=case(f'boundary_{label}_h{height:g}',phi,1.,height,angles=angles);c['study']['group']='boundary';out.append(c)
    for axis in ('z','x','y'):
        c=case('free_z'+axis,60.,1.,8.,axis);c['solver'].update(diffraction=False,specular_reflection=False)
        c['study']['group']='free';c['receivers']=[point(a,4.,8.) for a in (40,80,100,160)];c['study']['angles']=[40,80,100,160];out.append(c)
    for axis in ('z','x','y'):
        c=case('reciprocity_z'+axis,60.,1.,8.,axis,angles=[170.]);c['study']['group']='reciprocity';out.append(c)
        r=copy.deepcopy(c);r['name']+='__reverse';r['tx'],r['receivers']=c['receivers'][0],[c['tx']]
        r['tx_orientation'],r['rx_orientation']=r['rx_orientation'],[0.,0.,0.]
        r['study']['reverse_of']=c['name'];out.append(r)
    for sigma in (1e8,1e16):
        c=case(f'pec_sigma{sigma:g}',60.,1.,8.);c['material']['conductivity']=f32(sigma)
        c['study']['group']='conductivity';out.append(c)
    c=case('extent80',60.,1.,8.);c['meshes']=[wedge(length=80,height=80)];c['canonical_edges'][0]['half_length']=80.;c['study']['group']='extent';out.append(c)
    return out

if __name__=='__main__':
    import sys
    p=Path(sys.argv[1]);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(dict(cases=cases()),indent=2),encoding='utf-8')
    print(len(cases()),'cases')

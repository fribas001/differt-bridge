"""Matched dielectric fixtures. No engine imports or engine-produced reference data."""
import copy
import numpy as np
from diffraction_cases import f32,benchmark_cases
from diffraction_physics_cases import fixture

MATERIALS={
    'concrete':(5.24,.123086944,.1), 'lossless':(4.,0.,.1),
    'high_loss':(5.24,10.,.1), 'thin':(5.24,.123086944,.001),
    'thick':(5.24,.123086944,1.), 'pec':(1.,1e12,.1),
    'air':(1.,0.,.1),
}

def make(name,pi,pd,pol,material,**kwargs):
    c=fixture(name,pi,pd,pol,material,**kwargs)
    er,sigma,d=MATERIALS[material]
    c['material'].update(relative_permittivity=f32(er),conductivity=f32(sigma),thickness=f32(d))
    c['study']=dict(kind='reciprocity',material=material,polarization=pol,skew=kwargs.get('z',(0.,0.))!=(0.,0.))
    return c

def cases():
    result=[]
    def paired(c):
        result.append(c);b=copy.deepcopy(c);b['name']+='__reverse'
        b['tx'],b['receivers']=b['receivers'][0],[b['tx']]
        b['tx_pol'],b['rx_pol']=b['rx_pol'],b['tx_pol']
        b['study']['reverse_of']=c['name'];result.append(b)
    for mat in ('concrete','lossless','high_loss','thin','thick','pec'):
        for i,(pi,pd) in enumerate(((60,100),(30,240),(150,80),(120,166),(150,260))):
            for pol in ('V','H'):paired(make(f'{mat}_angle{i}_{pol}',pi,pd,pol,mat))
    a,b=np.deg2rad([57,23]);ry=np.array([[np.cos(a),0,np.sin(a)],[0,1,0],[-np.sin(a),0,np.cos(a)]])
    rz=np.array([[np.cos(b),-np.sin(b),0],[np.sin(b),np.cos(b),0],[0,0,1]])
    for label,rot,z in [('skew',np.eye(3),(-3,5)),('tilted',rz@ry,(0.,0.)),('tilted_skew',rz@ry,(-3,5))]:
        for mat in ('concrete','lossless','pec'):
            for pol in ('VV','HH','VH','HV'):
                paired(make(f'{mat}_{label}_{pol}',45,210,pol,mat,rotation=rot,z=z))
    offsets=[-1.,-.1,-.01,-.001,-.0001,0.,.0001,.001,.01,.1,1.]
    configurations=[(m,'broadside',p,(0.,0.),3.5e9) for m in ('concrete','lossless','high_loss','thin','pec','air') for p in ('VV','HH')]
    configurations += [(m,'skew',p,(-3,5),3.5e9) for m in ('concrete','lossless') for p in ('VV','HH','VH','HV')]
    configurations += [('concrete','28GHz',p,(0.,0.),28e9) for p in ('VV','HH')]
    for mat,label,pol,z,freq in configurations:
        for boundary,pi,pd in [('incident',30,210),('reflection0',60,120),('reflectionn',120,240)]:
            c=make(f'boundary_{mat}_{label}_{boundary}_{pol}',pi,pd,pol,mat,z=z)
            c['receivers']=[make('x',pi,pd+eps,pol,mat,z=z)['receivers'][0] for eps in offsets]
            c['frequency_hz']=freq;c['solver'].update(los=True,specular_reflection=True)
            c['study'].update(kind='boundary',boundary=boundary,offsets_deg=offsets,boundary_angle_deg=pd,frequency_hz=freq)
            result.append(c)
    for mat in ('concrete','lossless','pec'):
        for pol in ('V','H'):
            for pi,pd in ((60,100),(120,166)):
                c=make(f'order_{mat}_{pi}_{pol}',pi,pd,pol,mat);c['study']['kind']='mesh_order';result.append(c)
                b=copy.deepcopy(c);b['name']+='__face_swap';b['study']['same_geometry_as']=c['name']
                tri=b['meshes'][0]['triangles'];b['meshes'][0]['triangles']=tri[2:]+tri[:2];result.append(b)
    original={c['name']:c for c in benchmark_cases()}
    for name in ('block_incoming','block_outgoing','clear_nearby','block_near_edge_0_001'):
        c=copy.deepcopy(original[name]);c['study']=dict(kind='obstacle',expected_paths=1 if name=='clear_nearby' else 0);result.append(c)
    assert len({c['name'] for c in result})==len(result)
    return result

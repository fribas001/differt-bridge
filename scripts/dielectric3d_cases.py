"""Identical 3D dielectric ports for both native engines and Maxwell solvers."""
import copy,json
from pathlib import Path
import numpy as np
from scipy.constants import epsilon_0
from native3d_cases import case,point
from dielectric3d_synthesis import campaign
from diffraction_cases import f32
MATERIALS={'concrete':5.24-.632143019j,'lower':2.5-.35j}
ORIENT={'z':[0.,0.,0.],'x':[0.,np.pi/2,0.],'y':[np.pi/2,np.pi/2,0.]}

def cases():
    p=campaign();out=[];nr=len(p['angles'])
    for material,eps in MATERIALS.items():
        for si,source in enumerate(p['sources']):
            for txaxis in ('x','y','z'):
                for rxaxis in ('x','y','z'):
                    for hi,height in enumerate(p['heights']):
                        c=case(f'{material}_s{si}_{txaxis}{rxaxis}_h{height:g}',axis=rxaxis)
                        c['tx']=source;c['receivers']=p['receivers'][hi*nr:(hi+1)*nr];c['tx_orientation']=ORIENT[txaxis]
                        c['material'].update(relative_permittivity=f32(eps.real),conductivity=f32(-eps.imag*2*np.pi*299792458.*epsilon_0),thickness=10.)
                        c['study']=dict(kind='dielectric3d',material=material,epsilon=[eps.real,eps.imag],source_index=si,tx_axis=txaxis,rx_axis=rxaxis,height=height,height_index=hi,angles=p['angles'],group='primary')
                        c['expected']='Native full vector point-dipole channel against an independent solid-dielectric Maxwell wedge; no PEC or 2D substitution.'
                        out.append(c)
    for txaxis in ('x','y','z'):
        for rxaxis in ('x','y','z'):
            c=copy.deepcopy(next(c for c in out if c['name']==f'concrete_s0_{txaxis}{rxaxis}_h3'))
            c['name']=f'reciprocity_{txaxis}{rxaxis}';c['receivers']=[point(170,2.,3.)];c['study'].update(group='reciprocity',angles=[170.]);out.append(c)
            r=copy.deepcopy(c);r['name']+='__reverse';r['tx'],r['receivers']=c['receivers'][0],[c['tx']]
            r['tx_orientation'],r['rx_orientation']=c['rx_orientation'],c['tx_orientation'];r['study']['reverse_of']=c['name'];out.append(r)
    return out

if __name__=='__main__':
    import sys
    p=Path(sys.argv[1]);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(dict(cases=cases()),indent=2),encoding='utf-8');print(len(cases()),'cases')

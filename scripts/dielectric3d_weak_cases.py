"""Fresh materials and ports frozen before evaluating the extrapolation holdout."""
import copy,json,sys
from pathlib import Path
import numpy as np
from scipy.constants import epsilon_0
from native3d_cases import point
from diffraction_cases import f32
from dielectric3d_shadow_cases import primary
from dielectric3d_refinement import ORIENT,validate

def cases():
    template=primary()[0];rows=[]
    angles=[243.99,244.,244.01,250.,260.,265.];heights=[.45,1.35,2.6]
    for material,eps in [('new_a',4.4-.65j),('new_b',6.4-.9j)]:
        for tx in 'xyz':
            for rx in 'xyz':
                for hi,height in enumerate(heights):
                    c=copy.deepcopy(template);c['name']=f'{material}_{tx}{rx}_h{height:g}';c['tx']=point(64.,1.65,.1);c['receivers']=[point(a,2.15,height) for a in angles]
                    c['tx_orientation']=ORIENT[tx];c['rx_orientation']=ORIENT[rx]
                    c['material'].update(relative_permittivity=f32(eps.real),conductivity=f32(-eps.imag*2*np.pi*299792458.*epsilon_0))
                    c['study']=dict(kind='dielectric3d',material=material,epsilon=[eps.real,eps.imag],source_index=0,source_angle=64.,tx_axis=tx,rx_axis=rx,height=height,height_index=hi,angles=angles,group='new_holdout')
                    c['expected']='Unseen complete-vector low-height and skew ports, including +/-0.01 degree shadow-boundary stencils.';validate(c);rows.append(c)
    return rows

def main(folder):
    folder.mkdir(parents=True,exist_ok=True);rows=cases()
    for label,part in [('new_holdout',rows),*[(m,[c for c in rows if c['study']['material']==m]) for m in ('new_a','new_b')]]:
        (folder/(label+'_cases.json')).write_text(json.dumps(dict(cases=part),indent=2),encoding='utf-8')

if __name__=='__main__':main(Path(sys.argv[1]))

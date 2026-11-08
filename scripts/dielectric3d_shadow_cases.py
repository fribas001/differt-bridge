"""Primary and fresh holdout manifests for the guarded 3D dielectric solver."""
import copy,json,sys
from pathlib import Path
import numpy as np
from scipy.constants import epsilon_0
from native3d_cases import case,point
from dielectric3d_cases import cases as original_cases
from diffraction_cases import f32
from dielectric3d_refinement import DOMAIN,ORIENT,validate

def primary():
    out=[c for c in original_cases() if c['study']['group']=='primary']
    for c in out:c['maxwell_domain']=copy.deepcopy(DOMAIN)
    return out

def reciprocity():
    lookup={c['name']:c for c in primary()};out=[]
    for tx in 'xyz':
        for rx in 'xyz':
            c=copy.deepcopy(lookup[f'concrete_s0_{tx}{rx}_h3']);c['name']=f'shadow_reciprocity_{tx}{rx}'
            c['receivers']=[point(245.,2.,3.)];c['study'].update(angles=[245.],group='reciprocity')
            reverse=copy.deepcopy(c);reverse['name']=c['name']+'__reverse';reverse['tx']=c['receivers'][0];reverse['receivers']=[c['tx']]
            reverse['tx_orientation'],reverse['rx_orientation']=c['rx_orientation'],c['tx_orientation']
            reverse['study'].update(tx_axis=rx,rx_axis=tx,reverse_of=c['name'])
            out.extend((c,reverse))
    return out

def holdout():
    angles=[20.,110.,200.,223.49,223.5,223.51,235.,245.,251.24,251.25,251.26,255.,260.,265.]
    sources=[point(43.5,1.25,-.2),point(71.25,1.8,.25)];heights=[.7,2.2];out=[]
    for material,eps in [('holdout_a',3.3-.48j),('holdout_b',7.1-1.1j)]:
        for si,source in enumerate(sources):
            for txaxis in 'xyz':
                for rxaxis in 'xyz':
                    for hi,height in enumerate(heights):
                        c=case(f'{material}_s{si}_{txaxis}{rxaxis}_h{height:g}',axis=rxaxis)
                        c['tx']=source;c['receivers']=[point(a,2.3,height) for a in angles];c['tx_orientation']=ORIENT[txaxis]
                        c['material'].update(relative_permittivity=f32(eps.real),conductivity=f32(-eps.imag*2*np.pi*299792458.*epsilon_0),thickness=10.)
                        c['maxwell_domain']=copy.deepcopy(DOMAIN);c['study']=dict(kind='dielectric3d',material=material,epsilon=[eps.real,eps.imag],source_index=si,source_angle=[43.5,71.25][si],tx_axis=txaxis,rx_axis=rxaxis,height=height,height_index=hi,angles=angles,group='holdout')
                        c['expected']='Fresh complete-vector 3D holdout; two new materials and source/receiver coordinates.';out.append(c)
    return out

def main(output):
    output.mkdir(parents=True,exist_ok=True)
    for label,cases in [('primary',primary()),('holdout',holdout())]:
        for c in cases:validate(c)
        (output/(label+'_cases.json')).write_text(json.dumps(dict(cases=cases),indent=2),encoding='utf-8')
        for material in dict.fromkeys(c['study']['material'] for c in cases):
            part=[c for c in cases if c['study']['material']==material];(output/(material+'_cases.json')).write_text(json.dumps(dict(cases=part),indent=2),encoding='utf-8')
        print(label,len(cases))
    cases=reciprocity()
    for c in cases:validate(c)
    (output/'reciprocity_cases.json').write_text(json.dumps(dict(cases=cases),indent=2),encoding='utf-8')
    print('reciprocity',len(cases))

if __name__=='__main__':main(Path(sys.argv[1]))

"""Matched actual-engine fixtures for the independent 2D Maxwell campaign."""
import json,sys
from pathlib import Path
from ray_wedge2d import fixture
from run_maxwell_reference import SOURCES,RECEIVERS,MATERIALS

def cases():
    result=[]
    for material,epsilon in MATERIALS.items():
        for pol in ('Ez','Hz'):
            for i,source in enumerate(SOURCES):
                c=fixture(source,RECEIVERS[0],epsilon,pol,f'{material}_{pol}_source{i}')
                c['receivers']=[[*map(float,r),0.] for r in RECEIVERS]
                c['solver'].update(los=True,specular_reflection=True)
                c['study']=dict(kind='maxwell',material=material,polarization=pol,source_index=i,epsilon=[epsilon.real,epsilon.imag])
                c['expected']='Compare each actual-engine ray after cylindrical line-source conversion with independent solid-wedge Maxwell field.'
                result.append(c)
    return result

if __name__=='__main__':Path(sys.argv[1]).write_text(json.dumps(dict(cases=cases()),indent=2),encoding='utf-8')

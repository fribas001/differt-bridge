import copy,sys
from pathlib import Path
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from refinement_cases import cases
from canonical_maxwell_refinement import validate,UnsupportedScene,CanonicalRefiner,refine_cases

@pytest.fixture
def case():return cases()[0]

def test_canonical_validation_does_not_mutate_scene(case):
    before=copy.deepcopy(case);eps,pol=validate(case)
    assert case==before and pol=='Ez' and eps.imag<0

@pytest.mark.parametrize('change',[
    lambda c:c.pop('maxwell_domain'),
    lambda c:c['maxwell_domain'].update(source_type='point'),
    lambda c:c['meshes'].append(copy.deepcopy(c['meshes'][0])),
    lambda c:c['meshes'][0]['vertices'][0].__setitem__(0,1e-5),
    lambda c:c['tx'].__setitem__(2,.001),
    lambda c:c.update(rx_pol='H'),
    lambda c:c['material'].update(thickness=.1),
    lambda c:c['material'].update(conductivity=0),
    lambda c:c['solver'].update(max_depth=2),
    lambda c:c['solver'].update(diffuse_reflection=True),
    lambda c:c['receivers'].__setitem__(0,c['tx'].copy()),
    lambda c:c['receivers'].__setitem__(0,[1,1,0]),
    lambda c:c.update(receivers=[]),
    lambda c:c['physics'].update(opening_deg=120),
])
def test_unsupported_geometry_and_features_fail_closed(case,change):
    change(case)
    with pytest.raises(UnsupportedScene):validate(case)

def test_obstacle_batch_is_rejected_before_computation(case,monkeypatch):
    obstacle=copy.deepcopy(case)
    center=np.asarray(case['tx'])*.5
    vertices=[(center+5e-6*np.array([x,y,z])).tolist() for x,y,z in [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]]
    triangles=[[0,2,1],[0,3,2],[4,5,6],[4,6,7],[0,1,5],[0,5,4],[1,2,6],[1,6,5],[2,3,7],[2,7,6],[3,0,4],[3,4,7]]
    obstacle['meshes'].append(dict(name='10_micron_blocker',vertices=vertices,triangles=triangles,material='wall'))
    monkeypatch.setattr(CanonicalRefiner,'solve',lambda *a,**k:pytest.fail('Unsupported scene reached solver'))
    with pytest.raises(UnsupportedScene):refine_cases([case,obstacle])

def test_projected_field_is_reciprocal_with_raw_bias_disclosed():
    m=CanonicalRefiner(16);a=[[-2.1,1.3],[-1.2,-2.8]];b=[[2.2,-1.4],[-3.2,2.1]]
    u,f,r,info=m.solve(a,b,4-2j,'Hz');v,_,_,_=m.solve(b,a,4-2j,'Hz')
    assert np.allclose(u,v.T,rtol=1e-13,atol=1e-14)
    assert 0<info['raw_reciprocity_rms']<.005
    assert np.linalg.norm(u-f)>0 and np.isfinite(u).all()

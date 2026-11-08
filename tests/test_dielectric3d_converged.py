import copy,sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import dielectric3d_converged as candidate
from dielectric3d_shadow_cases import primary
from dielectric3d_refinement import UnsupportedScene

def test_extra_obstacle_anywhere_in_batch_prevents_either_resolution(tmp_path,monkeypatch):
    cases=primary()[:2];cases[1]['meshes'].append(copy.deepcopy(cases[1]['meshes'][0]))
    def forbidden(*a,**k):raise AssertionError('Must reject before a numerical solve')
    monkeypatch.setattr(candidate,'refine',forbidden)
    with pytest.raises(UnsupportedScene):candidate.refine_converged(cases,tmp_path/'absent')
    assert not (tmp_path/'absent').exists()

@pytest.mark.parametrize('key,value',[('epsilon',[3.,-.5]),('sources',[[1.,2.,3.]]),('receivers',[[1.,2.,3.]]),('contour',.6),('qmax',28.)])
def test_extrapolation_refuses_different_physical_or_spectral_problems(key,value):
    group=dict(epsilon=[7.1,-1.1],sources=[[0.,1.,0.]],receivers=[[1.,0.,.5]],order=8,contour=.5,qmax=24.,source_hashes={})
    a=dict(status='completed',panels=16,order=8,source_hashes={},groups=[copy.deepcopy(group)],results=[])
    b=copy.deepcopy(a);b['panels']=32;b['groups'][0][key]=value
    with pytest.raises(AssertionError):candidate.combine(a,b)

"""Regression checks for accepting/rejecting migration evidence, without RT imports."""
import copy
import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('rt22_compare', Path(__file__).resolve().parents[1]/'scripts/compare_rt22_results.py')
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)


def evidence():
    paths = [dict(rx=0, interactions=[8], points=[[0.,0.,0.],[0.,1.,0.],[1.,1.,0.]],
                  delay_s=1e-8, finite=True, a=[1e-4,2e-4], cir=[2e-4,1e-4]),
             dict(rx=0, interactions=[], points=[[0.,0.,0.],[1.,1.,0.]],
                  delay_s=5e-9, finite=True, a=[3e-4,4e-4], cir=[4e-4,3e-4])]
    return dict(versions={'sionna-rt':'2.1.0'}, manifest_sha256='same', cases=[
        dict(name='fixture', status='completed', valid_paths=2,
             array_shapes={'a':[1,2]}, input_file_sha256='same', effective_materials={'eps':5.}, paths=paths)])


def test_route_order_is_not_physics():
    old = evidence()
    new = copy.deepcopy(old)
    new['versions']={'sionna-rt':'2.2.0'}
    new['cases'][0]['paths'].reverse()
    result=comparison.compare(old,new)
    assert result['passed'] and result['cases'][0]['field_absolute']==0
    assert result['cases'][0]['phase_rad']==0


@pytest.mark.parametrize('damage', ['missing_path','phase','shape','obstacle','failed_case'])
def test_detects_scientific_regressions(damage):
    old=evidence();new=copy.deepcopy(old);case=new['cases'][0]
    if damage=='missing_path':case['paths'].pop()
    if damage=='phase':case['paths'][0]['a'][0]+=1e-5
    if damage=='shape':case['array_shapes']={'a':[2,1]}
    if damage=='obstacle':case['input_file_sha256']='changed mesh'
    if damage=='failed_case':case['status']='failed'
    assert not comparison.compare(old,new)['passed']


def test_empty_or_mismatched_campaign_cannot_pass():
    old=evidence();new=copy.deepcopy(old);new['manifest_sha256']='different'
    with pytest.raises(AssertionError):comparison.compare(old,new)
    old['cases']=[];new=copy.deepcopy(old)
    with pytest.raises(AssertionError):comparison.compare(old,new)

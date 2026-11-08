"""Physical 3D checks and fail-closed obstacle/material scope tests."""
import copy,sys
from pathlib import Path
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from native3d_cases import case
from hertz_pec3d import validate,refine,vector,potential
from maxwell3d_pec_reference import wedge_green,electric_z_column,free_dyadic

@pytest.mark.parametrize('height',[0.,2.,8.])
def test_uniform_vector_matches_independent_maxwell(height):
    s=[-2.598076,1.5,0];r=[2.,-3.5,height]
    actual=vector(s,r,h=2.5e-4);reference=electric_z_column(s,r)
    assert np.linalg.norm(actual-reference)/np.linalg.norm(reference)<.02

def test_vector_pec_plane_is_exact_method_of_images():
    s=np.array([-2.,1.,0.]);r=np.array([-1.,-3.,4.]);image=s.copy();image[0]*=-1
    np.testing.assert_allclose(electric_z_column(s,r,alpha=np.pi),(free_dyadic(s,r)-free_dyadic(image,r))[:,2],atol=1e-10,rtol=1e-8)

def test_point_source_zz_reciprocity_without_averaging():
    s=np.array([-2.,1.,0.]);r=np.array([1.,-3.,4.])
    np.testing.assert_allclose(wedge_green(s,r),wedge_green(r,s),rtol=1e-12,atol=1e-13)
    np.testing.assert_allclose(vector(s,r)[2],vector(r,s)[2],rtol=1e-7,atol=1e-9)

def test_broadside_cross_polar_field_is_a_null():
    np.testing.assert_allclose(vector([-2.,1.,0.],[1.,-3.,0.])[:2],0.,atol=1e-10)

@pytest.mark.parametrize('change',['obstacle','vertex','triangles','dielectric','pattern','source_axis','receiver_axis','frequency','transmission','multiple_edges','finite_edge','missing_declaration'])
def test_unsupported_scene_never_silently_loses_physics(change):
    c=case('guard')
    if change=='obstacle':c['meshes'].append(copy.deepcopy(c['meshes'][0]))
    if change=='vertex':c['meshes'][0]['vertices'][0][0]+=1e-7
    if change=='triangles':c['meshes'][0]['triangles'].pop()
    if change=='dielectric':c['material']['relative_permittivity']=5.24
    if change=='pattern':c['pattern']='iso'
    if change=='source_axis':c['tx_orientation']=[0,.1,0]
    if change=='receiver_axis':c['rx_orientation']=[0,.1,0]
    if change=='frequency':c['frequency_hz']=3.5e9
    if change=='transmission':c['solver']['refraction']=True
    if change=='multiple_edges':c['solver']['max_depth']=2
    if change=='finite_edge':c['meshes'][0]['vertices'][0][2]=-1
    if change=='missing_declaration':c.pop('study')
    with pytest.raises(ValueError):validate(c)

def test_whole_batch_is_guarded_before_any_result(monkeypatch):
    import hertz_pec3d
    good=case('good');bad=copy.deepcopy(good);bad['material']['relative_permittivity']=4
    def forbidden(*args,**kwargs):raise AssertionError('field evaluated before batch guard')
    monkeypatch.setattr(hertz_pec3d,'vector',forbidden)
    with pytest.raises(ValueError):refine([good,bad])

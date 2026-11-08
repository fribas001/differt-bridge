"""Physical constraints independent of the measured campaign summaries."""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from reciprocal_geometry import _solve,_valid_laws,_blocked,_basis

class Mesh:
    """Brute-force triangle list; exercises visibility without its BVH."""
    def __init__(self,triangles):
        self.triangles=np.asarray(triangles,float);self.a=self.triangles[:,0]
        self.e1=self.triangles[:,1]-self.a;self.e2=self.triangles[:,2]-self.a
        self.normals=np.cross(self.e1,self.e2);self.norm=np.linalg.norm(self.normals,axis=1)
        self.error=np.full(len(triangles),32*np.finfo(float).eps);self.segments_checked=0
    def _query(self,*args):return np.arange(len(self.triangles))

def test_mixed_stationary_chain_reverses_and_obeys_reflection_law():
    n=np.array([0.,0.,1.]);ground=np.array([[-20,-20,-3],[20,-20,-3],[0,20,-3.]])
    supports=[dict(kind=1,origin=ground[0],basis=_basis(n),normal=n,triangles=[ground]),
              dict(kind=8,origin=np.array([0.,0.,-20]),basis=np.array([[0.],[0.],[1.]]),length=40.)]
    tx=np.array([-4.,4.,0.]);rx=np.array([4.,-2.,0.])
    a=_solve(tx,rx,supports);b=_solve(rx,tx,supports[::-1])
    assert _valid_laws(a,supports) and _valid_laws(b,supports[::-1])
    np.testing.assert_allclose(a,b[::-1],atol=1e-8,rtol=0)

def test_endpoint_contact_never_exempts_nearby_real_blocker():
    endpoint=[[0.,-1,-1],[0,1,-1],[0,0,1]]
    for offset in (1e-3,1e-5,1e-7):
        obstacle=np.asarray(endpoint)+[offset,0,0]
        visibility=Mesh([endpoint,obstacle])
        assert _blocked(visibility,np.array([0.,0,0]),np.array([1.,0,0]),[0],[])
    assert not _blocked(Mesh([endpoint]),np.array([0.,0,0]),np.array([1.,0,0]),[0],[])

def test_coplanar_obstacle_is_not_an_endpoint_gap():
    tri=[[0,0,0],[1,0,0],[0,1,0]]
    assert _blocked(Mesh([tri]),np.array([-.1,.2,0]),np.array([.8,.2,0]),[],[])

def test_exact_pec_reference_is_reciprocal_for_both_scalar_polarizations():
    from maxwell2d_reference import pec_green
    for pol in ('Ez','Hz'):
        a=pec_green([-2.5,1.5],[3.5,-2.],pol);b=pec_green([3.5,-2.],[-2.5,1.5],pol)
        np.testing.assert_allclose(a,b,atol=1e-13,rtol=1e-13)

def test_independent_maxwell_free_space_converges_to_signed_hankel_solution():
    from maxwell2d_reference import Maxwell2D,free_green
    s=[[-1.5,.5]];r=[[1.5,-1.]];errors=[]
    for ppw in (8,16):
        model=Maxwell2D(ppw=ppw,inner=3,pml=1.5,epsilon=1+0j,geometry='free',polarization='Ez')
        u,residual=model.solve(s,r)
        assert residual<1e-10
        errors.append(abs(u[0,0]/free_green(s[0],r[0])-1))
    assert errors[1]<errors[0]/3

def test_guard_rejects_unknown_runtime_code():
    from reciprocal_corrections import _guard
    import pytest
    with pytest.raises(RuntimeError,match='Unsupported runtime'):_guard(test_guard_rejects_unknown_runtime_code,'not-a-source-digest')

def test_coincident_go_merge_supports_synthetic_and_element_path_shapes():
    from reciprocal_boundary import duplicate_mask
    from types import SimpleNamespace
    for synthetic in (False,True):
        shape=(1,1,2) if synthetic else (1,1,1,1,2)
        valid=np.ones(shape,bool);flags=np.zeros((1,*shape),int);flags[...,0]=8
        vertices=np.zeros((1,*shape,3))
        p=SimpleNamespace(valid=valid,interactions=flags,vertices=vertices,
                          sources=np.array([[-1.],[1.],[0.]]),targets=np.array([[1.],[-1.],[0.]]))
        mask=duplicate_mask(p,'sionna');assert mask.sum()==1 and mask[...,1].all()
        # The same GO ray must survive if no valid diffraction route supports it.
        p.valid[...,0]=False;assert not duplicate_mask(p,'sionna').any()

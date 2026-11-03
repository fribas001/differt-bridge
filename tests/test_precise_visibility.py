"""Known-valid corners, real blockers, seams, and coordinate transforms."""
import json
from pathlib import Path
import sys
import numpy as np
import pytest
import equinox as eqx
import jax.numpy as jnp

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/differt_bridge'))
import differt_backend as b
from precise_visibility import SegmentVisibility,trace_specular
from differt.geometry import Scene,Mesh,ExhaustivePathTracer

CASES=json.loads((Path(__file__).resolve().parents[1]/'examples/corner_investigation/minimal_fixture.json').read_text())['cases']

def fixture(case,rotation=None,shift=None,scale=1.):
    r=np.eye(3) if rotation is None else rotation
    t=np.zeros(3) if shift is None else np.asarray(shift)
    transform=lambda x:scale*np.asarray(x)@r.T+t
    return (Mesh(vertices=jnp.asarray(transform(case['triangle_vertices']).reshape(-1,3),dtype=jnp.float64),
                 triangles=jnp.asarray([[0,1,2],[3,4,5]],dtype=jnp.int32)),transform(case['tx']),transform(case['rx']))

def trace(mesh,tx,rx):
    check=SegmentVisibility(mesh)
    scene=Scene(mesh=check.candidate_mesh,transmitters=jnp.asarray([tx]),receivers=jnp.asarray([rx]))
    paths=ExhaustivePathTracer(min_len=10*np.finfo(np.float32).eps).trace_path_candidates(
        scene,jnp.asarray([[0,1]],dtype=jnp.int32),jnp.asarray([[0,0]],dtype=jnp.int32))
    return check.validate(paths)

def add_blocker(mesh,start,end,distance,offset=0.):
    d=end-start;d=d/np.linalg.norm(d)
    u=np.cross(d,[0.,0.,1.]);u/=np.linalg.norm(u);v=np.cross(d,u)
    center=start+distance*d+offset*u;size=.002
    tri=np.array([center+size*(u+v),center+size*(-u+v),center-2*size*v])
    return Mesh(vertices=jnp.concatenate([mesh.vertices,jnp.asarray(tri)]),
                triangles=jnp.concatenate([mesh.triangles,jnp.asarray([[6,7,8]],dtype=jnp.int32)]))

@pytest.mark.parametrize('case',CASES,ids=lambda c:c['name'])
@pytest.mark.parametrize('rotation,shift,scale',[(None,None,1.),(b.rotation([.31,-.24,.68]),[100.,-200.,75.],1.),
                                                (b.rotation([-.6,.2,.4]),[-8.,13.,4.],.25),(None,[1e5,-1e5,3e4],100.)])
def test_valid_corner_under_rigid_transforms_and_scale(case,rotation,shift,scale):
    mesh,tx,rx=fixture(case,rotation,shift,scale)
    paths=trace(mesh,tx,rx)
    assert bool(paths.mask[0,0,0])
    assert np.asarray(paths.vertices).dtype==np.float64

@pytest.mark.parametrize('case',CASES,ids=lambda c:c['name'])
@pytest.mark.parametrize('segment',[0,1,2])
@pytest.mark.parametrize('from_end',[False,True])
@pytest.mark.parametrize('distance',[1e-5,1e-4])
def test_real_blockers_ten_and_hundred_microns_from_each_endpoint(case,segment,from_end,distance):
    mesh,tx,rx=fixture(case)
    path=np.asarray(trace(mesh,tx,rx).vertices)[0,0,0]
    start,end=path[segment:segment+2]
    if from_end:start,end=end,start
    obstructed=add_blocker(mesh,start,end,distance)
    assert not bool(trace(obstructed,tx,rx).mask[0,0,0])

@pytest.mark.parametrize('case',CASES,ids=lambda c:c['name'])
def test_mid_segment_blocker_and_near_miss(case):
    mesh,tx,rx=fixture(case);path=np.asarray(trace(mesh,tx,rx).vertices)[0,0,0]
    start,end=path[1:3];half=np.linalg.norm(end-start)/2
    assert not bool(trace(add_blocker(mesh,start,end,half),tx,rx).mask[0,0,0])
    assert bool(trace(add_blocker(mesh,start,end,half,offset=.02),tx,rx).mask[0,0,0])

def test_coplanar_seams_and_wrong_endpoint_identity():
    mesh,tx,rx=fixture(CASES[0])
    # Reverse winding and duplicate mirrors: both are the same endpoint plane.
    mesh=eqx.tree_at(lambda m:m.triangles,mesh,jnp.concatenate([mesh.triangles,mesh.triangles[:,::-1]]))
    paths=trace(mesh,tx,rx);assert bool(paths.mask[0,0,0])
    check=SegmentVisibility(mesh)
    # An unrelated face must not be exempted just because its ID was supplied.
    assert check.blocked([5.9,4.,2.],[6.1,4.,2.],start_face=1)

def test_unshifted_visibility_detects_coplanar_and_transverse_blockers():
    mesh=Mesh(vertices=jnp.array([[0.,-1.,-1.],[0.,1.,-1.],[0.,0.,1.]]),triangles=jnp.array([[0,1,2]]))
    check=SegmentVisibility(mesh)
    assert check.blocked([-1.,0.,0.],[1.,0.,0.])
    assert check.blocked([0.,-2.,0.],[0.,2.,0.])
    assert not check.blocked([1.,-2.,0.],[1.,2.,0.])
    assert not check.blocked([-1.,2.,0.],[1.,2.,0.])

def test_masked_obstacle_is_inactive():
    mesh=Mesh(vertices=jnp.array([[0.,-1.,-1.],[0.,1.,-1.],[0.,0.,1.]]),
              triangles=jnp.array([[0,1,2]]),mask=jnp.array([False]))
    assert not SegmentVisibility(mesh).blocked([-1.,0.,0.],[1.,0.,0.])


@pytest.mark.parametrize('case',CASES,ids=lambda c:c['name'])
def test_original_float32_obstacle_controls(case):
    mesh,tx,rx=fixture(case)
    path=np.asarray(trace(mesh,tx,rx).vertices)[0,0,0]
    for segment,fraction in [(1,.5),(2,3e-5)]:
        start,end=path[segment:segment+2]
        obstacle=add_blocker(mesh,start,end,np.linalg.norm(end-start)*fraction)
        obstacle=eqx.tree_at(lambda m:m.vertices,obstacle,obstacle.vertices.astype(jnp.float32))
        assert not bool(trace(obstacle,tx,rx).mask[0,0,0])


def test_specular_correction_is_used_in_mixed_candidate_chunks():
    mesh,tx,rx=fixture(CASES[0]);mesh=eqx.tree_at(lambda m:m.vertices,mesh,mesh.vertices.astype(jnp.float32))
    scene=Scene(mesh=mesh,transmitters=jnp.asarray([tx],dtype=jnp.float32),receivers=jnp.asarray([rx],dtype=jnp.float32))
    allowed=frozenset({b.InteractionType.REFLECTION,b.InteractionType.SCATTERING})
    results=list(trace_specular(scene,2,'exhaustive',{'chunk_size':16},SegmentVisibility(mesh),allowed))
    assert any(np.any(np.asarray(p.mask)&np.all(np.asarray(p.interaction_types)==0,axis=-1)) for p in results)

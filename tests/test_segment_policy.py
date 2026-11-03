"""Physical units, exact threshold boundaries, safe corner routes and defaults."""
import importlib.util,json,os,sys
from pathlib import Path
import numpy as np
import pytest
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(repo/'src/differt_bridge'));sys.path.insert(0,str(repo/'scripts/runtime_profiles'))
import segment_policy as d
import _bridge_segment_policy as s
from _bridge_geometry import SegmentVisibility,validated_path,reconstruct

@pytest.mark.parametrize('policy',[d,s])
@pytest.mark.parametrize('length,accepted',[(0.,False),(.0009,False),(np.nextafter(.001,0.),False),(.001,True),(np.nextafter(.001,np.inf),True),(.00105,True),(.00603,True),(.01,True)])
def test_physical_metres_and_inclusive_boundary(policy,length,accepted):
    assert policy.segments_at_least([[0,0,0],[length,0,0]])==accepted

@pytest.mark.parametrize('policy',[d,s])
def test_short_internal_segment_not_hidden_by_total_path_length(policy):
    assert not policy.segments_at_least([[0,0,0],[10,0,0],[10.0005,0,0],[20,0,0]])
    assert not policy.segments_at_least([[0,0,0],[1,0,0],[1,0,0]])
    assert not policy.segments_at_least([[0,0,0],[np.nan,0,0]])
    assert not policy.segments_at_least([[0,0,0],[np.inf,0,0]])

@pytest.mark.parametrize('policy',[d,s])
def test_native_and_shared_modes_do_not_mutate_constants(policy,monkeypatch):
    monkeypatch.delenv('RADIO_SEGMENT_PROFILE',raising=False)
    assert policy.segment_profile()=='native' and policy.preliminary_minimum(.01)==.01
    monkeypatch.setenv('RADIO_SEGMENT_PROFILE','shared_1mm')
    assert policy.preliminary_minimum(.01)==0.
    monkeypatch.setenv('RADIO_SEGMENT_PROFILE','native');assert policy.preliminary_minimum(.01)==.01
    monkeypatch.setenv('RADIO_SEGMENT_PROFILE','unknown')
    with pytest.raises(ValueError):policy.segment_profile()

def test_both_engines_use_identical_policy_source():
    assert (repo/'src/differt_bridge/segment_policy.py').read_bytes()==(repo/'scripts/runtime_profiles/_bridge_segment_policy.py').read_bytes()

CASES=json.loads((repo/'examples/corner_investigation/minimal_fixture.json').read_text())['cases']
@pytest.mark.parametrize('case',CASES,ids=lambda c:c['name'])
def test_real_corner_retained_and_blockers_still_rejected(case):
    tri=np.asarray(case['triangle_vertices'],np.float64);tx=np.asarray(case['tx']);rx=np.asarray(case['rx'])
    check=SegmentVisibility(tri);points,reason=validated_path(tx,rx,[0,1],check,d.MINIMUM_M,inclusive=True)
    assert reason is None
    for segment in range(len(points)-1):
        for reverse in (False,True):
            start,end=points[segment:segment+2].copy()
            if reverse:start,end=end,start
            direction=end-start;direction/=np.linalg.norm(direction)
            axis=np.eye(3)[np.argmin(abs(direction))];u=np.cross(direction,axis);u/=np.linalg.norm(u);v=np.cross(direction,u)
            for distance in (1e-6,1e-5,1e-4):
                center=start+direction*distance;size=.002
                obstacle=np.array([center+size*(u+v),center+size*(-u+v),center-2*size*v])
                for dtype in (np.float32,np.float64):
                    blocked=SegmentVisibility(np.concatenate([tri,obstacle[None]]).astype(dtype))
                    assert validated_path(tx,rx,[0,1],blocked,d.MINIMUM_M,inclusive=True)[1]=='obstacle'

def test_differt_native_min_len_is_a_squared_distance():
    import differt_backend as b
    from precise_visibility import SegmentVisibility as DVisibility
    from differt.geometry import Scene,Mesh,ExhaustivePathTracer
    import jax.numpy as jnp
    mesh=Mesh(vertices=jnp.array([[2.,0.,0.],[2.,1.,0.],[2.,0.,1.]],dtype=jnp.float64),triangles=jnp.array([[0,1,2]],jnp.int32))
    # Isolate DiffeRT's length gate; this clear LoS fixture has no blocker.
    # Its Warp visibility kernel accepts float32 only, unlike the image method.
    mesh=DVisibility(mesh).candidate_mesh
    def accepted(length,limit):
        scene=Scene(mesh=mesh,transmitters=jnp.array([[0.,0.,0.]],jnp.float64),receivers=jnp.array([[length,0.,0.]],jnp.float64))
        tracer=ExhaustivePathTracer(min_len=limit)
        p=tracer.trace_path_candidates(scene,jnp.zeros((1,0),jnp.int32),jnp.zeros((1,0),jnp.int32))
        return bool(p.mask[0,0,0])
    old=10*np.finfo(np.float32).eps
    assert not accepted(.00105,old) and accepted(.0012,old)
    assert not accepted(np.nextafter(.001,0.),.001**2)
    assert accepted(.001,.001**2) and accepted(.00105,.001**2)

def test_production_differt_gate_defers_squared_length_cutoff(monkeypatch):
    import differt_backend
    from precise_visibility import SegmentVisibility as DVisibility,trace_specular
    from differt.geometry import Scene,Mesh
    import jax.numpy as jnp
    mesh=Mesh(vertices=jnp.array([[2.,0.,0.],[2.,1.,0.],[2.,0.,1.]],dtype=jnp.float64),triangles=jnp.array([[0,1,2]],jnp.int32))
    def accepted(length):
        scene=Scene(mesh=mesh,transmitters=jnp.array([[0.,0.,0.]],jnp.float64),receivers=jnp.array([[length,0.,0.]],jnp.float64))
        return bool(next(trace_specular(scene,0,'exhaustive',{'chunk_size':16},DVisibility(mesh))).mask[0,0,0])
    monkeypatch.setenv('RADIO_SEGMENT_PROFILE','native');assert not accepted(.00105)
    monkeypatch.setenv('RADIO_SEGMENT_PROFILE','shared_1mm')
    assert accepted(.00105) and accepted(.001) and not accepted(np.nextafter(.001,0.))
    monkeypatch.setenv('RADIO_SEGMENT_PROFILE','native');assert not accepted(.00105)

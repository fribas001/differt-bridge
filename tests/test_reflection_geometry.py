"""Physical reconstruction, real obstacles, near misses and no endpoint gaps."""
import json,sys
from pathlib import Path
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/runtime_profiles'))
from _bridge_geometry import SegmentVisibility,reconstruct,validated_path,geometry_profile
CASES=json.loads((Path(__file__).resolve().parents[1]/'examples/corner_investigation/minimal_fixture.json').read_text())['cases']

def data(case,rotation=None,shift=0.,scale=1.):
    rotation=np.eye(3) if rotation is None else rotation
    transform=lambda v:(np.asarray(v)*scale)@rotation.T+shift
    return transform(case['tx']),transform(case['rx']),transform(case['triangle_vertices'])

@pytest.mark.parametrize('case',CASES,ids=lambda c:c['name'])
@pytest.mark.parametrize('scale,shift',[(1.,0.),(.25,np.array([-8,13,4.])),(100.,np.array([1e5,-1e5,3e4]))])
def test_specular_geometry_under_rotation_scale_translation(case,scale,shift):
    axis=np.array([.3,.5,.7]);axis/=np.linalg.norm(axis);angle=.63
    cross=np.array([[0,-axis[2],axis[1]],[axis[2],0,-axis[0]],[-axis[1],axis[0],0]])
    rotation=np.eye(3)*np.cos(angle)+(1-np.cos(angle))*np.outer(axis,axis)+np.sin(angle)*cross
    tx,rx,tri=data(case,rotation,shift,scale)
    vertices,reason=validated_path(tx,rx,[0,1],SegmentVisibility(tri))
    assert reason is None and vertices.dtype==np.float64
    for i,t in enumerate(tri):
        n=np.cross(t[1]-t[0],t[2]-t[0]);n/=np.linalg.norm(n)
        a=vertices[i+1]-vertices[i];a/=np.linalg.norm(a)
        b=vertices[i+2]-vertices[i+1];b/=np.linalg.norm(b)
        assert np.linalg.norm(b-(a-2*np.dot(a,n)*n))<1e-9

def blocker(start,end,distance,offset=0.):
    d=end-start;d/=np.linalg.norm(d);basis=np.eye(3)[np.argmin(abs(d))]
    u=np.cross(d,basis);u/=np.linalg.norm(u);v=np.cross(d,u);center=start+d*distance+offset*u
    return np.array([center+.002*(u+v),center+.002*(-u+v),center-.004*v])

@pytest.mark.parametrize('case',CASES,ids=lambda c:c['name'])
@pytest.mark.parametrize('segment',[0,1,2])
@pytest.mark.parametrize('from_end',[False,True])
@pytest.mark.parametrize('distance',[1e-6,1e-5,1e-4])
@pytest.mark.parametrize('dtype',[np.float32,np.float64])
def test_real_obstacle_near_every_endpoint(case,segment,from_end,distance,dtype):
    tx,rx,tri=data(case);vertices=reconstruct(tx,rx,tri);start,end=vertices[segment:segment+2].copy()
    if from_end:start,end=end,start
    obstacle=blocker(start,end,distance)
    check=SegmentVisibility(np.concatenate([tri,obstacle[None]]).astype(dtype))
    points,reason=validated_path(tx,rx,[0,1],check)
    assert points is None and reason=='obstacle'

@pytest.mark.parametrize('case',CASES,ids=lambda c:c['name'])
def test_midpoint_blocker_near_miss_and_minimum_length(case):
    tx,rx,tri=data(case);vertices=reconstruct(tx,rx,tri);start,end=vertices[1:3].copy();half=np.linalg.norm(end-start)/2
    for offset,blocked in [(0.,True),(.02,False)]:
        check=SegmentVisibility(np.concatenate([tri,blocker(start,end,half,offset)[None]]))
        points,reason=validated_path(tx,rx,[0,1],check)
        assert (reason=='obstacle')==blocked
    minimum=np.min(np.linalg.norm(np.diff(vertices,axis=0),axis=-1))
    assert validated_path(tx,rx,[0,1],SegmentVisibility(tri),minimum*1.01)[1]=='segment_length'
    assert validated_path(tx,rx,[0,1],SegmentVisibility(tri),minimum*.99)[1] is None

def test_coplanar_obstacle_and_invalid_endpoint_exemption():
    tri=np.array([[[0,-1,-1],[0,1,-1],[0,0,1.]]]);check=SegmentVisibility(tri)
    assert check.blocked([-1,0,0],[1,0,0],start_face=0)
    assert check.blocked([0,-2,0],[0,2,0])
    assert not check.blocked([1,-2,0],[1,2,0])
    assert not SegmentVisibility(tri,active=[False]).blocked([-1,0,0],[1,0,0])

def test_outside_triangle_and_degenerate_geometry_rejected():
    tri=np.array([[[0,-1,-1],[0,1,-1],[0,0,1.]]])
    assert reconstruct([1,10,0],[1,12,0],tri) is None
    assert reconstruct([1,0,0],[1,1,0],np.zeros((1,3,3))) is None

def test_profile_is_explicit_and_invalid_modes_rejected(monkeypatch):
    monkeypatch.delenv('SIONNA_GEOMETRY_PROFILE',raising=False);assert geometry_profile()=='native'
    monkeypatch.setenv('SIONNA_GEOMETRY_PROFILE','unshifted_float64');assert geometry_profile()=='unshifted_float64'
    monkeypatch.setenv('SIONNA_GEOMETRY_PROFILE','unknown')
    with pytest.raises(ValueError):geometry_profile()

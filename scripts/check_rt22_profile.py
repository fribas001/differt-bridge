"""Runtime invariants and actual 1 mm solver boundaries for research profiles."""
import argparse,json,os
from pathlib import Path
import numpy as np
import rt22_profiles as profiles

def main():
    p=argparse.ArgumentParser();p.add_argument('--profile',choices=('phase','reciprocal'),required=True)
    p.add_argument('--scene',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();import sionna.rt as rt
    before=rt.PathSolver.__call__;detail=profiles.install(a.profile)
    assert rt.PathSolver.__call__ is before # worker already installed once
    try:profiles.install('reciprocal' if a.profile=='phase' else 'phase')
    except RuntimeError:pass
    else:raise AssertionError('Profile switch accepted in a live process')
    original=profiles.sha
    try:
        profiles.sha=lambda path:'invalid'
        try:profiles.verify()
        except RuntimeError:pass
        else:raise AssertionError('Unverified source accepted')
    finally:profiles.sha=original
    runs=[]
    if a.profile=='phase':
        from rt22_profiles._bridge_geometry import SegmentVisibility,validated_path
        fixture=Path(__file__).resolve().parents[1]/'examples/corner_investigation/minimal_fixture.json'
        blocked_checks=0
        for case in json.loads(fixture.read_text())['cases']:
            tri=np.array(case['triangle_vertices']);tx=np.array(case['tx']);rx=np.array(case['rx'])
            points,reason=validated_path(tx,rx,[0,1],SegmentVisibility(tri),.001,inclusive=True)
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
                            mesh=np.concatenate([tri,obstacle[None]]).astype(dtype)
                            assert validated_path(tx,rx,[0,1],SegmentVisibility(mesh),.001,inclusive=True)[1]=='obstacle'
                            blocked_checks+=1
        edge=np.float32(.001)
        lengths=np.array([.0009,np.nextafter(edge,np.float32(0)),edge,np.nextafter(edge,np.float32(np.inf)),.00105,.00603,.01,.012],np.float32)
        for deterministic in (True,False):
            scene=rt.load_scene(str(a.scene.resolve()),merge_shapes=True);scene.frequency=3.5e9
            scene.tx_array=rt.PlanarArray(num_rows=1,num_cols=1,pattern='iso',polarization='V')
            scene.rx_array=rt.PlanarArray(num_rows=1,num_cols=1,pattern='iso',polarization='V')
            scene.add(rt.Transmitter('test_tx',[0.,-10.,1.]))
            for i,length in enumerate(lengths):scene.add(rt.Receiver('test_rx_'+str(i),[float(length),-10.,1.]))
            solver=rt.PathSolver(deterministic=deterministic)
            paths=solver(scene,max_depth=0,samples_per_src=64,max_num_paths_per_src=64,
                         los=True,specular_reflection=False,diffuse_reflection=False,refraction=False,diffraction=False)
            valid=np.asarray(paths.valid).reshape(len(lengths),-1).any(axis=1)
            assert np.array_equal(valid,lengths.astype(float)>=.001)
            runs.append(dict(deterministic=deterministic,lengths_m=lengths.astype(float).tolist(),accepted=valid.tolist()))
            try:solver(scene,max_depth=1,diffraction=True)
            except ValueError:pass
            else:raise AssertionError('Phase profile silently accepted diffraction')
        detail=dict(detail,obstacle_rejections=blocked_checks,valid_corner_cases=2,runs=runs)
    else:
        from sionna.rt.path_solvers.image_method import ImageMethod
        try:ImageMethod.__call__(None,src_boxes=object())
        except ValueError:pass
        else:raise AssertionError('Unvalidated source exclusion boxes accepted')
    profiles.verify()
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(dict(passed=True,profile=a.profile,detail=detail,idempotence=True,
                                      source_guard_rejection=True,cross_profile_rejected=True),indent=2))
    print('PROFILE_CHECK_PASS',a.profile)

if __name__=='__main__':main()

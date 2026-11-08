"""NumPy-only stationary-chain and full-mesh visibility adapter.

Geometry helpers derive from the bridge validated_diffraction.py implementation.
No DiffeRT/JAX dependency: usable in the separate Sionna runtime. Native accepted
mixed candidates only; no sampling expansion or obstacle-exclusion radius.
"""
import numpy as np
from scipy.optimize import minimize

EPS=np.finfo(float).eps
LAW_TOL=1e-8
MIN_SEGMENT=np.sqrt(10*np.finfo(np.float32).eps)


def _basis(normal):
    axis=np.eye(3)[np.argmin(abs(normal))]
    u=np.cross(normal,axis);u/=np.linalg.norm(u)
    return np.stack([u,np.cross(normal,u)],axis=1)


def _single_edge(a,b,o,e):
    za=(a-o)@e;zb=(b-o)@e
    ra=np.linalg.norm(a-o-za*e);rb=np.linalg.norm(b-o-zb*e)
    if ra+rb==0:return None
    return o+((rb*za+ra*zb)/(ra+rb))*e


def _solve(tx,rx,supports):
    if len(supports)==1 and supports[0]['kind']==8:
        s=supports[0];point=_single_edge(tx,rx,s['origin'],s['basis'][:,0])
        return None if point is None else np.array([tx,point,rx])
    center=(tx+rx)/2;scale=max(np.linalg.norm(rx-tx),1e-6)
    a=(tx-center)/scale;b=(rx-center)/scale
    origins=[];bases=[];offsets=[0]
    for s in supports:
        basis=s['basis'];origin=s['origin']+basis@(basis.T@(center-s['origin']))
        origins.append((origin-center)/scale);bases.append(basis);offsets.append(offsets[-1]+basis.shape[1])
    def unpack(x):return np.array([a,*[o+v@x[offsets[i]:offsets[i+1]] for i,(o,v) in enumerate(zip(origins,bases))],b])
    def objective(x):
        p=unpack(x);d=np.diff(p,axis=0);length=np.linalg.norm(d,axis=1)
        unit=d/np.maximum(length[:,None],1e-16)
        gradient=unit[:-1]-unit[1:]
        return length.sum(),np.concatenate([v.T@g for v,g in zip(bases,gradient)])
    result=minimize(objective,np.zeros(offsets[-1]),jac=True,method='BFGS',options={'gtol':1e-11,'maxiter':400})
    points=unpack(result.x)*scale+center
    # Solver status alone is not an acceptance test. Physical residuals below
    # decide validity, including near-degenerate minima and failed searches.
    return points


def _inside(point,triangle):
    a,b,c=triangle;u=b-a;v=c-a;w=point-a
    uu=u@u;uv=u@v;vv=v@v;den=uu*vv-uv*uv
    if den<=0:return False
    x=((w@u)*vv-(w@v)*uv)/den;y=((w@v)*uu-(w@u)*uv)/den
    return x>=-128*EPS and y>=-128*EPS and x+y<=1+128*EPS


def _valid_laws(points,supports,minimum=.01):
    if not np.isfinite(points).all():return False
    delta=np.diff(points,axis=0);length=np.linalg.norm(delta,axis=1)
    if np.any(length<=minimum):return False
    unit=delta/length[:,None]
    for i,s in enumerate(supports):
        point=points[i+1]
        if s['kind']==8:
            e=s['basis'][:,0];z=(point-s['origin'])@e
            bound=128*EPS*max(1.,np.max(abs(point)),s['length'])
            if z < -bound or z>s['length']+bound:return False
            if abs((unit[i]-unit[i+1])@e)>LAW_TOL:return False
        else:
            n=s['normal']
            if not any(_inside(point,t) for t in s['triangles']):return False
            if np.linalg.norm(unit[i+1]-(unit[i]-2*(unit[i]@n)*n))>LAW_TOL:return False
    return True


def _coplanar_interval(start,end,triangle,normal):
    keep=np.arange(3)!=np.argmax(abs(normal));tri=triangle[:,keep];p=start[keep];d=(end-start)[keep]
    cross=lambda a,b:a[0]*b[1]-a[1]*b[0]
    sign=np.sign(cross(tri[1]-tri[0],tri[2]-tri[0]));lo=0.;hi=1.
    for i in range(3):
        edge=tri[(i+1)%3]-tri[i];c=sign*cross(edge,p-tri[i]);s=sign*cross(edge,d)
        if s==0:
            if c<0:return None
        elif s>0:lo=max(lo,-c/s)
        else:hi=min(hi,-c/s)
    return (lo,hi) if lo<=hi else None


def _blocked(visibility,start,end,start_faces,end_faces):
    """No physical endpoint gap; only known endpoint planes can be contacts."""
    direction=end-start;length=np.linalg.norm(direction);visibility.segments_checked+=1
    ids=visibility._query(start,direction)
    contact={}
    for endpoint,faces in ((0,start_faces),(1,end_faces)):
        point=start if endpoint==0 else end
        for face in faces:
            n=visibility.normals[face]/visibility.norm[face]
            bound=visibility.error[face]+32*EPS*max(1.,np.max(abs(point)))
            if abs((point-visibility.a[face])@n)>bound:continue
            dist=np.max(abs((visibility.triangles-visibility.a[face])@n),axis=1)
            same=dist<=visibility.error+visibility.error[face]
            for j in ids[same[ids]]:contact.setdefault(int(j),set()).add(endpoint)
    for face in ids:
        tri=visibility.triangles[face];e1=visibility.e1[face];e2=visibility.e2[face]
        normal=visibility.normals[face]/visibility.norm[face]
        h=np.cross(direction,e2);det=e1@h
        if abs(det)>64*EPS*np.linalg.norm(e1)*np.linalg.norm(e2)*length:
            q=np.cross(start-tri[0],e1);u=(start-tri[0])@h/det;v=direction@q/det;t=e2@q/det
            if u>=-64*EPS and v>=-64*EPS and u+v<=1+64*EPS and -64*EPS<=t<=1+64*EPS:
                # An affine segment crosses a nonparallel endpoint plane once.
                if face not in contact:return True
        elif min(abs((start-tri[0])@normal),abs((end-tri[0])@normal))<=visibility.error[face]:
            interval=_coplanar_interval(start,end,tri,normal)
            if interval is not None:
                lo,hi=interval
                if face in contact and ((hi<=64*EPS and 0 in contact[face]) or (lo>=1-64*EPS and 1 in contact[face])):continue
                return True
    return False


def repair_mixed(scene,paths,src_positions,tgt_positions,selected):
    """Reconstruct supported native-accepted R/D chains and reject obstructions."""
    import mitsuba as mi,drjit as dr
    from sionna.rt.path_solvers._bridge_geometry import SegmentVisibility
    from sionna.rt.constants import MIN_SEGMENT_LENGTH
    triangles=[]
    for mesh in scene.shapes():
        if not isinstance(mesh,mi.Mesh):raise ValueError('Triangular meshes required')
        f=mesh.face_indices(dr.arange(mi.UInt,mesh.face_count()))
        triangles.extend(np.stack([np.asarray(mesh.vertex_position(x)).T for x in (f.x,f.y,f.z)],axis=1))
    triangles=np.asarray(triangles,float);visibility=SegmentVisibility(triangles)
    lookup={tuple(t.reshape(-1)):i for i,t in enumerate(triangles)}
    valid=np.asarray(paths.valid).copy();mask=selected&valid
    src=np.asarray(paths.source_indices);tgt=np.asarray(paths.target_indices)
    sources=np.asarray(src_positions).T;targets=np.asarray(tgt_positions).T
    vertices=[];flags=[];faceids=[]
    for depth in range(1,paths.max_depth+1):
        kind=np.asarray(paths.get_interaction_type(depth,True));flags.append(kind)
        active=mi.Bool(mask&(kind!=0))
        vertices.append(np.asarray(paths.get_vertex(depth,True)).T.copy())
        props=paths.get_primitive_props(depth,False,True,mi.Bool(mask&(kind==1)))
        tris=np.stack([np.asarray(p).T for p in props],axis=1)
        ids=np.full(len(valid),-1,int)
        for i in np.flatnonzero(mask&(kind==1)):ids[i]=lookup[tuple(tris[i].reshape(-1))]
        faceids.append(ids)
    w=paths.diffracting_wedges
    origins=np.asarray(w.o).T;directions=np.asarray(w.e_hat).T;lengths=np.asarray(w.length)
    wf=w.shape.face_indices(w.prim0)
    wedge_triangles=np.stack([np.asarray(w.shape.vertex_position(x)).T for x in (wf.x,wf.y,wf.z)],axis=1)
    first=np.asarray(paths.k_tx).T.copy();last=np.asarray(paths.k_rx).T.copy()
    for i in np.flatnonzero(mask):
        supports=[]
        for depth,kind in enumerate(flags):
            if kind[i]==0:continue
            if kind[i]==8:
                approx_p=origins[i].astype(float);approx_q=approx_p+directions[i]*lengths[i]
                tri=wedge_triangles[i].astype(float)
                p=tri[np.argmin(np.linalg.norm(tri-approx_p,axis=1))]
                q=tri[np.argmin(np.linalg.norm(tri-approx_q,axis=1))]
                bound=16*np.finfo(np.float32).eps*max(1.,np.max(abs(tri)))
                if max(np.linalg.norm(p-approx_p),np.linalg.norm(q-approx_q))>bound or np.array_equal(p,q):
                    raise ValueError('Cannot identify the native edge endpoints')
                vector=q-p;length=np.linalg.norm(vector)
                has_p=np.any(np.all(triangles==p,axis=-1),axis=1)
                has_q=np.any(np.all(triangles==q,axis=-1),axis=1)
                faces=np.flatnonzero(has_p&has_q)
                if not len(faces):raise ValueError('Unsupported rounded edge identity')
                supports.append(dict(kind=8,origin=p,basis=(vector/length)[:,None],length=float(length),faces=faces))
            elif kind[i]==1:
                face=faceids[depth][i];n=visibility.normals[face]/visibility.norm[face]
                supports.append(dict(kind=1,origin=triangles[face,0],basis=_basis(n),normal=n,triangles=triangles[[face]],faces=[face]))
            else:raise ValueError('Unsupported mixed interaction')
        points=_solve(sources[src[i]],targets[tgt[i]],supports)
        if points is None or not _valid_laws(points,supports,float(MIN_SEGMENT_LENGTH)):
            valid[i]=False;continue
        endpoints=[[],*[s['faces'] for s in supports],[]]
        if any(_blocked(visibility,a,b,endpoints[j],endpoints[j+1]) for j,(a,b) in enumerate(zip(points[:-1],points[1:]))):
            valid[i]=False;continue
        rounded=points.astype(np.float32)
        for d in range(len(supports)):vertices[d][i]=rounded[d+1]
        first[i]=rounded[1]-sources[src[i]];last[i]=rounded[-2]-targets[tgt[i]]
    paths.valid=mi.Bool(valid)
    for depth,v in enumerate(vertices,1):
        paths.set_vertex(depth,mi.Point3f(v.T.copy()),mi.Bool(mask&valid&(flags[depth-1]!=0)))
    paths.set_k_tx(dr.normalize(mi.Vector3f(first.T.copy())),mi.Bool(mask&valid))
    paths.set_k_rx(dr.normalize(mi.Vector3f(last.T.copy())),mi.Bool(mask&valid))
    paths.schedule();dr.eval()
    return paths



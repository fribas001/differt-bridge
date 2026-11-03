"""Bridge-level diffraction geometry; native discovery and EM remain in DiffeRT.

Only reflection/diffraction chains are handled here. Single edges use the exact
stationary point. Mixed chains minimize path length in centered, normalized
float64 coordinates. Every accepted path must satisfy its interaction laws,
finite surfaces, physical segment limit and visibility against the full mesh.
This CPU adapter does not expose geometry derivatives through NumPy/SciPy.
"""
import numpy as np
import jax.numpy as jnp
from scipy.optimize import minimize
from differt.geometry import TracedPaths
from differt.em import InteractionType as I

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
    if len(supports)==1 and supports[0]['kind']==I.DIFFRACTION:
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


def _valid_laws(points,supports):
    if not np.isfinite(points).all():return False
    delta=np.diff(points,axis=0);length=np.linalg.norm(delta,axis=1)
    if np.any(length<MIN_SEGMENT):return False
    unit=delta/length[:,None]
    for i,s in enumerate(supports):
        point=points[i+1]
        if s['kind']==I.DIFFRACTION:
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


def trace_validated(scene,candidates,kinds,visibility):
    """Keep native half-edge IDs so the original UTD field model is used."""
    mesh=scene.mesh;cs=np.asarray(candidates);ks=np.asarray(kinds);txs=np.asarray(scene.transmitters,dtype=float);rxs=np.asarray(scene.receivers,dtype=float)
    triangles=visibility.triangles;edges=np.asarray(mesh.triangle_edges,dtype=float).reshape(-1,2,3)
    order=cs.shape[1];shape=(len(txs),len(rxs),len(cs));vertices=np.zeros((*shape,order+2,3));mask=np.zeros(shape,bool)
    objects=np.empty((*shape,order+2),np.int32);objects[...,1:-1]=cs
    objects[...,0]=np.arange(len(txs))[:,None,None];objects[...,-1]=np.arange(len(rxs))[None,:,None]
    types=np.broadcast_to(ks,(*shape,order)).copy()
    stats=getattr(visibility,'diffraction_stats',dict(candidates=0,accepted=0,rejected_laws=0,rejected_visibility=0))
    visibility.diffraction_stats=stats
    cache=getattr(visibility,'diffraction_geometry_cache',{})
    visibility.diffraction_geometry_cache=cache
    for ci,(candidate,types_row) in enumerate(zip(cs,ks)):
        stats['candidates']+=len(txs)*len(rxs)
        active=np.flatnonzero(candidate>=0);supports=[]
        for slot in active:
            obj=int(candidate[slot]);kind=types_row[slot]
            if kind==I.DIFFRACTION:
                p,q=edges[obj];vec=q-p;length=np.linalg.norm(vec)
                if length==0:break
                # Include all triangles sharing this actual geometric edge,
                # irrespective of triangulation or duplicate vertex indexing.
                has_p=np.any(np.all(triangles==p,axis=-1),axis=1);has_q=np.any(np.all(triangles==q,axis=-1),axis=1)
                supports.append(dict(kind=kind,origin=p,basis=(vec/length)[:,None],length=length,faces=np.flatnonzero(has_p&has_q)))
            else:
                faces=[obj,obj+1] if mesh.assume_quads else [obj];n=visibility.normals[obj]/visibility.norm[obj]
                supports.append(dict(kind=kind,origin=triangles[obj,0],basis=_basis(n),normal=n,triangles=triangles[faces],faces=faces))
        if len(supports)!=len(active):stats['rejected_laws']+=len(txs)*len(rxs);continue
        keys=[]
        for s in supports:
            if s['kind']==I.DIFFRACTION:
                ends=[tuple(s['origin']),tuple(s['origin']+s['basis'][:,0]*s['length'])]
                keys.append(('edge',*sorted(ends)))
            else:
                n=s['normal'].copy()
                if n[np.argmax(abs(n))]<0:n=-n
                keys.append(('plane',*n,float(n@s['origin'])))
        if any(a==b for a,b in zip(keys[:-1],keys[1:])):
            stats['rejected_laws']+=len(txs)*len(rxs);continue
        for ti,tx in enumerate(txs):
            for ri,rx in enumerate(rxs):
                index=(ti,ri,ci)
                key=(tuple(tx),tuple(rx),tuple(keys))
                if len(cache)>=8192:cache.clear()
                if key not in cache:cache[key]=_solve(tx,rx,supports)
                points=cache[key]
                if points is None or not _valid_laws(points,supports):stats['rejected_laws']+=1;continue
                endpoints=[[],*[s['faces'] for s in supports],[]]
                if any(_blocked(visibility,a,b,endpoints[j],endpoints[j+1]) for j,(a,b) in enumerate(zip(points[:-1],points[1:]))):
                    stats['rejected_visibility']+=1;continue
                full=np.tile(rx,(order+2,1));full[0]=tx;full[active+1]=points[1:-1]
                vertices[index]=full;mask[index]=True;stats['accepted']+=1
    return TracedPaths(jnp.asarray(vertices),jnp.asarray(objects),mask=jnp.asarray(mask),interaction_types=jnp.asarray(types))

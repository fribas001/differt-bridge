"""Opt-in unshifted specular reconstruction before native Sionna EM fields.

Native candidate generation and its acceptance mask are preserved. Reflection
vertices are independently reconstructed from native hit triangles in float64,
and every unshifted segment is checked against every active mesh via a BVH.
No ray offsets or world-space endpoint tolerances are used in this validation.
Only then are vertices rounded to Sionna's native float32 path buffer.
CPU LoS/specular only; geometry is detached, field/material differentiation is
left to the original field calculator. Default mode is native.
"""
import os
import numpy as np
try:
    from ._bridge_segment_policy import segment_profile,SHARED_PROFILE,MINIMUM_M,segments_at_least
except ImportError:
    from _bridge_segment_policy import segment_profile,SHARED_PROFILE,MINIMUM_M,segments_at_least

PROFILE='unshifted_float64'
last_diagnostics={}

def geometry_profile():
    value=os.environ.get('SIONNA_GEOMETRY_PROFILE','native')
    if value not in ('native',PROFILE):raise ValueError('Unknown SIONNA_GEOMETRY_PROFILE: '+value)
    return value

class SegmentVisibility:
    def __init__(self,triangles,active=None):
        self.triangles=np.asarray(triangles,dtype=np.float64)
        self.a=self.triangles[:,0]
        self.e1=self.triangles[:,1]-self.a;self.e2=self.triangles[:,2]-self.a
        self.normals=np.cross(self.e1,self.e2);self.norm=np.linalg.norm(self.normals,axis=1)
        self.scale=np.maximum(1.,np.max(np.abs(self.triangles),axis=(1,2)))
        self.error=32*np.finfo(np.float64).eps*self.scale
        self.low=self.triangles.min(axis=1)-self.error[:,None]
        self.high=self.triangles.max(axis=1)+self.error[:,None]
        active=np.ones(len(self.triangles),bool) if active is None else np.asarray(active,bool)
        ids=np.flatnonzero(active & (self.norm>0));self.nodes=[]
        self.root=self._build(ids) if len(ids) else -1
        self._planes={};self.segments_checked=0

    def _build(self,ids):
        lo=self.low[ids].min(axis=0);hi=self.high[ids].max(axis=0)
        node=len(self.nodes);self.nodes.append(None)
        if len(ids)<=16:self.nodes[node]=(lo,hi,ids,None)
        else:
            axis=int(np.argmax(hi-lo));ids=ids[np.argsort((self.low[ids,axis]+self.high[ids,axis])/2)]
            middle=len(ids)//2
            self.nodes[node]=(lo,hi,None,(self._build(ids[:middle]),self._build(ids[middle:])))
        return node

    @staticmethod
    def _box(origin,direction,low,high):
        moving=direction!=0
        if np.any(~moving & ((origin<low)|(origin>high))):return False
        a=(low[moving]-origin[moving])/direction[moving]
        b=(high[moving]-origin[moving])/direction[moving]
        return max(0.,float(np.min([a,b],axis=0).max(initial=-np.inf))) <= min(1.,float(np.max([a,b],axis=0).min(initial=np.inf)))

    def _query(self,start,direction):
        found=[];stack=[self.root] if self.root>=0 else []
        while stack:
            lo,hi,ids,children=self.nodes[stack.pop()]
            if not self._box(start,direction,lo,hi):continue
            if ids is not None:found.extend(ids.tolist())
            else:stack.extend(children)
        return np.asarray(found,dtype=np.int64)

    def _endpoint_plane(self,face,point,direction):
        if face<0:return None
        n=self.normals[face]/self.norm[face]
        # A wrong endpoint association must never exempt a real obstacle.
        bound=self.error[face]+32*np.finfo(float).eps*max(1.,np.max(abs(point)))
        if abs(np.dot(point-self.a[face],n))>bound:return None
        if abs(np.dot(direction,n))<=32*np.finfo(float).eps*np.linalg.norm(direction):return None
        if face not in self._planes:
            distance=np.max(np.abs((self.triangles-self.a[face])@n),axis=1)
            self._planes[face]=distance <= (self.error+self.error[face])
        return self._planes[face]

    def _coplanar_overlap(self,start,end,face):
        # Clip the segment against the triangle in its dominant 2D projection.
        keep=np.arange(3)!=int(np.argmax(abs(self.normals[face])))
        tri=self.triangles[face][:,keep];p=start[keep];d=(end-start)[keep]
        cross=lambda a,b:a[0]*b[1]-a[1]*b[0]
        sign=np.sign(cross(tri[1]-tri[0],tri[2]-tri[0]))
        lo,hi=0.,1.
        for i in range(3):
            a=tri[i];edge=tri[(i+1)%3]-a
            c=sign*cross(edge,p-a);s=sign*cross(edge,d)
            tolerance=self.error[face]*max(1.,np.linalg.norm(edge))
            if s==0:
                if c < -tolerance:return False
            elif s>0:lo=max(lo,(-tolerance-c)/s)
            else:hi=min(hi,(-tolerance-c)/s)
        return lo<=hi

    def blocked(self,start,end,start_face=-1,end_face=-1):
        start=np.asarray(start,dtype=np.float64);end=np.asarray(end,dtype=np.float64)
        direction=end-start;self.segments_checked+=1
        if not np.isfinite([start,end]).all() or np.linalg.norm(direction)==0:return True
        ids=self._query(start,direction)
        for face,point in ((start_face,start),(end_face,end)):
            plane=self._endpoint_plane(int(face),point,direction)
            if plane is not None:ids=ids[~plane[ids]]
        if not len(ids):return False
        e1,e2=self.e1[ids],self.e2[ids]
        h=np.cross(direction,e2);det=np.einsum('ij,ij->i',e1,h)
        nonparallel=det!=0
        s=start-self.a[ids];q=np.cross(s,e1)
        with np.errstate(divide='ignore',invalid='ignore'):
            u=np.einsum('ij,ij->i',s,h)/det
            v=np.einsum('j,ij->i',direction,q)/det
            t=np.einsum('ij,ij->i',e2,q)/det
        # Enlarge uncertain contacts, never carve away a segment endpoint.
        rounding=64*np.finfo(float).eps
        hit=nonparallel & (u>=-rounding) & (v>=-rounding) & (u+v<=1+rounding) & (t>=-rounding) & (t<=1+rounding)
        if np.any(hit):return True
        # Parallel/coplanar rays cannot use Moller-Trumbore. Conservatively
        # test projected overlap when the plane separation is within roundoff.
        near_parallel=abs(det)<=rounding*np.linalg.norm(e1,axis=1)*np.linalg.norm(e2,axis=1)*np.linalg.norm(direction)
        for face in ids[near_parallel]:
            n=self.normals[face]/self.norm[face]
            if min(abs(np.dot(start-self.a[face],n)),abs(np.dot(end-self.a[face],n)))<=self.error[face]:
                if self._coplanar_overlap(start,end,int(face)):return True
        return False


def reconstruct(tx,rx,triangles):
    """Solve stationary specular geometry without displaced origins or targets."""
    tx=np.asarray(tx,np.float64);rx=np.asarray(rx,np.float64)
    planes=[];images=[tx]
    for tri in np.asarray(triangles,np.float64):
        a,b,c=tri;n=np.cross(b-a,c-a);length=np.linalg.norm(n)
        if length==0:return None
        n=n/length;planes.append((a,n))
        images.append(images[-1]-2*np.dot(images[-1]-a,n)*n)
    current=rx;points=[rx]
    for i in reversed(range(len(planes))):
        a,n=planes[i];direction=images[i+1]-current;den=np.dot(direction,n)
        if abs(den)<=64*np.finfo(float).eps*np.linalg.norm(direction):return None
        fraction=np.dot(a-current,n)/den
        if not (0<fraction<1):return None
        current=current+fraction*direction;points.insert(0,current)
    vertices=np.vstack([tx,*points])
    if not np.isfinite(vertices).all():return None
    # Reject hits outside the native reflecting triangles; no geometric slack.
    for p,tri,(a,n) in zip(vertices[1:-1],triangles,planes):
        edge=np.stack([tri[1]-a,tri[2]-a],axis=-1)
        uv=np.linalg.lstsq(edge,p-a,rcond=None)[0]
        bound=128*np.finfo(float).eps*max(1.,np.linalg.cond(edge))
        if min(uv)<-bound or sum(uv)>1+bound:return None
    # Verify reflection law and same-side reflections independently of images.
    for i,(a,n) in enumerate(planes):
        incoming=vertices[i+1]-vertices[i];outgoing=vertices[i+2]-vertices[i+1]
        li,lo=np.linalg.norm(incoming),np.linalg.norm(outgoing)
        if min(li,lo)==0:return None
        ki,ko=incoming/li,outgoing/lo
        if np.dot(ki,n)*np.dot(ko,n)>=0:return None
        if np.linalg.norm(ko-(ki-2*np.dot(ki,n)*n))>1e-9:return None
    return vertices

def validated_path(tx,rx,faces,visibility,min_length=0.,inclusive=False):
    points=reconstruct(tx,rx,visibility.triangles[faces])
    if points is None:return None,'geometry'
    if inclusive:
        if not segments_at_least(points,min_length):return None,'segment_length'
    elif np.any(np.linalg.norm(np.diff(points,axis=0),axis=-1)<=min_length):return None,'segment_length'
    endpoints=[-1,*faces,-1]
    for i in range(len(points)-1):
        if visibility.blocked(points[i],points[i+1],endpoints[i],endpoints[i+1]):return None,'obstacle'
    return points,None

def repair_paths(scene,paths,src_positions,tgt_positions):
    """Repair accepted native LoS/specular paths; never accept an occluded route."""
    import mitsuba as mi
    import drjit as dr
    from sionna.rt.constants import MIN_SEGMENT_LENGTH
    global last_diagnostics
    if not mi.variant().startswith('llvm'):raise ValueError('Unshifted geometry profile is validated on the LLVM CPU backend only')
    triangles=[]
    for mesh in scene.shapes():
        if not isinstance(mesh,mi.Mesh):raise ValueError('Unshifted geometry profile requires triangular meshes')
        faces=mesh.face_indices(dr.arange(mi.UInt,mesh.face_count()))
        triangles.extend(np.stack([np.asarray(mesh.vertex_position(x)).T for x in (faces.x,faces.y,faces.z)],axis=1))
    triangles=np.asarray(triangles,np.float64)
    if len(triangles)==0:raise ValueError('No mesh triangles for unshifted visibility')
    key=lambda tri:tuple(np.asarray(tri).reshape(-1))
    lookup={key(tri):i for i,tri in enumerate(triangles)}
    visibility=SegmentVisibility(triangles)
    valid=np.asarray(paths.valid).copy();before=int(valid.sum());size=len(valid)
    sources=np.asarray(src_positions).T;targets=np.asarray(tgt_positions).T
    src=np.asarray(paths.source_indices);tgt=np.asarray(paths.target_indices)
    flags=[];vertices=[];faceids=[]
    for depth in range(1,paths.max_depth+1):
        kind=np.asarray(paths.get_interaction_type(depth,True));flags.append(kind)
        active=paths.valid & mi.Bool(kind!=0)
        if np.any(valid & (kind!=0) & (kind!=1)):raise ValueError('Unshifted geometry profile supports only LoS/specular paths')
        vertices.append(np.asarray(paths.get_vertex(depth,active)).T.copy())
        props=paths.get_primitive_props(depth,False,True,active)
        tris=np.stack([np.asarray(p).T for p in props],axis=1)
        ids=np.full(size,-1,int)
        for i in np.flatnonzero(valid & (kind!=0)):ids[i]=lookup[key(tris[i])]
        faceids.append(ids)
    first=sources[src].copy();last=targets[tgt].copy();rejected={};maximum=0.;lawmax=0.
    for i in np.flatnonzero(valid):
        count=sum(k[i]!=0 for k in flags)
        if any(k[i]!=1 for k in flags[:count]):raise ValueError('Non-contiguous specular path')
        ids=[int(f[i]) for f in faceids[:count]]
        shared=segment_profile()==SHARED_PROFILE
        points,reason=validated_path(sources[src[i]],targets[tgt[i]],ids,visibility,MINIMUM_M if shared else float(MIN_SEGMENT_LENGTH),inclusive=shared)
        if reason:valid[i]=False;rejected[reason]=rejected.get(reason,0)+1;continue
        if count:
            old=np.array([v[i] for v in vertices[:count]])
            maximum=max(maximum,float(np.max(np.linalg.norm(old-points[1:-1],axis=-1))))
            rounded=points.astype(np.float32)
            for depth in range(count):vertices[depth][i]=rounded[depth+1]
            first[i]=rounded[1];last[i]=rounded[-2]
        else:first[i]=targets[tgt[i]];last[i]=sources[src[i]]
    paths.valid=mi.Bool(valid)
    for depth,v in enumerate(vertices,1):paths.set_vertex(depth,mi.Point3f(v.T.copy()),paths.valid & mi.Bool(flags[depth-1]!=0))
    paths.set_k_tx(dr.normalize(mi.Vector3f((first-sources[src]).T.copy())),paths.valid)
    paths.set_k_rx(dr.normalize(mi.Vector3f((last-targets[tgt]).T.copy())),paths.valid)
    paths.schedule();dr.eval()
    last_diagnostics=dict(profile=PROFILE,native_accepted=before,accepted=int(valid.sum()),rejected=rejected,
        segment_length_profile=segment_profile(),minimum_segment_length_m=MINIMUM_M if segment_profile()==SHARED_PROFILE else float(MIN_SEGMENT_LENGTH),
        minimum_segment_comparison='greater_than_or_equal' if segment_profile()==SHARED_PROFILE else 'strict_greater_than',
        max_vertex_correction_m=maximum,triangles=len(triangles),unshifted_segments_checked=visibility.segments_checked,
        scope='Native accepted candidates; unshifted float64 geometry checked against all mesh triangles before float32 field storage. Segment minimum and boundary are recorded separately.')
    return paths

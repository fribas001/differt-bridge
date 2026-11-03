"""Unshifted float64 visibility for DiffeRT's LoS/specular image-method paths.

Candidate discovery stays in DiffeRT. Its image method and geometric gates run
in float64, then every surviving segment is checked against the exported mesh.
Only the known endpoint reflection planes are exempted from self-intersection;
there is no length-relative ray offset or gap in front of another surface.
Reflection/diffraction chains also receive stationary-point refinement and full
mesh validation in validated_diffraction. Other mixed interactions retain the
native tracer; DIFFERT_DIFFRACTION_GEOMETRY=native restores native diffraction.
"""
from dataclasses import fields
import os
import numpy as np
import equinox as eqx
import jax.numpy as jnp
from differt.geometry import Mesh, Scene, ExhaustivePathTracer, HybridPathTracer, SBRPathTracer
from differt.em import InteractionType
from segment_policy import segment_profile,SHARED_PROFILE,segments_at_least


class _CandidateMesh(Mesh):
    """Internal geometry-only stage. Never expose its unvalidated path masks."""
    def ray_intersect_any_triangle(self, ray_origins, ray_directions, **kwargs):
        return jnp.zeros(ray_origins.shape[:-1], dtype=bool)


class SegmentVisibility:
    """CPU float64 segment/triangle checks with a bounded-memory BVH.

Numerically ambiguous edge contacts are treated as blocked. Endpoint plane
equivalence uses only float64 roundoff bounds, not a user/world-space tolerance.
This cannot restore detail already lost when geometry was exported to float32.
"""
    def __init__(self, mesh):
        self.triangles=np.asarray(mesh.triangle_vertices,dtype=np.float64)
        self.a=self.triangles[:,0]
        self.e1=self.triangles[:,1]-self.a;self.e2=self.triangles[:,2]-self.a
        self.normals=np.cross(self.e1,self.e2)
        self.norm=np.linalg.norm(self.normals,axis=1)
        self.scale=np.maximum(1.,np.max(np.abs(self.triangles),axis=(1,2)))
        self.error=32*np.finfo(np.float64).eps*self.scale
        self.low=self.triangles.min(axis=1)-self.error[:,None]
        self.high=self.triangles.max(axis=1)+self.error[:,None]
        active=np.ones(len(self.triangles),bool) if mesh.mask is None else np.asarray(mesh.mask,bool)
        ids=np.flatnonzero(active & (self.norm>0))
        self.nodes=[];self.root=self._build(ids) if len(ids) else -1
        self._planes={}
        values={f.name:getattr(mesh,f.name) for f in fields(mesh)}
        values['vertices']=mesh.vertices.astype(jnp.float64)
        self.precise_mesh=Mesh(**values)
        self.candidate_mesh=_CandidateMesh(**values)
        self.segments_checked=0

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

    def validate(self,paths):
        mask=np.array(paths.mask,dtype=bool,copy=True)
        vertices=np.asarray(paths.vertices,dtype=np.float64);objects=np.asarray(paths.objects)
        for index in zip(*np.where(mask)):
            points=vertices[index];faces=objects[index][1:-1]
            active=faces>=0
            if not active.all():
                points=points[np.r_[True,active,True]];faces=faces[active]
            endpoints=np.concatenate([[-1],faces,[-1]])
            if segment_profile()==SHARED_PROFILE and not segments_at_least(points):
                mask[index]=False;continue
            for i in range(len(points)-1):
                if self.blocked(points[i],points[i+1],endpoints[i],endpoints[i+1]):
                    mask[index]=False;break
        return eqx.tree_at(lambda p:p.mask,paths,jnp.asarray(mask))


def trace_specular(scene,order,method,kwargs,visibility,allowed=None):
    """Discover natively; correct specular candidates, including in mixed runs."""
    options=dict(kwargs);chunk=options.pop('chunk_size')
    tracer={'exhaustive':ExhaustivePathTracer,'hybrid':HybridPathTracer,'sbr':SBRPathTracer}[method](**options)
    allowed=allowed or frozenset({InteractionType.REFLECTION})
    precise=Scene(mesh=visibility.candidate_mesh,transmitters=scene.transmitters.astype(jnp.float64),
                  receivers=scene.receivers.astype(jnp.float64))
    # DiffeRT 0.12 compares min_len against squared lengths. In shared mode,
    # defer this gate to the common physical predicate on unshifted vertices.
    exact=ExhaustivePathTracer(min_len=0. if segment_profile()==SHARED_PROFILE else 10*np.finfo(np.float32).eps)
    for candidates,kinds in tracer.generate_path_candidates_chunks_iter(scene,order,allowed,chunk_size=chunk):
        specular=np.all((np.asarray(kinds)==InteractionType.REFLECTION)|(np.asarray(kinds)==InteractionType.NONE),axis=-1)
        if specular.any():
            paths=exact.trace_path_candidates(precise,candidates[specular],kinds[specular],frozenset({InteractionType.REFLECTION}))
            yield visibility.validate(paths)
        if not specular.all():
            cs=candidates[~specular];ks=kinds[~specular]
            validated=np.all(np.isin(np.asarray(ks),[InteractionType.REFLECTION,InteractionType.DIFFRACTION,InteractionType.NONE]),axis=-1)
            profile=os.environ.get('DIFFERT_DIFFRACTION_GEOMETRY','validated')
            if profile not in ('native','validated'):raise ValueError('Unknown diffraction geometry profile: '+profile)
            if profile=='native':validated[:]=False
            if validated.any():
                from validated_diffraction import trace_validated
                yield trace_validated(scene,cs[validated],ks[validated],visibility)
            if not validated.all():yield tracer.trace_path_candidates(scene,cs[~validated],ks[~validated],allowed)

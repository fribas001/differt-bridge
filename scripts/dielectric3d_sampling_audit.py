"""Audit field recovery without changing the independent FEM solution.

The cubic stencil is restricted to homogeneous vacuum away from the PML.
It is a diagnostic reconstruction, not a replacement Maxwell discretization.
"""
import numpy as np
from dielectric3d_fem import VectorWedgeFEM,K

def weights(t):
    nodes=np.arange(-1,3);values=[];derivatives=[]
    for j,node in enumerate(nodes):
        other=np.delete(nodes,j);den=np.prod(node-other)
        values.append(np.prod(t-other)/den)
        derivatives.append(sum(np.prod(t-np.delete(other,k)) for k in range(3))/den)
    return np.array(values),np.array(derivatives)

class SamplingAuditFEM(VectorWedgeFEM):
    def sample(self,u,receivers):
        original=super().sample(u,receivers)
        grid=np.zeros((self.nn*self.nn,u.shape[1]),complex);grid[self.ids>=0]=u;grid=grid.reshape(self.nn,self.nn,-1);values=[];grad=[]
        for r in receivers:
            p=(np.asarray(r)[:2]-self.x[0])/self.h;i=np.floor(p).astype(int);f=p-i
            ix=np.arange(i[0]-1,i[0]+3);iy=np.arange(i[1]-1,i[1]+3)
            assert ix.min()>=0 and iy.min()>=0 and ix.max()<self.nn and iy.max()<self.nn
            xx,yy=np.meshgrid(self.x[ix],self.x[iy],indexing='ij')
            assert max(abs(xx).max(),abs(yy).max())<self.metadata['inner']
            material=(xx>0)&(yy>0) if self.metadata['geometry']=='wedge' else xx>0 if self.metadata['geometry']=='halfspace' else np.zeros_like(xx,dtype=bool)
            assert not material.any(),'Cubic sampling requires homogeneous vacuum stencil'
            wx,dx=weights(f[0]);wy,dy=weights(f[1]);v=grid[ix[:,None],iy[None,:]]
            values.append(np.einsum('i,j,ijk->k',wx,wy,v))
            grad.append([np.einsum('i,j,ijk->k',dx/self.h,wy,v),np.einsum('i,j,ijk->k',wx,dy/self.h,v)])
        self.sample_records.append((np.asarray(values),np.asarray(grad)));return original
    def solve(self,q,*args,**kwargs):
        self.sample_records=[];field,metadata=super().solve(q,*args,**kwargs)
        (ez,ge),(_,gh)=self.sample_records;kap2=K*K-q*q
        et=1j*q/kap2*ge+1j*K/kap2*np.stack([-gh[:,1,:],gh[:,0,:]],axis=1)
        self.cubic_field=np.concatenate([et,ez[:,None,:]],axis=1)
        return field,metadata

"""Independent Q1 finite-element vector Maxwell reference in Fourier-z.

Two longitudinal fields E_z and Z0 H_z, with material-interface coupling:
div(eps/kappa^2 grad E)+eps E-(q/k) curl(1/kappa^2 grad H)=source
div(1/kappa^2 grad H)+H+(q/k) curl(1/kappa^2 grad E)=0.
Complex-coordinate PML, exact interface-aligned cells, analytic incident
fields, and a contrast/scattered-field RHS avoid a point-grid delta source.
This implementation uses no boundary-integral or UTD operator.
"""
import time
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import splu
from scipy.special import hankel2
K=2*np.pi

def incoming(points,source,q,axis):
    kap=np.sqrt(complex(K*K-q*q))
    if kap.imag>0:kap=-kap
    d=points-np.asarray(source)[:2];rho=np.sqrt(np.sum(d*d,axis=-1))
    # The source is in vacuum, outside every nonzero contrast element. Its
    # singular nodal value is unused; avoid 0*NaN in those zero RHS blocks.
    rho=np.where(abs(rho)<1e-12,1.,rho);g=-.25j*hankel2(0,kap*rho)
    grad=.25j*kap*hankel2(1,kap*rho)[...,None]*d/rho[...,None]
    if axis==2:return kap*kap/(K*K)*g,np.zeros_like(g)
    return 1j*q/(K*K)*grad[...,axis],1j/K*(grad[...,0] if axis==1 else -grad[...,1])

class VectorWedgeFEM:
    def __init__(self,ppw=16,inner=2.5,pml=1.5,strength=4.,geometry='wedge'):
        self.h=h=1/ppw;half=round((inner+pml)*ppw);self.x=np.arange(-half,half+1)*h;nn=len(self.x);self.nn=nn
        xc=(self.x[:-1]+self.x[1:])/2;xx,yy=np.meshgrid(xc,xc,indexing='ij')
        material=(xx>0)&(yy>0) if geometry=='wedge' else xx>0 if geometry=='halfspace' else np.zeros_like(xx,dtype=bool)
        self.material=material.ravel()
        stretch=lambda x:1-1j*strength*np.maximum((abs(x)-inner)/pml,0.)**3
        sx,sy=stretch(xx),stretch(yy);self.wx=(sy/sx).ravel();self.wy=(sx/sy).ravel();self.mass=(sx*sy).ravel()
        X=self.x-1j*np.sign(self.x)*strength*np.maximum(abs(self.x)-inner,0.)**4/(4*pml**3)
        X,Y=np.meshgrid(X,X,indexing='ij');self.points=np.stack([X.ravel(),Y.ravel()],axis=-1)
        node=np.arange(nn*nn).reshape(nn,nn);self.cells=np.stack([node[:-1,:-1],node[1:,:-1],node[1:,1:],node[:-1,1:]],axis=-1).reshape(-1,4)
        active=np.ones((nn,nn),bool);active[[0,-1],:]=False;active[:,[0,-1]]=False
        ids=np.full(nn*nn,-1,int);ids[active.ravel()]=np.arange(active.sum());self.ids=ids;self.n=int(active.sum())
        ids=ids[self.cells];self.rows=np.broadcast_to(ids[:,:,None],(len(ids),4,4)).ravel();self.cols=np.broadcast_to(ids[:,None,:],(len(ids),4,4)).ravel();self.valid=(self.rows>=0)&(self.cols>=0)
        self.row_cells=ids
        m=np.zeros((4,4));xx=np.zeros((4,4));yy=np.zeros((4,4));xy=np.zeros((4,4))
        for a in (-1/np.sqrt(3),1/np.sqrt(3)):
            for b in (-1/np.sqrt(3),1/np.sqrt(3)):
                N=np.array([(1-a)*(1-b),(1+a)*(1-b),(1+a)*(1+b),(1-a)*(1+b)])/4
                dx=np.array([-(1-b),1-b,1+b,-(1+b)])/2
                dy=np.array([-(1-a),-(1+a),1+a,1-a])/2
                m+=np.outer(N,N)/4;xx+=np.outer(dx,dx)/4;yy+=np.outer(dy,dy)/4
                xy+=(np.outer(dx,dy)-np.outer(dy,dx))/4
        self.M=m*h*h;self.XX=xx;self.YY=yy;self.XY=xy
        self.metadata=dict(method='coupled longitudinal vector Maxwell Q1 finite elements',ppw=ppw,inner=inner,pml=pml,strength=strength,geometry=geometry,unknowns=2*self.n)

    def blocks(self,q,epsilon):
        eps=np.where(self.material,epsilon,1.);kap2=K*K*eps-q*q;a=eps/kap2;b=1/kap2
        stiff=self.wx[:,None,None]*self.XX+self.wy[:,None,None]*self.YY
        E=-a[:,None,None]*stiff+(eps*self.mass)[:,None,None]*self.M
        H=-b[:,None,None]*stiff+self.mass[:,None,None]*self.M
        C=(q/K*b)[:,None,None]*self.XY
        return E,C,-C,H

    def sample(self,u,receivers):
        grid=np.zeros((self.nn*self.nn,u.shape[1]),complex);grid[self.ids>=0]=u;grid=grid.reshape(self.nn,self.nn,-1)
        dx,dy=np.gradient(grid,self.h,axis=(0,1),edge_order=2);values=[];grad=[]
        for r in receivers:
            p=(np.asarray(r)[:2]-self.x[0])/self.h;i=np.floor(p).astype(int);f=p-i
            values.append(sum(grid[i[0]+a,i[1]+b]*((f[0] if a else 1-f[0])*(f[1] if b else 1-f[1])) for a in (0,1) for b in (0,1)))
            grad.append([sum(g[i[0]+a,i[1]+b]*((f[0] if a else 1-f[0])*(f[1] if b else 1-f[1])) for a in (0,1) for b in (0,1)) for g in (dx,dy)])
        return np.asarray(values),np.asarray(grad)

    def solve(self,q,epsilon,sources,receivers,axes=(2,)):
        started=time.perf_counter();blocks=self.blocks(q,epsilon);vacuum=self.blocks(q,1.)
        data=[];row=[];col=[]
        for b,(i,j) in zip(blocks,[(0,0),(0,1),(1,0),(1,1)]):
            data.append(b.ravel()[self.valid]);row.append(self.rows[self.valid]+i*self.n);col.append(self.cols[self.valid]+j*self.n)
        A=coo_matrix((np.concatenate(data),(np.concatenate(row),np.concatenate(col))),shape=(2*self.n,2*self.n)).tocsc()
        A.data[abs(A.data)<1e-16]=0.;A.eliminate_zeros()
        rhs=[]
        for s in sources:
            for axis in axes:
                e,h=incoming(self.points,s,q,axis);fields=[e,h];f=np.zeros(2*self.n,complex)
                for b,v,(i,j) in zip(blocks,vacuum,[(0,0),(0,1),(1,0),(1,1)]):
                    cells=-np.einsum('cij,cj->ci',b-v,fields[j][self.cells]);mask=self.row_cells>=0
                    np.add.at(f,self.row_cells[mask]+i*self.n,cells[mask])
                rhs.append(f)
        rhs=np.asarray(rhs).T
        # Element and COO work arrays are no longer needed by the assembled CSC
        # system. Release them before sparse LU's peak-memory allocation.
        del blocks,vacuum,data,row,col,fields,e,h,cells,f,b,v
        lu=splu(A,permc_spec='MMD_AT_PLUS_A');u=lu.solve(rhs)
        residual=np.linalg.norm(A@u-rhs)/max(np.linalg.norm(rhs),1e-30)
        ez,ge=self.sample(u[:self.n],receivers);_,gh=self.sample(u[self.n:],receivers)
        kap2=K*K-q*q;et=1j*q/kap2*ge+1j*K/kap2*np.stack([-gh[:,1,:],gh[:,0,:]],axis=1)
        field=np.concatenate([et,ez[:,None,:]],axis=1)
        # SuperLU.nnz does not materialize copies of the large triangular factors.
        return field,dict(**self.metadata,q=[q.real,q.imag],epsilon=[epsilon.real,epsilon.imag],linear_residual=float(residual),seconds=time.perf_counter()-started,lu_nonzeros=int(lu.nnz),lu_nonzeros_kind='SuperLU stored entries; may include structural zeros')


"""Coupled vector Maxwell BIE for a z-invariant dielectric quadrant.

exp(+i wt), Fourier convention exp(+i q z), vacuum k=2pi. Longitudinal
E_z and Z0 H_z satisfy Helmholtz equations with kappa^2=k^2 epsilon-q^2.
The four Maxwell tangential continuity conditions couple them when q!=0.
No ray tracer, UTD coefficient, material fit or reference-field lookup.
"""
import time
import numpy as np
from scipy.linalg import lu_factor,lu_solve
from scipy.special import hankel2
from numpy.polynomial.legendre import leggauss

K=2*np.pi
def outgoing_sqrt(v):
    v=np.sqrt(complex(v))
    return -v if v.imag>0 else v
def green(k,r):return -.25j*hankel2(0,k*r)

def incident(points,source,q,axis=2):
    """Exact Fourier-domain longitudinal fields of an electric point dipole."""
    kap=outgoing_sqrt(K*K-q*q);d=np.asarray(points)-np.asarray(source)[:2]
    r=np.sqrt(np.sum(d*d,axis=-1));g=green(kap,r)
    grad=.25j*kap*hankel2(1,kap*r)[...,None]*d/r[...,None]
    if axis==2:return (kap*kap/(K*K))*g,np.zeros_like(g)
    e=1j*q/(K*K)*grad[...,axis]
    h=(1j/K)*(grad[...,0] if axis==1 else -grad[...,1])
    return e,h

class VectorWedgeBEM:
    def __init__(self,panels=16,core=3.,tail=3.,stretch=2.,quadrature=12):
        h=1/panels;near=np.geomspace(h/256,h,9)
        p=np.unique(np.r_[0.,near,np.arange(h,core+tail+h/2,h)])
        c=p-1j*stretch*np.maximum(p-core,0.)**3/(3*tail**2)
        a,b=c[:-1],c[1:];mid=(a+b)/2;length=b-a;nf=len(mid)
        self.points=np.r_[np.stack([mid,0*mid],-1),np.stack([0*mid,mid],-1)]
        self.length=np.tile(length,2);self.normals=np.repeat([[0.,-1.],[-1.,0.]],nf,axis=0)
        self.tangents=np.repeat([[1.,0.],[0.,1.]],nf,axis=0)
        self.oriented=np.stack([-self.normals[:,1],self.normals[:,0]],axis=-1)
        t,w=leggauss(quadrature);self.t=t/2;self.w=w/2
        self.samples=self.points[:,None,:]+self.length[:,None,None]*self.t[None,:,None]*self.tangents[:,None,:]
        self.metadata=dict(method='coupled longitudinal vector Maxwell transmission BIE',panels=panels,core=core,tail=tail,stretch=stretch,quadrature=quadrature,boundary_panels=len(self.points))

    def operators(self,targets,k,diagonal=False,gradient=False):
        S=[];D=[];T=[];GS=[];GD=[]
        weights=self.length[:,None]*self.w[None,:]
        for block in np.array_split(np.asarray(targets),max(1,(len(targets)+31)//32)):
            d=self.samples[None,:,:,:]-block[:,None,None,:];r=np.sqrt(np.sum(d*d,axis=-1))
            g=green(k,r);gp=.25j*k*hankel2(1,k*r);dot=np.sum(d*self.normals[None,:,None,:],axis=-1)
            S.append(np.sum(g*weights,axis=-1));D.append(np.sum(gp*dot/r*weights,axis=-1))
            T.append(np.sum(gp*np.sum(d*self.oriented[None,:,None,:],axis=-1)/r*weights,axis=-1))
            if gradient:
                GS.append(np.sum((-gp/r)[...,None]*d*weights[None,:,:,None],axis=-2))
                # d/d target grad_source G: minus Hessian of G.
                gpp=-k*k*g-gp/r
                hess=((gpp-gp/r)*dot/(r*r))[...,None]*d+(gp/r)[...,None]*self.normals[None,:,None,:]
                GD.append(np.sum(-hess*weights[None,:,:,None],axis=-2))
        S=np.concatenate(S);D=np.concatenate(D);T=np.concatenate(T)
        if diagonal:
            r=self.length[:,None]*abs(self.t)[None,:]
            smooth=green(k,r)+np.log(abs(self.t))[None,:]/(2*np.pi)
            selfterm=self.length*(np.sum(smooth*self.w,axis=-1)+(1+np.log(2))/(2*np.pi))
            np.fill_diagonal(S,selfterm);np.fill_diagonal(D,0.);np.fill_diagonal(T,0.)
        return (S,D,T,np.concatenate(GS),np.concatenate(GD)) if gradient else (S,D,T)

    def solve(self,q,epsilon,sources,receivers,axes=(2,),boundary='dielectric',equilibrate=True):
        started=time.perf_counter();n=len(self.points);I=np.eye(n);zero=np.zeros_like(I)
        k0=outgoing_sqrt(K*K-q*q);ki=outgoing_sqrt(K*K*epsilon-q*q)
        S0,D0,_=self.operators(self.points,k0,True)
        Si,Di,Ti=self.operators(self.points,ki,True) if boundary=='dielectric' else (zero,zero,zero)
        b=ki*ki/(k0*k0);a=b/epsilon;ce=-q/(K*epsilon)*(b-1);ch=q/K*(b-1)
        # Integration by parts around the continuous boundary gives
        # S d_t u = -T u. Endpoint contributions cancel at the wedge corner.
        A=np.block([[.5*I-D0,zero,S0,zero],[zero,.5*I-D0,zero,S0],
                    [.5*I+Di,ce*Ti,-a*Si,zero],[ch*Ti,.5*I+Di,zero,-b*Si]])
        if boundary=='pec':A=np.block([[.5*I-D0,zero,S0,zero],[zero,.5*I-D0,zero,S0],[I,zero,zero,zero],[zero,zero,zero,I]])
        rhs=[]
        for s in sources:
            for axis in axes:
                e,h=incident(self.points,s,q,axis);rhs.append(np.r_[e,h,np.zeros(2*n)])
        rhs=np.array(rhs).T
        if equilibrate:
            columns=1/np.maximum(np.max(abs(A),axis=0),1e-30)
            scaled=A*columns[None,:];rows=1/np.maximum(np.max(abs(scaled),axis=1),1e-30)
            factors=lu_factor(rows[:,None]*scaled)
            solve=lambda b:columns[:,None]*lu_solve(factors,rows[:,None]*b)
        else:
            factors=lu_factor(A);solve=lambda b:lu_solve(factors,b)
        u=solve(rhs);refinements=0
        for _ in range(3):
            residual_vector=rhs-A@u
            if np.linalg.norm(residual_vector)<1e-11*np.linalg.norm(rhs):break
            u+=solve(residual_vector);refinements+=1
        residual=np.linalg.norm(A@u-rhs)/np.linalg.norm(rhs)
        S,D,_,GS,GD=self.operators(np.asarray(receivers)[:,:2],k0,gradient=True)
        Ez=D@u[:n]-S@u[2*n:3*n]
        ge=np.einsum('rni,nj->rij',GD,u[:n])-np.einsum('rni,nj->rij',GS,u[2*n:3*n])
        gh=np.einsum('rni,nj->rij',GD,u[n:2*n])-np.einsum('rni,nj->rij',GS,u[3*n:])
        Et=1j*q/(k0*k0)*ge+1j*K/(k0*k0)*np.stack([-gh[:,1,:],gh[:,0,:]],axis=1)
        field=np.concatenate([Et,Ez[:,None,:]],axis=1)
        return field,dict(**self.metadata,q=[q.real,q.imag],epsilon=[epsilon.real,epsilon.imag],linear_residual=float(residual),solution_max=float(abs(u).max()),equilibrated=equilibrate,iterative_refinements=refinements,seconds=time.perf_counter()-started)


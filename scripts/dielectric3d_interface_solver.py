"""Exact block elimination with an interface-only iterative Schur solve.

Reference-only adapter; no FEM matrix, RHS, mesh or sampling change. The
longitudinal coupling has support only at material interfaces. Two scalar LU
factors replace the full coupled factor; the reduced solve retains all terms.
"""
import hashlib,time
from pathlib import Path
import numpy as np
from scipy.sparse.linalg import splu,gmres,LinearOperator

class InterfaceFactor:
    def __init__(self,A,**kwargs):
        started=time.perf_counter();self.n=A.shape[0]//2
        assert A.shape==(2*self.n,2*self.n)
        n=self.n;self.B=A[:n,n:].tocsc();C=A[n:,:n].tocsc()
        self.indices=np.flatnonzero(np.diff(C.indptr));self.C=C[:,self.indices].tocsr()
        self.E=splu(A[:n,:n].tocsc(),permc_spec='MMD_AT_PLUS_A',diag_pivot_thresh=.01)
        self.H=splu(A[n:,n:].tocsc(),permc_spec='MMD_AT_PLUS_A',diag_pivot_thresh=.01)
        self.nnz=self.E.nnz+self.H.nnz
        self.metadata=dict(method='interface Schur GMRES with two scalar SuperLU factors',
            reduced_unknowns=len(self.indices),scalar_lu_nonzeros=int(self.nnz),
            factor_seconds=time.perf_counter()-started,rtol=1e-12,restart=80,maxiter=50,diagonal_pivot_threshold=.01,rhs=[])
    def transfer(self,w):
        return self.E.solve(self.B@self.H.solve(self.C@w))
    def solve(self,rhs):
        vector=rhs.ndim==1;rhs=rhs[:,None] if vector else rhs;columns=[]
        for b in rhs.T:
            f,g=b[:self.n],b[self.n:];u0=self.E.solve(f-self.B@self.H.solve(g));history=[]
            if len(self.indices):
                op=LinearOperator((len(self.indices),)*2,matvec=lambda w:w-self.transfer(w)[self.indices],dtype=np.complex128)
                w,info=gmres(op,u0[self.indices],rtol=1e-12,atol=0.,restart=80,maxiter=50,callback=history.append,callback_type='pr_norm')
                assert info==0,dict(info=info,iterations=len(history),last=history[-1] if history else None)
                reduced=np.linalg.norm(op@w-u0[self.indices])/max(np.linalg.norm(u0[self.indices]),1e-30)
                assert reduced<2e-12,reduced
                u=u0+self.transfer(w)
            else:u=u0;reduced=0.
            v=self.H.solve(g-self.C@u[self.indices]);columns.append(np.r_[u,v])
            self.metadata['rhs'].append(dict(iterations=len(history),reduced_residual=float(reduced)))
        answer=np.array(columns).T
        return answer[:,0] if vector else answer

def activate():
    import dielectric3d_fem
    records=[]
    def factor(A,**kwargs):
        value=InterfaceFactor(A,**kwargs);records.append(value.metadata);return value
    dielectric3d_fem.splu=factor
    return records

def policy():
    return dict(name='exact interface Schur elimination',matrix_changed=False,rhs_changed=False,
        sampler_changed=False,precision='complex128',source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())

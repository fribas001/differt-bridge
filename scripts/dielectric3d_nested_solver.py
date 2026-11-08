"""Geometric nested-dissection ordering of the exact scalar FEM blocks."""
import hashlib,time
from pathlib import Path
import numpy as np
from scipy.sparse.linalg import splu
from dielectric3d_interface_solver import InterfaceFactor

def ordering(side,leaf=12):
    grid=np.arange(side*side,dtype=np.int32).reshape(side,side)
    def visit(a):
        nx,ny=a.shape
        if max(nx,ny)<=leaf:return a.ravel()
        if nx>=ny:
            k=nx//2;return np.r_[visit(a[:k]),visit(a[k+1:]),a[k].ravel()]
        k=ny//2;return np.r_[visit(a[:,:k]),visit(a[:,k+1:]),a[:,k].ravel()]
    return visit(grid)

class OrderedFactor:
    def __init__(self,A,p):
        self.p=p;self.factor=splu(A[p,:][:,p].tocsc(),permc_spec='NATURAL',diag_pivot_thresh=.01)
        self.nnz=self.factor.nnz
    def solve(self,b):
        answer=np.empty_like(b);answer[self.p]=self.factor.solve(b[self.p]);return answer

class NestedInterfaceFactor(InterfaceFactor):
    def __init__(self,A,**kwargs):
        started=time.perf_counter();self.n=A.shape[0]//2;n=self.n;side=int(round(np.sqrt(n)));assert side*side==n
        self.B=A[:n,n:].tocsc();C=A[n:,:n].tocsc();self.indices=np.flatnonzero(np.diff(C.indptr));self.C=C[:,self.indices].tocsr()
        p=ordering(side);assert len(np.unique(p))==n
        self.E=OrderedFactor(A[:n,:n].tocsc(),p);self.H=OrderedFactor(A[n:,n:].tocsc(),p);self.nnz=self.E.nnz+self.H.nnz
        self.metadata=dict(method='interface Schur GMRES with nested-dissection scalar LU',reduced_unknowns=len(self.indices),
            scalar_lu_nonzeros=int(self.nnz),factor_seconds=time.perf_counter()-started,rtol=1e-12,restart=80,maxiter=50,
            diagonal_pivot_threshold=.01,ordering='geometric nested dissection, leaf maximum side 12',rhs=[])

def activate():
    import dielectric3d_fem
    records=[]
    def factor(A,**kwargs):
        v=NestedInterfaceFactor(A,**kwargs);records.append(v.metadata);return v
    dielectric3d_fem.splu=factor;return records

def policy():
    return dict(name='exact interface Schur with geometric nested dissection',matrix_changed=False,rhs_changed=False,
        sampler_changed=False,precision='complex128',source_hashes={n:hashlib.sha256(Path(__file__).with_name(n).read_bytes()).hexdigest() for n in ('dielectric3d_nested_solver.py','dielectric3d_interface_solver.py')})

"""Research-only zero-drop SuperLU factorization with bounded initial storage.

The full-LU allocator guesses 30 times matrix nnz before allocating workspace.
The zero-drop ILU path exposes that initial allocation size. With only the
basic drop rule and tolerance zero, there is no fill quota or magnitude drop.
This is accepted only after field equivalence and original-system residual
checks; it is not installed into either ray-tracing runtime.
"""
import hashlib
from pathlib import Path
from scipy.sparse.linalg import spilu

def activate():
    import dielectric3d_fem
    def factor(A,**kwargs):
        return spilu(A,drop_tol=0.,fill_factor=3.,drop_rule='basic',
            diag_pivot_thresh=.01,panel_size=8,relax=10,
            options={'RowPerm':'NOROWPERM','ILU_FillTol':0.},**kwargs)
    dielectric3d_fem.splu=factor
    return dict(method='SuperLU zero-drop factorization',drop_tol=0.,fill_factor=3.,
        drop_rule='basic',diagonal_pivot_threshold=.01,panel_size=8,relax=10,
        row_permutation='NOROWPERM',tiny_pivot_fill_tolerance=0.,equations_changed=False,
        precision='complex128',source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())

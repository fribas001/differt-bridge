"""Process-local sparse factorization policy for large reference-only solves.

The Maxwell matrix, RHS, mesh and sampler remain unchanged. A lower SuperLU
diagonal-pivot threshold limits numerical-pivot fill. Every solve still must
meet the original residual gate and this policy is independently compared
with the standard factorization before use. No installed library is edited.
"""
import hashlib
from pathlib import Path
from scipy.sparse.linalg import splu
import dielectric3d_fem

def activate(threshold=0.01):
    assert 0<=threshold<=1
    def factor(A,**kwargs):
        return splu(A,diag_pivot_thresh=threshold,**kwargs)
    dielectric3d_fem.splu=factor
    return dict(method='SuperLU',diagonal_pivot_threshold=threshold,
        equations_changed=False,precision='complex128',
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())

"""Fresh analytic plane-interface and vacuum checks for the FEM reference."""
import sys
from pathlib import Path
import numpy as np
from dielectric3d_fem import VectorWedgeFEM
from dielectric3d_plane import reflected
from analyze_dielectric3d import rel,pairs
from investigate_dielectric3d_polarization import read,save,sha

def main(root):
    w=root/'work/d3pol'
    from dielectric3d_fem_linear_solver import activate
    policy=activate();assert policy==read(w/'linear_solver_validation.json')['policy']
    d=read(w/'diagnostics.json');eps=complex(*d['epsilon']);source=d['source'];rs=[[-1.,-1.,.7],[-.5,1.5,.7]];rows=[]
    for q in (1.525532409916329+.4977669015873694j,4.9+.5j):
        exact=[];quad=[]
        for r in rs:
            v,e=reflected(q,eps,source,r);exact.append(v);quad.append(e)
        exact=np.array(exact);levels=[]
        for n in (32,64):
            v,meta=VectorWedgeFEM(n,geometry='halfspace').solve(q,eps,[source],rs,(0,1,2))
            levels.append(dict(resolution=n,error=rel(v,exact),zx_error=rel(v[:,0,2],exact[:,0,2]),field=pairs(v),metadata=meta))
        rows.append(dict(q=pairs(q),exact=pairs(exact),quadrature_error=quad,levels=levels));print('PLANE',q,[(v['resolution'],v['error'],v['zx_error']) for v in levels],flush=True)
    vacuum,meta=VectorWedgeFEM(32).solve(3+.3j,1.,[source],rs,(0,1,2))
    passed=all(v['levels'][1]['error']<v['levels'][0]['error'] and v['levels'][1]['error']<.01 and v['levels'][1]['zx_error']<v['levels'][0]['zx_error'] for v in rows) and abs(vacuum).max()<1e-12
    result=dict(status='passed' if passed else 'failed',planes=rows,vacuum_maximum=float(abs(vacuum).max()),vacuum_metadata=meta,linear_solver=policy,
       source_hashes={n:sha(Path(__file__).with_name(n)) for n in ('dielectric3d_fem.py','dielectric3d_plane.py','validate_dielectric3d_polarization_reference.py','dielectric3d_fem_linear_solver.py')},
       scope='Fresh analytic flat-interface controls at two q values and vacuum. These do not certify every wedge field.')
    save(w/'analytic_controls.json',result);assert passed

if __name__=='__main__':main(Path(sys.argv[1]).resolve())

"""Independent analytic controls for cubic recovery and nested block solves."""
import sys
from pathlib import Path
import numpy as np
from dielectric3d_sampling_audit import SamplingAuditFEM,weights
from dielectric3d_nested_solver import activate,policy
from dielectric3d_plane import reflected
from investigate_dielectric3d_polarization import read,save,sha
from analyze_dielectric3d import rel,pairs

def main(root):
    w=root/'work/d3res';records=activate();d=read(root/'work/d3pol/diagnostics.json');eps=complex(*d['epsilon']);source=d['source'];rs=[[-1.,-1.,.7],[-.5,1.5,.7]];rows=[]
    for t in (0.,.17,.5,.99,1.):
        v,g=weights(t)
        for degree in range(4):
            assert abs(v@(np.arange(-1,3,dtype=float)**degree)-t**degree)<1e-12
            assert abs(g@(np.arange(-1,3,dtype=float)**degree)-(degree*t**(degree-1) if degree else 0))<1e-12
    for q in (1.525532409916329+.4977669015873694j,4.9+.5j):
        exact=[];quad=[]
        for r in rs:
            v,e=reflected(q,eps,source,r);exact.append(v);quad.append(e)
        exact=np.array(exact);levels=[]
        for n in (32,64,96):
            model=SamplingAuditFEM(n,geometry='halfspace');v,meta=model.solve(q,eps,[source],rs,(0,1,2));c=model.cubic_field
            assert meta['linear_residual']<1e-9
            levels.append(dict(resolution=n,original_error=rel(v,exact),original_zx_error=rel(v[:,0,2],exact[:,0,2]),
                cubic_error=rel(c,exact),cubic_zx_error=rel(c[:,0,2],exact[:,0,2]),original=pairs(v),cubic=pairs(c),metadata=meta,solver=records[-1]))
            print('PLANE',q,n,levels[-1]['original_error'],levels[-1]['cubic_error'],flush=True)
        rows.append(dict(q=pairs(q),exact=pairs(exact),quadrature_error=quad,levels=levels))
    model=SamplingAuditFEM(32);v,meta=model.solve(3+.3j,1.,[source],rs,(0,1,2));vacuum=max(abs(v).max(),abs(model.cubic_field).max())
    passed=all(r['levels'][-1]['cubic_error']<r['levels'][-1]['original_error'] and r['levels'][-1]['cubic_zx_error']<r['levels'][-1]['original_zx_error'] and all(a['cubic_error']>b['cubic_error'] for a,b in zip(r['levels'],r['levels'][1:])) for r in rows) and vacuum<1e-12
    result=dict(status='passed' if passed else 'failed',planes=rows,vacuum_maximum=float(vacuum),policy=policy(),
        sources={n:sha(Path(__file__).with_name(n)) for n in ('dielectric3d_sampling_audit.py','dielectric3d_nested_solver.py','dielectric3d_interface_solver.py','dielectric3d_plane.py','dielectric3d_fem.py')},
        scope='Analytic plane interface at two q values; reconstruction diagnostics are not a certified wedge error bound.')
    save(w/'sampling_validation.json',result);assert passed

if __name__=='__main__':main(Path(sys.argv[1]).resolve())

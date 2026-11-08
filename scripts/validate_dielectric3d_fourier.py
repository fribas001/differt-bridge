"""Check vector Fourier synthesis against the analytic 3D free-space dyadic."""
import json,sys
from pathlib import Path
import numpy as np
from dielectric3d_synthesis import quadrature
from validate_dielectric3d_refinement import free
from validate_dielectric3d_controls import error,pairs,save
from maxwell3d_pec_reference import free_dyadic
from native3d_cases import point

def main(output):
    s=point(60,1.5,0);rs=[point(a,2,z) for z in (0,1,3) for a in (25,130,245)];exact=np.array([free_dyadic(s,r) for r in rs]);rows=[]
    for order in (6,8,12):
        q,w=quadrature(order,.5,40.);values=[]
        for r in rs:
            a=np.zeros((3,3),complex);dz=r[2]-s[2]
            for qi,wi in zip(q,w):
                f=free(qi,s,r)
                for rx in range(3):
                    for tx in range(3):a[rx,tx]+=wi*f[rx,tx]*(1j*np.sin(qi*dz) if (rx==2)!=(tx==2) else np.cos(qi*dz))/np.pi
            values.append(a)
        values=np.array(values);rows.append(dict(order=order,relative_error=error(values,exact),maximum_absolute_error=float(abs(values-exact).max()),field=pairs(values)))
    passed=rows[-1]['relative_error']<2e-5 and rows[-1]['relative_error']<rows[0]['relative_error']
    result=dict(status='passed' if passed else 'failed',source=s,receivers=rs,exact=pairs(exact),convergence=rows)
    save(output/'fourier_control.json',result);print(result['status'],[(r['order'],r['relative_error']) for r in rows])
    if not passed:raise SystemExit('Fourier normalization control failed')

if __name__=='__main__':main(Path(sys.argv[1]))

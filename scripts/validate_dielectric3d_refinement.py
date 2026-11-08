"""Refine the initially failed coarse vacuum/reciprocity controls explicitly."""
import json
from pathlib import Path
import numpy as np
from scipy.special import hankel2
from dielectric3d_bem import VectorWedgeBEM
from dielectric3d_fem import VectorWedgeFEM
from native3d_cases import point
from validate_dielectric3d_controls import pairs,error,save

def free(q,s,r):
    k=2*np.pi;kap=np.sqrt(k*k-q*q+0j)
    if kap.imag>0:kap=-kap
    d=np.array(r[:2])-s[:2];rho=np.linalg.norm(d);n=d/rho;g=-.25j*hankel2(0,kap*rho);gp=.25j*kap*hankel2(1,kap*rho);gpp=-kap*kap*g-gp/rho
    a=np.zeros((3,3),complex);a[:2,:2]=g*np.eye(2)+((gpp-gp/rho)*np.outer(n,n)+gp/rho*np.eye(2))/k**2
    a[:2,2]=a[2,:2]=1j*q*gp*n/k**2;a[2,2]=(1-q*q/k**2)*g
    return a

def main(output):
    s=point(60,1.5,0);r=point(170,2,3);ports=[s,r];rows=[]
    for q in (3+.3j,6.4+.5j,10+.5j):
        inc=free(q,s,r)
        for method in ('bem','fem'):
            levels=[]
            for n in (16,32,48):
                model=VectorWedgeBEM(n) if method=='bem' else VectorWedgeFEM(n)
                a,m=model.solve(q,5.24-.632143019j,ports,ports,(0,1,2));b,m=model.solve(-q,5.24-.632143019j,ports,ports,(0,1,2))
                fw=a[1,:,:3];rv=b[0,:,3:].T;vac,vm=model.solve(q,1.,[s],[r],(0,1,2))
                levels.append(dict(resolution=n,scattered_reciprocity=error(fw,rv),total_reciprocity=error(fw+inc,rv+inc),vacuum_relative=float(np.linalg.norm(vac)/np.linalg.norm(inc)),vacuum_absolute=float(abs(vac).max()),forward=pairs(fw),reverse=pairs(rv),vacuum=pairs(vac),solver=m))
                print(method,q,n,'reciprocity total',levels[-1]['total_reciprocity'],'vacuum relative',levels[-1]['vacuum_relative'],flush=True)
            rows.append(dict(q=pairs(q),method=method,free=pairs(inc),levels=levels))
            save(output/'refined_controls.json',dict(status='running',rows=rows))
    gates=[dict(method=row['method'],q=row['q'],reciprocity_converges=row['levels'][-1]['total_reciprocity']<row['levels'][0]['total_reciprocity'],fine_total_reciprocity_below_one_percent=row['levels'][-1]['total_reciprocity']<.01,vacuum_below_point_one_percent=row['levels'][-1]['vacuum_relative']<.001) for row in rows]
    passed=all(all(v for k,v in gate.items() if k not in ('method','q')) for gate in gates)
    save(output/'refined_controls.json',dict(status='passed' if passed else 'failed',rows=rows,gates=gates,notes='Original coarse failures retained in modal_controls.json. Scattered-mode reciprocity can be larger when scattered fields are small; total and absolute diagnostics are both retained. No averaging of reversed fields.'))
    if not passed:raise SystemExit('Refined controls need investigation')

if __name__=='__main__':
    import sys;main(Path(sys.argv[1]))

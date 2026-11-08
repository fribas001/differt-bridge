"""Independent analytic, domain and reciprocity controls for vector Maxwell."""
import argparse,hashlib,json,time
from pathlib import Path
import numpy as np
from dielectric3d_bem import VectorWedgeBEM
from dielectric3d_fem import VectorWedgeFEM
from dielectric3d_plane import reflected
from dielectric3d_synthesis import quadrature,run
from maxwell3d_pec_reference import electric_z_column,free_dyadic
from native3d_cases import point

def pairs(v):return np.stack([np.real(v),np.imag(v)],axis=-1).tolist()
def error(a,b):return float(np.linalg.norm(a-b)/max(np.linalg.norm(b),1e-30))
def save(path,data):path.write_text(json.dumps(data,indent=2,allow_nan=False),encoding='utf-8')

def modal(output):
    eps=5.24-.632143019j;s=[-1.3,.75,0.];rs=[[-1.,-1.,1.],[-.5,1.5,1.]];rows=[]
    for q in (0j,3+.3j,6.4+.5j,10+.5j):
        exact=[];quad=[]
        for r in rs:
            f,e=reflected(q,eps,s,r);exact.append(f);quad.append(e)
        exact=np.array(exact);conv=[]
        for n in (16,24,32):
            f,meta=VectorWedgeFEM(n,geometry='halfspace').solve(q,eps,[s],rs,(0,1,2))
            conv.append(dict(resolution=n,relative_error=error(f,exact),field=pairs(f),solver=meta))
        rows.append(dict(q=pairs(q),analytic=pairs(exact),quadrature_error=quad,convergence=conv))
        print('PLANE',q,[c['relative_error'] for c in conv],flush=True)
    source=point(60,1.5,0);receivers=[point(a,2,1) for a in (25,130,245)];domain=[];vacuum=[];reciprocity=[]
    for q in (3+.3j,6.4+.5j,10+.5j):
        fields=[]
        for inner,pml in ((2.5,1.5),(3.,2.)):
            f,m=VectorWedgeFEM(24,inner,pml).solve(q,eps,[source],receivers,(0,1,2));fields.append(f)
        domain.append(dict(q=pairs(q),method='fem',relative_change=error(fields[0],fields[1]),fields=pairs(fields)))
        fields=[]
        for core,tail in ((3.,3.),(4.,4.)):
            f,m=VectorWedgeBEM(16,core,tail).solve(q,eps,[source],receivers,(0,1,2));fields.append(f)
        domain.append(dict(q=pairs(q),method='bem',relative_change=error(fields[0],fields[1]),fields=pairs(fields)))
        for method,model in [('bem',VectorWedgeBEM(16)),('fem',VectorWedgeFEM(24))]:
            f,m=model.solve(q,1.,[source],receivers,(0,1,2));vacuum.append(dict(method=method,q=pairs(q),maximum_scattered=float(abs(f).max()),solver=m))
            # Lorentz reciprocity in Fourier z: G(q;r,s) = G(-q;s,r)^T.
            other=point(170,2,3);ports=[source,other]
            a,m=model.solve(q,eps,ports,ports,(0,1,2))
            b,m=model.solve(-q,eps,ports,ports,(0,1,2))
            fw=a[1,:,:3];rv=b[0,:,3:].T
            reciprocity.append(dict(method=method,q=pairs(q),relative_error=error(fw,rv),forward=pairs(fw),reverse_transpose=pairs(rv)))
    passed=all(row['convergence'][-1]['relative_error']<.04 and row['convergence'][-1]['relative_error']<row['convergence'][0]['relative_error'] for row in rows)
    passed &= max(r['relative_change'] for r in domain)<.02
    passed &= max(r['maximum_scattered'] for r in vacuum)<1e-9
    passed &= max(r['relative_error'] for r in reciprocity)<.03
    data=dict(status='passed' if passed else 'failed',epsilon=pairs(eps),source=s,receivers=rs,plane=rows,domain=domain,vacuum=vacuum,reciprocity=reciprocity,
              scope='Modal controls at stated wavenumbers, not a bound on every 3D point or material.')
    save(output/'modal_controls.json',data)
    if not passed:raise SystemExit('A control needs investigation; see modal_controls.json')

def pec(output):
    sources=[point(60,1.5,0)];receivers=[point(a,2,z) for z in (0,1,3) for a in (25,130,245)]
    ports=dict(sources=sources,receivers=receivers,axes=[2]);rows=[]
    exact=1.5*np.array([electric_z_column(sources[0],r) for r in receivers])[:,:,None]
    for n in (16,32):
        result=run(output/f'pec_bem{n}',resolution=n,order=8,boundary='pec',ports=ports)
        v=np.array(result['field']);v=v[...,0]+1j*v[...,1]
        rows.append(dict(resolution=n,relative_error=error(v,exact),maximum_absolute_error=float(abs(v-exact).max()),field=pairs(v)))
    passed=rows[-1]['relative_error']<.02 and rows[-1]['relative_error']<rows[0]['relative_error']
    save(output/'pec_control.json',dict(status='passed' if passed else 'failed',ports=ports,exact=pairs(exact),convergence=rows))
    if not passed:raise SystemExit('PEC synthesis control needs investigation')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('output',type=Path);ap.add_argument('mode',choices=['modal','pec']);a=ap.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    globals()[a.mode](a.output)

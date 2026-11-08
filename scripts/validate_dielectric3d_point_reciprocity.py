"""Independent 3D Lorentz reciprocity: solve both source locations without averaging."""
import hashlib,json,sys
from pathlib import Path
import numpy as np
from dielectric3d_fem import VectorWedgeFEM
from dielectric3d_synthesis import quadrature
from maxwell3d_pec_reference import free_dyadic
from native3d_cases import point
from validate_dielectric3d_controls import pairs,error,save

def main(output):
    folder=output/'point_reciprocity_modes';folder.mkdir(exist_ok=True)
    ports=[point(60,1.5,0),point(170,2,3)];model=VectorWedgeFEM(32);nodes,weights=quadrature(8,.5,24.);fields=np.zeros((2,3,3),complex);meta=[]
    for i,(q,w) in enumerate(zip(nodes,weights)):
        f,m=model.solve(q,5.24-.632143019j,ports,ports,(0,1,2));assert m['linear_residual']<1e-9
        file=folder/f'mode_{i:03d}.npz';np.savez_compressed(file,field=f);m['sha256']=hashlib.sha256(file.read_bytes()).hexdigest();meta.append(m)
        for direction,(si,ri) in enumerate([(0,1),(1,0)]):
            dz=ports[ri][2]-ports[si][2]
            for rx in range(3):
                for tx in range(3):fields[direction,rx,tx]+=w*f[ri,rx,si*3+tx]*(1j*np.sin(q*dz) if (rx==2)!=(tx==2) else np.cos(q*dz))/np.pi
        print('POINT RECIPROCITY',i+1,'/',len(nodes),flush=True)
    for direction,(si,ri) in enumerate([(0,1),(1,0)]):fields[direction]+=free_dyadic(ports[si],ports[ri])
    fields*=1.5;err=error(fields[0],fields[1].T)
    save(output/'point_reciprocity.json',dict(status='passed' if err<.005 else 'failed',ports=ports,method='FEM32, Fourier order8',epsilon=[5.24,-.632143019],forward=pairs(fields[0]),reverse=pairs(fields[1]),relative_error=err,maximum_absolute_error=float(abs(fields[0]-fields[1].T).max()),modes=meta,source_hashes={n:hashlib.sha256((Path(__file__).parent/n).read_bytes()).hexdigest() for n in ['validate_dielectric3d_point_reciprocity.py','dielectric3d_fem.py','dielectric3d_synthesis.py']}))
    if err>=.005:raise SystemExit('3D reciprocity control needs investigation')

if __name__=='__main__':main(Path(sys.argv[1]))

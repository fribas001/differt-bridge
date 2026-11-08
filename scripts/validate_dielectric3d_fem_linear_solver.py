"""Compare reduced-fill sparse solves against completed standard FEM64 solves."""
import sys,time
from pathlib import Path
import numpy as np
from dielectric3d_fem_linear_solver import activate
from dielectric3d_fem import VectorWedgeFEM
from dielectric3d_synthesis import quadrature
from investigate_dielectric3d_polarization import read,save,sha

def main(root):
    w=root/'work/d3pol';d=read(w/'diagnostics.json');cfg=read(w/'holdout_b_fem64q8/config.json');ri=[cfg['ports']['receivers'].index(r) for r in d['receivers']]
    policy=activate();out=w/'linear64';out.mkdir(exist_ok=True);nodes,_=quadrature(8);model=VectorWedgeFEM(64);rows=[]
    for i in (0,5,10,20,26,32):
        field,meta=model.solve(nodes[i],complex(*d['epsilon']),[d['source']],d['receivers'],(2,))
        path=out/f'mode_{i:03d}.npz';np.savez_compressed(path,field=field);meta.update(field_sha256=sha(path),linear_solver=policy);save(path.with_suffix('.json'),meta)
        bp=w/f'holdout_b_fem64q8/mode_{i:03d}.npz';bm=read(bp.with_suffix('.json'));assert sha(bp)==bm['field_sha256'];baseline=np.load(bp)['field'][ri,:,2,None]
        change=float(np.linalg.norm(field-baseline)/np.linalg.norm(baseline));assert change<1e-9 and meta['linear_residual']<1e-9
        rows.append(dict(index=i,relative_change=change,standard_lu_nonzeros=bm['lu_nonzeros'],new_lu_nonzeros=meta['lu_nonzeros'],standard_seconds=bm['seconds'],new_seconds=meta['seconds'],linear_residual=meta['linear_residual']))
        print('LINEAR',i,rows[-1],flush=True)
    save(w/'linear_solver_validation.json',dict(status='passed',policy=policy,rows=rows,scope='Same FEM64 Maxwell matrix, RHS and sampler. Relative field difference below 1e-9; residual below 1e-9. No production/runtime source edit.'))

if __name__=='__main__':main(Path(sys.argv[1]).resolve())

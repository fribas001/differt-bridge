"""One-parameter modal controls at the remaining z-to-x target ports."""
import argparse, hashlib, json
from pathlib import Path
import numpy as np
from dielectric3d_bem import VectorWedgeBEM
from dielectric3d_fem import VectorWedgeFEM
from dielectric3d_synthesis import quadrature
from investigate_dielectric3d_polarization import read, save, sha

def main():
    ap=argparse.ArgumentParser();ap.add_argument('root',type=Path);ap.add_argument('label');ap.add_argument('--method',choices=['bie','fem'],default='bie');ap.add_argument('--resolution',type=int,default=32);ap.add_argument('--core',type=float,default=3.);ap.add_argument('--tail',type=float,default=3.);ap.add_argument('--quadrature',type=int,default=12);ap.add_argument('--inner',type=float,default=2.5);ap.add_argument('--pml',type=float,default=1.5);ap.add_argument('--strength',type=float,default=4.);ap.add_argument('--modes',default='5,10,20,26');ap.add_argument('--pivot',type=float);a=ap.parse_args()
    root=a.root.resolve();w=root/'work/d3res';d=read(root/'work/d3pol/diagnostics.json');out=w/a.label;out.mkdir(exist_ok=True)
    policy=None
    if a.pivot is not None:
        assert a.pivot==.01,'The validated bounded policy fixes the pivot threshold at 0.01'
        from dielectric3d_bounded_solver import activate
        policy=activate()
        assert read(w/'bounded128/validation.json')['config']['policy']==policy
    nodes,_=quadrature(8);indices=[int(v) for v in a.modes.split(',')]
    model=VectorWedgeBEM(a.resolution,a.core,a.tail,quadrature=a.quadrature) if a.method=='bie' else VectorWedgeFEM(a.resolution,a.inner,a.pml,a.strength)
    cfg=dict(method=a.method,resolution=a.resolution,core=a.core,tail=a.tail,quadrature=a.quadrature,inner=a.inner,pml=a.pml,strength=a.strength,sources=[d['source']],receivers=d['receivers'],axes=[2],epsilon=d['epsilon'],indices=indices,source_sha256=sha(Path(__file__).with_name('dielectric3d_bem.py' if a.method=='bie' else 'dielectric3d_fem.py')))
    if policy is not None:cfg['linear_solver']=policy
    if (out/'config.json').exists():assert read(out/'config.json')==cfg
    else:save(out/'config.json',cfg)
    for i in indices:
        file=out/f'mode_{i:03d}.npz';meta=file.with_suffix('.json')
        if file.exists() and meta.exists():assert sha(file)==read(meta)['field_sha256']
        else:
            field,detail=model.solve(nodes[i],complex(*d['epsilon']),cfg['sources'],cfg['receivers'],(2,))
            assert np.isfinite(field).all() and detail['linear_residual']<1e-9
            if policy is not None:detail['linear_solver']=policy
            np.savez_compressed(file,field=field);detail['field_sha256']=sha(file);save(meta,detail)
        print(a.label,i,flush=True)
    save(out/'receipt.json',dict(status='completed',config=cfg))

if __name__=='__main__':main()

"""Independent one-parameter controls for the weak crossed-polarization field."""
import argparse,hashlib,json,time
from pathlib import Path
import numpy as np
from dielectric3d_bem import VectorWedgeBEM
from dielectric3d_fem import VectorWedgeFEM
from dielectric3d_refinement import spectral_quadrature

def main():
    ap=argparse.ArgumentParser();ap.add_argument('root',type=Path);ap.add_argument('label');ap.add_argument('--method',choices=['bie','fem'],default='bie');ap.add_argument('--resolution',type=int,default=32);ap.add_argument('--core',type=float,default=3.);ap.add_argument('--tail',type=float,default=3.);ap.add_argument('--quadrature',type=int,default=12);ap.add_argument('--inner',type=float,default=2.5);ap.add_argument('--pml',type=float,default=1.5);ap.add_argument('--modes',default='5,11,20,26');a=ap.parse_args();root=a.root.resolve();work=root/'work/d3weak';d=json.loads((work/'diagnostics.json').read_text());out=work/a.label;out.mkdir(exist_ok=True)
    source=d['source'];receivers=d['receivers'];eps=complex(*d['epsilon']);indices=[int(i) for i in a.modes.split(',')];nodes,_=spectral_quadrature()
    model=VectorWedgeBEM(a.resolution,a.core,a.tail,quadrature=a.quadrature) if a.method=='bie' else VectorWedgeFEM(a.resolution,a.inner,a.pml)
    config=dict(method=a.method,resolution=a.resolution,core=a.core,tail=a.tail,quadrature=a.quadrature,inner=a.inner,pml=a.pml,sources=[source],receivers=receivers,axes=[1],epsilon=d['epsilon'],indices=indices,source_sha256=hashlib.sha256(Path(__file__).with_name('dielectric3d_bem.py' if a.method=='bie' else 'dielectric3d_fem.py').read_bytes()).hexdigest())
    cfg=out/'config.json'
    if cfg.exists():assert json.loads(cfg.read_text())==config
    else:cfg.write_text(json.dumps(config,indent=2),encoding='utf-8')
    for i in indices:
        file=out/f'mode_{i:03d}.npz';meta=file.with_suffix('.json')
        if file.exists() and meta.exists():assert hashlib.sha256(file.read_bytes()).hexdigest()==json.loads(meta.read_text())['field_sha256']
        else:
            field,detail=model.solve(nodes[i],eps,[source],receivers,(1,));assert np.isfinite(field).all() and detail['linear_residual']<1e-9
            np.savez_compressed(file,field=field);detail['field_sha256']=hashlib.sha256(file.read_bytes()).hexdigest();meta.write_text(json.dumps(detail,indent=2),encoding='utf-8')
        print(a.label,i,flush=True)
    (out/'receipt.json').write_text(json.dumps(dict(status='completed',config=config),indent=2),encoding='utf-8')

if __name__=='__main__':main()

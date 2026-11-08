"""Validate static complex sparse pivots before larger reference runs."""
import argparse
from pathlib import Path
import numpy as np
from dielectric3d_fem_linear_solver import activate
from dielectric3d_sampling_audit import SamplingAuditFEM
from dielectric3d_synthesis import quadrature
from investigate_dielectric3d_polarization import read,save,sha

def main(root,resolution,indices):
    policy=activate(0.);w=root/'work/d3res';d=read(root/'work/d3pol/diagnostics.json');out=w/f'static{resolution}';out.mkdir(exist_ok=True);nodes,_=quadrature(8);rows=[]
    cfg=dict(policy=policy,resolution=resolution,indices=indices,epsilon=d['epsilon'],source=d['source'],receivers=d['receivers'],sources={n:sha(Path(__file__).with_name(n)) for n in ('dielectric3d_fem.py','dielectric3d_sampling_audit.py','dielectric3d_fem_linear_solver.py')})
    if (out/'config.json').exists():assert read(out/'config.json')==cfg
    else:save(out/'config.json',cfg)
    model=SamplingAuditFEM(resolution)
    for i in indices:
        p=out/f'mode_{i:03d}.npz';m=p.with_suffix('.json')
        if p.exists() and m.exists():field=np.load(p)['field'];meta=read(m);assert sha(p)==meta['sha256']
        else:
            field,meta=model.solve(nodes[i],complex(*d['epsilon']),[d['source']],d['receivers'],(2,));assert meta['linear_residual']<1e-9
            np.savez_compressed(p,field=field,cubic=model.cubic_field);meta['sha256']=sha(p);save(m,meta)
        if resolution==64:
            base=root/'work/d3pol/holdout_b_fem64q8';ports=read(base/'config.json')['ports'];ri=[ports['receivers'].index(r) for r in d['receivers']];old=np.load(base/p.name)['field'][ri,:,ports['sources'].index(d['source'])*3+2,None]
        elif resolution==96:base=root/'work/d3pol/target_fem96q8_lowmem';old=np.load(base/p.name)['field']
        elif resolution==128:base=w/'fem128_direct';old=np.load(base/p.name)['field']
        else:old=None
        error=float(np.linalg.norm(field-old)/np.linalg.norm(old)) if old is not None else None
        if error is not None:assert error<1e-8,error
        rows.append(dict(index=i,error=error,metadata=meta,baseline_sha256=sha(base/p.name) if old is not None else None));print('STATIC',resolution,i,'error',error,'seconds',meta['seconds'],'LU nnz',meta['lu_nonzeros'],flush=True)
    save(out/'validation.json',dict(status='passed',config=cfg,rows=rows))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--resolution',type=int,required=True);p.add_argument('--modes',required=True);a=p.parse_args();main(a.root.resolve(),a.resolution,[int(i) for i in a.modes.split(',')])

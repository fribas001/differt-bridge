"""Explicit multiresolution FEM reference, with a separately audited weak tail.

The fine spatial mesh solves q in [0,7]; modes above 7 retain independently
solved FEM64 fields. This is never labelled a uniform FEM80/FEM96 result.
No production BIE value enters this reference or its tail audit.
"""
import argparse, time
from pathlib import Path
import numpy as np
from dielectric3d_fem import VectorWedgeFEM
from dielectric3d_synthesis import quadrature
from maxwell3d_pec_reference import free_dyadic
from investigate_dielectric3d_polarization import read, save, sha

def main(root,resolution):
    w=root/'work/d3pol';d=read(w/'diagnostics.json');base=w/'holdout_b_fem64q8';bc=read(base/'config.json')
    assert bc['resolution']==64 and bc['order']==8 and bc['epsilon']==d['epsilon']
    assert bc['source_hashes']['dielectric3d_fem.py']==sha(Path(__file__).with_name('dielectric3d_fem.py'))
    ports=dict(sources=[d['source']],receivers=d['receivers'],axes=[2]);si=bc['ports']['sources'].index(d['source']);ri=[bc['ports']['receivers'].index(r) for r in d['receivers']]
    cfg=dict(method='fem',resolution=resolution,order=8,epsilon=d['epsilon'],ports=ports,contour=.5,qmax=24.,inner=2.5,pml=1.5,
        mixed_resolution=True,mode_resolutions=[resolution]*32+[64]*32,
        label=f'FEM{resolution} q<7 / FEM64 q>=7',
        tail_provenance=dict(config_sha256=sha(base/'config.json'),folder=str(base.relative_to(root))),
        source_hashes={n:sha(Path(__file__).with_name(n)) for n in ('dielectric3d_fem.py','dielectric3d_synthesis.py','run_dielectric3d_polarization_reference.py')})
    out=w/f'target_fem{resolution}q8';out.mkdir(exist_ok=True)
    if (out/'config.json').exists():assert read(out/'config.json')==cfg
    else:save(out/'config.json',cfg)
    model=VectorWedgeFEM(resolution);nodes,weights=quadrature(8);total=np.zeros((len(ri),3,1),complex);terms=[];metadata=[];start=time.perf_counter()
    dz=np.array(d['receivers'])[:,2]-d['source'][2]
    for i,(q,weight) in enumerate(zip(nodes,weights)):
        path=out/f'mode_{i:03d}.npz';meta=path.with_suffix('.json')
        if path.exists() and meta.exists():
            detail=read(meta);assert sha(path)==detail['field_sha256'];field=np.load(path)['field']
        else:
            if i<32:field,detail=model.solve(q,complex(*d['epsilon']),ports['sources'],ports['receivers'],(2,))
            else:
                source=base/path.name;detail=read(source.with_suffix('.json'));assert sha(source)==detail['field_sha256']
                field=np.load(source)['field'][ri,:,si*3+2,None]
                detail=dict(detail,source_mode_sha256=sha(source),source_mode=str(source.relative_to(root)),selection=dict(receivers=ri,column=si*3+2))
            assert field.shape==(len(ri),3,1) and np.isfinite(field).all() and detail['linear_residual']<1e-9
            np.savez_compressed(path,field=field);detail['field_sha256']=sha(path);save(meta,detail)
        assert detail['ppw']==cfg['mode_resolutions'][i];metadata.append(detail)
        term=field.copy()
        for axis in range(3):term[:,axis,0]*=weight/np.pi*(1j*np.sin(q*dz) if axis!=2 else np.cos(q*dz))
        total+=term;terms.append(term)
        print(cfg['label'],'MODE',i+1,'/64',flush=True)
    for j,r in enumerate(d['receivers']):total[j,:,0]+=free_dyadic(d['source'],r)[:,2]
    total*=1.5;terms=1.5*np.array(terms);mask=np.array(d['shadow_mask']);scale=np.linalg.norm(total[mask,0,0])
    result=dict(status='completed',**cfg,nodes=len(nodes),field=np.stack([total.real,total.imag],axis=-1).tolist(),shape=list(total.shape),
       linear_residual=max(v['linear_residual'] for v in metadata),elapsed_seconds=time.perf_counter()-start,
       tail_absolute_sum_relative=float(np.linalg.norm(np.sum(abs(terms[32:,mask,0,0]),axis=0))/scale),
       tail_coherent_relative=float(np.linalg.norm(np.sum(terms[32:,mask,0,0],axis=0))/scale),
       tail_scope='Computed FEM64 tail magnitude, not an a priori bound on the exact continuum tail; independent higher-resolution tail controls are required.')
    save(out/'result.json',result)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('root',type=Path);ap.add_argument('--resolution',type=int,choices=(80,96),required=True);a=ap.parse_args();main(a.root.resolve(),a.resolution)

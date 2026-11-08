"""Research-only finer BIE sweep across all prior holdout-b polarizations."""
import sys,os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np
from dielectric3d_refinement import validate
from dielectric3d_synthesis import run,quadrature
from dielectric3d_bem import VectorWedgeBEM
from investigate_dielectric3d_polarization import read,save,sha

def main(root):
    manifest=root/'work/d3shadow/holdout_b_cases.json';cases=read(manifest)['cases']
    for case in cases:validate(case)
    cfg=read(root/'work/d3pol/holdout_b_fem64q8/config.json');out=root/'work/d3res/bie64_full';out.mkdir(exist_ok=True)
    receipt=dict(status='passed',cases=len(cases),manifest=str(manifest.relative_to(root)),manifest_sha256=sha(manifest),
        scope='Research candidate only; production fixed 16/32 companion remains unchanged.')
    if (out/'guard.json').exists():assert read(out/'guard.json')==receipt
    else:save(out/'guard.json',receipt)
    # Independent modal operators have no shared mutable solution state. Three
    # bounded workers accelerate the dense BIE sweep, after the large FEM jobs.
    # The authoritative synthesis below still verifies every saved mode.
    assert os.environ.get('OPENBLAS_NUM_THREADS')=='1'
    params=dict(method='bem',resolution=64,epsilon=cfg['epsilon'],order=8,contour=.5,qmax=24.,core=3.,tail=3.,inner=2.5,pml=1.5,boundary='dielectric',ports=cfg['ports'])
    params['source_hashes']={n:sha(Path(__file__).with_name(n)) for n in ('dielectric3d_synthesis.py','dielectric3d_bem.py')}
    if (out/'config.json').exists():assert read(out/'config.json')==params
    else:save(out/'config.json',params)
    execution=dict(workers=3,blas_threads=1,source_sha256=sha(Path(__file__)),mode_arithmetic_changed=False)
    if (out/'execution.json').exists():assert read(out/'execution.json')==execution
    else:save(out/'execution.json',execution)
    nodes,_=quadrature(8)
    def one(i):
        p=out/f'mode_{i:03d}.npz';m=p.with_suffix('.json')
        if p.exists() and m.exists():assert sha(p)==read(m)['field_sha256'];return
        model=VectorWedgeBEM(64);field,meta=model.solve(nodes[i],complex(*cfg['epsilon']),cfg['ports']['sources'],cfg['ports']['receivers'],cfg['ports']['axes'])
        assert np.isfinite(field).all() and meta['linear_residual']<1e-9
        np.savez_compressed(p,field=field);meta['field_sha256']=sha(p);save(m,meta)
        print('BIE64 COMPLETE',i,round(meta['seconds'],2),flush=True)
    with ThreadPoolExecutor(max_workers=3) as pool:
        controls=(5,10,20,26)
        for _ in pool.map(one,controls):pass
        d=read(root/'work/d3pol/diagnostics.json')
        ri=[cfg['ports']['receivers'].index(r) for r in d['receivers']];col=cfg['ports']['sources'].index(d['source'])*3+2
        for i in controls:
            old=np.load(root/'work/d3pol/bie64'/f'mode_{i:03d}.npz')['field']
            field=np.load(out/f'mode_{i:03d}.npz')['field'][ri,:,col,None]
            assert np.linalg.norm(field-old)/np.linalg.norm(old)<1e-9
        for _ in pool.map(one,[i for i in range(64) if i not in controls]):pass
    run(out,method='bem',resolution=64,epsilon=complex(*cfg['epsilon']),order=8,ports=cfg['ports'])

if __name__=='__main__':main(Path(sys.argv[1]).resolve())

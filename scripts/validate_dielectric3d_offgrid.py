"""Analytic Maxwell controls at genuinely off-grid receiver positions."""
import sys
from pathlib import Path
import numpy as np
from dielectric3d_bounded_solver import activate
from dielectric3d_sampling_audit import SamplingAuditFEM
from dielectric3d_plane import reflected
from investigate_dielectric3d_polarization import read,save,sha
from analyze_dielectric3d import rel,pairs,z

def main(root):
    w=root/'work/d3res';policy=activate();d=read(root/'work/d3pol/diagnostics.json');eps=complex(*d['epsilon']);source=d['source'];rs=[[-.87,-1.13,.7],[-.47,1.37,.7]]
    cfg=dict(epsilon=d['epsilon'],source=source,receivers=rs,resolutions=[64,96,128],q=[[1.525532409916329,.4977669015873694],[4.9,.5]],policy=policy,
        sources={n:sha(Path(__file__).with_name(n)) for n in ('dielectric3d_fem.py','dielectric3d_sampling_audit.py','dielectric3d_plane.py','dielectric3d_bounded_solver.py','validate_dielectric3d_offgrid.py')},
        acceptance=dict(finest_vector_error=.002,finest_zx_error=.005,require_contracting_vector_error=True,linear_residual=1e-9))
    out=w/'offgrid';out.mkdir(exist_ok=True)
    if (out/'config.json').exists():assert read(out/'config.json')==cfg
    else:save(out/'config.json',cfg)
    rows=[]
    for qi,qpair in enumerate(cfg['q']):
        q=complex(*qpair);exact=[];quad=[]
        for r in rs:v,e=reflected(q,eps,source,r);exact.append(v);quad.append(e)
        exact=np.array(exact);levels=[]
        for n in cfg['resolutions']:
            for r in rs:assert not np.allclose(np.asarray(r[:2])*n,np.rint(np.asarray(r[:2])*n),atol=1e-6)
            p=out/f'q{qi}_fem{n}.json'
            if p.exists():level=read(p);assert level['config_sha256']==sha(out/'config.json')
            else:
                model=SamplingAuditFEM(n,geometry='halfspace');v,meta=model.solve(q,eps,[source],rs,(0,1,2));cube=model.cubic_field;assert meta['linear_residual']<1e-9
                level=dict(resolution=n,original_error=rel(v,exact),original_zx_error=rel(v[:,0,2],exact[:,0,2]),cubic_error=rel(cube,exact),cubic_zx_error=rel(cube[:,0,2],exact[:,0,2]),original=pairs(v),cubic=pairs(cube),metadata=meta,config_sha256=sha(out/'config.json'));save(p,level)
            levels.append(level);print('OFFGRID',qi,n,level['original_error'],level['cubic_error'],flush=True)
        rows.append(dict(q=qpair,exact=pairs(exact),quadrature_error=quad,levels=levels))
    passed=all(row['levels'][-1]['original_error']<.002 and row['levels'][-1]['original_zx_error']<.005 and all(a['original_error']>b['original_error'] for a,b in zip(row['levels'],row['levels'][1:])) for row in rows)
    result=dict(status='passed' if passed else 'failed',config=cfg,planes=rows,scope='Independent off-grid planar-interface controls. No claim of a rigorous corner-error bound.');save(w/'offgrid_validation.json',result);assert passed

if __name__=='__main__':main(Path(sys.argv[1]).resolve())

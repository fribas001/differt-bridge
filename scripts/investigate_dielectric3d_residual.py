"""Frozen follow-up plan and same-equation reference solver pilot."""
import argparse,json,time
from pathlib import Path
import numpy as np
from investigate_dielectric3d_polarization import read,save,sha
from dielectric3d_synthesis import quadrature
from dielectric3d_fem import VectorWedgeFEM

def setup(root):
    work=root/'work/d3res';work.mkdir(exist_ok=True);scripts=Path(__file__).parent
    prior=root/'outputs/differt-bridge/examples/dielectric3d_polarization';assert read(prior/'verification.json')['status']=='passed'
    plan=dict(status='frozen_before_new_reference_results',target='holdout_b_s0_zx_h0.7',baseline=read(prior/'analysis.json')['target']['series'][-1]['companion'],
        controls=['Validate exact interface Schur solve against saved direct FEM64 and FEM96 fields, including difficult and tail modes.',
            'If equivalence and resource checks pass, refine target to FEM112 and FEM128 below real(q)=7; retain audited FEM64 tail.',
            'Evaluate the full BIE64 target synthesis and fixed 2*BIE64-BIE32 candidate without fitted coefficients.',
            'Use fresh analytic halfspace and vacuum controls; assess mesh convergence independently of BIE.',
            'Inspect remaining spatial sampling error separately; accept no reference method solely on agreement with the companion.',
            'Fresh runtime/Blender checks and preserved installed-file, old-media and production hashes.'],
        acceptance=['Record failed candidates and every tested refinement, including worsening agreement.',
            'Residual <1e-9 in the original Maxwell system; same-equation fields within 1e-8 of direct solves.',
            'Do not alter installed runtimes or native UTD physics; keep production fixed unless independent generalization evidence supports a change.',
            'Explicitly identify all mixed-resolution references and numerical uncertainty.'],
        sources={p.name:sha(p) for p in scripts.glob('dielectric3d_*.py') if p.name!='dielectric3d_interface_solver.py'},
        prior_files={str(p.relative_to(root)):sha(p) for p in prior.rglob('*') if p.is_file()},
        production=read(root/'work/d3pol/production_baseline.json'))
    f=work/'plan.json'
    if f.exists():
        frozen=read(f)
        for key in plan:
            if key!='sources':assert frozen[key]==plan[key],key
        for name,digest in frozen['sources'].items():assert sha(scripts/name)==digest,name
    else:save(f,plan)

def pilot(root,resolution,indices,solver):
    if solver=='nested':from dielectric3d_nested_solver import activate,policy
    else:from dielectric3d_interface_solver import activate,policy
    records=activate();w=root/'work/d3res';d=read(root/'work/d3pol/diagnostics.json');nodes,_=quadrature(8)
    folder=w/f'{solver}{resolution}';folder.mkdir(exist_ok=True)
    cfg=dict(resolution=resolution,indices=indices,policy=policy(),epsilon=d['epsilon'],source=d['source'],receivers=d['receivers'],fem_sha256=sha(Path(__file__).with_name('dielectric3d_fem.py')))
    if (folder/'config.json').exists():assert read(folder/'config.json')==cfg
    else:save(folder/'config.json',cfg)
    model=VectorWedgeFEM(resolution);rows=[]
    for i in indices:
        path=folder/f'mode_{i:03d}.npz';meta=path.with_suffix('.json')
        if path.exists() and meta.exists():field=np.load(path)['field'];detail=read(meta);assert sha(path)==detail['field_sha256']
        else:
            field,detail=model.solve(nodes[i],complex(*d['epsilon']),[d['source']],d['receivers'],(2,))
            detail['interface_solver']=records[-1];detail['policy']=policy();assert detail['linear_residual']<1e-9
            np.savez_compressed(path,field=field);detail['field_sha256']=sha(path);save(meta,detail)
        if resolution==64:
            base=root/'work/d3pol/holdout_b_fem64q8';ports=read(base/'config.json')['ports'];ri=[ports['receivers'].index(r) for r in d['receivers']]
            old=np.load(base/path.name)['field'][ri,:,ports['sources'].index(d['source'])*3+2,None]
        else:
            base=root/'work/d3pol/target_fem96q8_lowmem';old=np.load(base/path.name)['field']
            assert read((base/path.name).with_suffix('.json'))['ppw']==resolution
        error=float(np.linalg.norm(field-old)/np.linalg.norm(old));assert error<1e-8,error
        rows.append(dict(index=i,error=error,metadata=detail,baseline_sha256=sha(base/path.name)))
        print('INTERFACE',resolution,i,'error',error,'seconds',detail['seconds'],'iterations',detail['interface_solver']['rhs'],flush=True)
    save(folder/'validation.json',dict(status='passed',config=cfg,rows=rows))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('root',type=Path);ap.add_argument('action',choices=['setup','pilot']);ap.add_argument('--resolution',type=int,default=64);ap.add_argument('--modes',default='0,5,20,26,29,32,40');ap.add_argument('--solver',choices=['interface','nested'],default='interface');a=ap.parse_args()
    if a.action=='setup':setup(a.root.resolve())
    else:pilot(a.root.resolve(),a.resolution,[int(x) for x in a.modes.split(',')],a.solver)

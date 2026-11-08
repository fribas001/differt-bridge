"""Reference-first audit of the remaining crossed-polarization discrepancy.

No production solver is changed by this script. Fields are checked against
their saved hashes before modal differences or synthesis are evaluated.
"""
import argparse, hashlib, json
from pathlib import Path
import numpy as np
from analyze_dielectric3d import read, z, pairs, metrics, rel
from dielectric3d_synthesis import run, quadrature
from dielectric3d_refinement import electric_free

TARGET = 'holdout_b_s0_zx_h0.7'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p, v): p.write_text(json.dumps(v, indent=2, allow_nan=False), encoding='utf-8')

def setup(root):
    w=root/'work/d3pol';w.mkdir(exist_ok=True)
    rows=read(root/'work/d3weak/analysis.json')['comparisons']
    row=next(r for r in rows if r['engine']=='sionna' and r['name']==TARGET)
    scripts=Path(__file__).parent
    plan=dict(status='reference_first_plan_frozen',target=TARGET,
        baseline_shadow_rms=row['shadow_refined']['complex_rms'],
        baseline_reference_change=row['reference_shadow_change']['complex_rms'],
        production_change=False,
        planned_controls=['Full holdout-b FEM64 at order8, all polarizations and both source positions.',
          'Target source FEM80 and FEM96 at order8; independent spatial refinement.',
          'Target source FEM48/order12, separating quadrature from mesh changes.',
          'Selected dominant modes: FEM domain/absorber and BIE resolution controls.',
          'Refine holdout-a reference independently to audit the second-largest residual.'],
        acceptance=['Report all reference refinements and any non-monotonic results.',
          'No fitted channel gains, phase adjustments or reference lookup in product.',
          'Change production only if independent refined-reference and regression evidence support it.',
          'Preserve original installed runtime, extension and obstacle guard hashes.',
          'Both engine batches and both Blender workflows must pass.'],
        source_hashes={p.name:sha(p) for p in scripts.glob('dielectric3d_*.py')},
        prior_artifacts={str(p.relative_to(root)):sha(p) for p in (root/'outputs/differt-bridge/examples/dielectric3d_weak').iterdir() if p.suffix in ('.mp4','.zip')},
        row=row)
    path=w/'study_plan.json'
    if path.exists():
        frozen=read(path)
        # Later reference-only helpers have their own recorded addenda. Their
        # addition must not rewrite this original pre-refinement plan.
        for key in plan:
            if key!='source_hashes':assert frozen[key]==plan[key],key
        for name,digest in frozen['source_hashes'].items():assert sha(scripts/name)==digest,name
    else: save(path,plan)
    diagnose(root)

def diagnose(root):
    w=root/'work/d3pol';r=read(w/'study_plan.json')['row'];old=root/'work/d3shadow'
    cfg=read(old/'holdout_b_standard_product_modes/group_00/config.json')
    si=cfg['sources'].index(r['tx']);ri=[cfg['receivers'].index(v) for v in r['receivers']]
    nodes,weights=quadrature(8);mask=np.array(r['shadow_mask']);dz=np.array(r['receivers'])[:,2]-r['tx'][2]
    modes={};terms={}
    folders=dict(bie16=root/'work/d3weak/holdout_b_converged_modes/coarse16/group_00',
       bie32=old/'holdout_b_standard_product_modes/group_00',fem32=old/'holdout_b_fem32',fem48=old/'holdout_b_fem48')
    for label,folder in folders.items():
        vals=[]
        for i in range(len(nodes)):
            f=folder/f'mode_{i:03d}.npz';assert sha(f)==read(f.with_suffix('.json'))['field_sha256']
            vals.append(np.load(f)['field'][ri,0,si*3+2])
        modes[label]=np.array(vals)
    modes['converged']=2*modes['bie32']-modes['bie16']
    for label,mm in modes.items():terms[label]=1.5*weights[:,None]/np.pi*1j*np.sin(nodes[:,None]*dz)*mm
    free=np.array([1.5*electric_free(r['tx'],v)[0,2] for v in r['receivers']]);total={k:free+v.sum(axis=0) for k,v in terms.items()}
    assert np.allclose(total['converged'],z(r['field']),rtol=1e-10,atol=1e-13)
    err=terms['converged']-terms['fem48'];ranking=np.argsort(np.linalg.norm(err[:,mask],axis=1))[::-1]
    result=dict(status='completed',target=TARGET,source=r['tx'],receivers=r['receivers'],epsilon=cfg['epsilon'],
       shadow_mask=r['shadow_mask'],angles=r['study']['angles'],free=pairs(free),
       totals={k:pairs(v) for k,v in total.items()},
       cancellation_ratio=((abs(free)+np.sum(abs(terms['fem48']),axis=0))/abs(total['fem48'])).tolist(),
       modes=[dict(index=int(i),q=pairs(nodes[i]),error_norm=float(np.linalg.norm(err[i,mask])),
          reference_change_norm=float(np.linalg.norm((terms['fem32']-terms['fem48'])[i,mask])),
          fields={k:pairs(mm[i]) for k,mm in modes.items()}) for i in ranking],
       intervals=[dict(q_range=[a,b],error_norm=float(np.linalg.norm(err[j*8:(j+1)*8,mask].sum(axis=0)))) for j,(a,b) in enumerate(zip([0,2,4,5.5,7,9,12,16],[2,4,5.5,7,9,12,16,24]))])
    save(w/'diagnostics.json',result)
    print('Dominant modes',[(v['index'],v['error_norm'],v['reference_change_norm']) for v in result['modes'][:8]],flush=True)

def reference(root,resolution,order,material,target_only,inner,pml):
    w=root/'work/d3pol';cfg=read(root/f'work/d3shadow/{material}_fem48/config.json')
    ports=cfg['ports']
    if target_only:
        d=read(w/'diagnostics.json');ports=dict(sources=[d['source']],receivers=d['receivers'],axes=[2])
    label=f'{"target" if target_only else material}_fem{resolution}q{order}'
    if inner!=2.5 or pml!=1.5:label+=f'_inner{inner:g}_pml{pml:g}'
    run(w/label,method='fem',resolution=resolution,epsilon=complex(*cfg['epsilon']),order=order,ports=ports,inner=inner,pml=pml)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('root',type=Path);ap.add_argument('action',choices=['setup','reference']);ap.add_argument('--resolution',type=int,default=64);ap.add_argument('--order',type=int,default=8);ap.add_argument('--material',default='holdout_b');ap.add_argument('--target-only',action='store_true');ap.add_argument('--inner',type=float,default=2.5);ap.add_argument('--pml',type=float,default=1.5);a=ap.parse_args();root=a.root.resolve()
    if a.action=='setup':setup(root)
    else:reference(root,a.resolution,a.order,a.material,a.target_only,a.inner,a.pml)

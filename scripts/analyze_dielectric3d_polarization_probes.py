"""Independent nuisance controls and BIE self-convergence, without fitting."""
import sys
from pathlib import Path
import numpy as np
from analyze_dielectric3d import read,z,pairs,rel
from investigate_dielectric3d_polarization import save,sha
from dielectric3d_synthesis import quadrature

def main(root):
    w=root/'work/d3pol';d=read(w/'diagnostics.json');mask=np.array(d['shadow_mask']);rows=[];nodes,weights=quadrature(8)
    def get(label,i):
        folder=w/label;f=folder/f'mode_{i:03d}.npz';assert sha(f)==read(f.with_suffix('.json'))['field_sha256'];v=np.load(f)['field']
        cfg=read(folder/'config.json')
        if 'ports' in cfg and cfg['ports']['axes']==[0,1,2]:
            ri=[cfg['ports']['receivers'].index(r) for r in d['receivers']];col=cfg['ports']['sources'].index(d['source'])*3+2;return v[ri,0,col]
        return v[:,0,0]
    for i in (5,10,20,26):
        m=next(v for v in d['modes'] if v['index']==i);values={k:z(v) for k,v in m['fields'].items()}
        for label in ('holdout_b_fem64q8','target_fem80q8_lowmem','target_fem96q8_lowmem','bie64','bie32quad24','fem48domain','fem48pml'):
            values[label]=get(label,i)
        reference=values['target_fem96q8_lowmem'];rich64=2*values['bie64']-values['bie32']
        rows.append(dict(index=i,q=m['q'],fields={k:pairs(v) for k,v in values.items()},
           errors={k:rel(v[mask],reference[mask]) for k,v in values.items()},
           finer_bie_extrapolation=rel(rich64[mask],reference[mask]),
           bie_extrapolation_change=rel(rich64[mask],values['converged'][mask]),
           domain_change=rel(values['fem48domain'][mask],values['fem48'][mask]),
           pml_change=rel(values['fem48pml'][mask],values['fem48'][mask]),
           panel_quadrature_change=rel(values['bie32quad24'][mask],values['bie32'][mask])))
    tails=[];scale=np.linalg.norm(z(read(w/'target_fem96q8_lowmem/result.json')['field'])[mask,0,0]);dz=np.array(d['receivers'])[:,2]-d['source'][2]
    for i in (32,40):
        a=get('fem96tail',i);b=get('holdout_b_fem64q8',i);factor=1.5*weights[i]/np.pi*1j*np.sin(nodes[i]*dz)
        tails.append(dict(index=i,q=pairs(nodes[i]),relative_modal_change=rel(a[mask],b[mask]),
            weighted_change_relative_to_total=float(np.linalg.norm((factor*(a-b))[mask])/scale),
            fine_weighted_magnitude_relative_to_total=float(np.linalg.norm((factor*a)[mask])/scale)))
    passed=max(v['domain_change'] for v in rows)<.001 and max(v['pml_change'] for v in rows)<.001 and max(v['panel_quadrature_change'] for v in rows)<.001 and max(v['weighted_change_relative_to_total'] for v in tails)<1e-5
    result=dict(status='passed' if passed else 'failed',rows=rows,tail_controls=tails,
      scope='Selected modal sensitivities, not certified physical error bounds. Finer BIE extrapolation is a diagnostic only; production remains fixed 16/32.')
    save(w/'probe_analysis.json',result);print('PROBES',result['status'],flush=True)
    assert passed

if __name__=='__main__':main(Path(sys.argv[1]).resolve())

"""Exact Fourier-z reuse at every existing height for the same source/axis.

This does not create new volume solves. The unchanged z-invariant modal FEM
samples x/y only; z dependence is restored by its declared Fourier factor.
Validate every reused mode and the complete synthesis against the earlier
all-height FEM64 calculation before deriving the finer-height references.
"""
import sys
from pathlib import Path
import numpy as np
from investigate_dielectric3d_polarization import read,save,sha
from dielectric3d_synthesis import quadrature
from maxwell3d_pec_reference import free_dyadic
from analyze_dielectric3d import z,pairs,rel

def synthesize(nodes,weights,modal,source,receivers):
    total=np.zeros((len(receivers),3,1),complex);dz=np.asarray(receivers)[:,2]-source[2]
    for q,weight,field in zip(nodes,weights,modal):
        for axis in range(3):total[:,axis,0]+=weight/np.pi*(1j*np.sin(q*dz) if axis!=2 else np.cos(q*dz))*field[:,axis,0]
    for j,r in enumerate(receivers):total[j,:,0]+=free_dyadic(source,r)[:,2]
    return total*1.5

def prepare(root):
    w=root/'work/d3res';base=root/'work/d3pol/holdout_b_fem64q8';bc=read(base/'config.json');d=read(root/'work/d3pol/diagnostics.json')
    ports=dict(sources=[d['source']],receivers=bc['ports']['receivers'],axes=[2]);xy=[r[:2] for r in d['receivers']]
    assert len(xy)==len(set(map(tuple,xy)));indices=[xy.index(r[:2]) for r in ports['receivers']]
    plan=dict(status='declared_before_fine_height_results',ports=ports,receiver_indices=indices,
        source_sha256=sha(Path(__file__)),original_config_sha256=sha(base/'config.json'),
        rationale='Use all existing receiver heights for the same transmitter and z polarization. Fourier modal fields depend on x/y, not receiver z. No new volume solves or arbitrary finite-object extension is claimed.',
        acceptance=dict(all_64_mode_selections_exact=True,synthesis_relative_error=1e-12,tail_probe_relative_change=1e-5))
    p=w/'height_synthesis_plan.json'
    if p.exists():assert read(p)==plan
    else:save(p,plan)
    nodes,weights=quadrature(8);col=bc['ports']['sources'].index(d['source'])*3+2;ri=[bc['ports']['receivers'].index(r) for r in d['receivers']];modal=[]
    for i in range(64):
        p=base/f'mode_{i:03d}.npz';assert sha(p)==read(p.with_suffix('.json'))['field_sha256']
        field=np.load(p)['field'][:,:,col,None];expanded=field[ri][indices];assert np.array_equal(field,expanded);modal.append(expanded)
    total=synthesize(nodes,weights,modal,d['source'],ports['receivers']);old=z(read(base/'result.json')['field'])[:,:,col,None];error=rel(total,old);assert error<1e-12
    save(w/'height_synthesis_validation.json',dict(status='passed',mode_selections_exact=64,synthesis_relative_error=error,config_sha256=sha(base/'config.json'),reference_sha256=sha(base/'result.json'),plan_sha256=sha(w/'height_synthesis_plan.json')))
    return plan

def derive(root,resolution):
    w=root/'work/d3res';plan=prepare(root);folder=w/f'fem{resolution}_bounded';cfg=read(folder/'config.json');result=read(folder/'result.json');assert result['status']=='completed'
    assert cfg['ports']['sources']==plan['ports']['sources'] and cfg['ports']['axes']==[2]
    nodes,weights=quadrature(8);modal=[]
    for i in range(64):
        p=folder/f'mode_{i:03d}.npz';assert sha(p)==read(p.with_suffix('.json'))['sha256'];modal.append(np.load(p)['field'][plan['receiver_indices']])
    total=synthesize(nodes,weights,modal,cfg['ports']['sources'][0],plan['ports']['receivers'])
    ri=[plan['ports']['receivers'].index(r) for r in cfg['ports']['receivers']];error=rel(total[ri],z(result['field']));assert error<1e-12
    expanded=dict(status='completed',config=dict(ports=plan['ports'],epsilon=cfg['epsilon'],resolution=resolution,order=8,contour=.5,qmax=24.),field=pairs(total),
        source_result_sha256=sha(folder/'result.json'),source_config_sha256=sha(folder/'config.json'),plan_sha256=sha(w/'height_synthesis_plan.json'),
        original_height_reconstruction_error=error,scope='Exact Fourier-z reweighting of existing modes at prior benchmark heights; no additional volume solves.')
    save(w/f'fem{resolution}_heights.json',expanded);return expanded

if __name__=='__main__':prepare(Path(sys.argv[1]).resolve());print('HEIGHT_RECONSTRUCTION_VALIDATED',flush=True)

"""Further independent spatial refinement with paired field-recovery audits."""
import argparse,ctypes,time
from pathlib import Path
import numpy as np
from dielectric3d_sampling_audit import SamplingAuditFEM
from dielectric3d_synthesis import quadrature
from maxwell3d_pec_reference import free_dyadic
from investigate_dielectric3d_polarization import read,save,sha
from analyze_dielectric3d import pairs

def memory():
    class Counters(ctypes.Structure):
        _fields_=[('cb',ctypes.c_ulong),('faults',ctypes.c_ulong),*[(s,ctypes.c_size_t) for s in ('peak_working_set','working_set','peak_paged_pool','paged_pool','peak_nonpaged_pool','nonpaged_pool','pagefile','peak_pagefile','private')]]
    c=Counters();c.cb=ctypes.sizeof(c)
    current=ctypes.windll.kernel32.GetCurrentProcess;current.restype=ctypes.c_void_p
    get=ctypes.windll.psapi.GetProcessMemoryInfo;get.argtypes=[ctypes.c_void_p,ctypes.POINTER(Counters),ctypes.c_ulong];get.restype=ctypes.c_int
    assert get(current(),ctypes.byref(c),c.cb)
    return dict(peak_working_set_bytes=c.peak_working_set,working_set_bytes=c.working_set,private_bytes=c.private)

def main(root,resolution,solver,modes):
    w=root/'work/d3res';d=read(root/'work/d3pol/diagnostics.json');base=root/'work/d3pol/holdout_b_fem64q8';bc=read(base/'config.json');records=[]
    if solver=='direct':
        from dielectric3d_fem_linear_solver import activate
        policy=activate();assert policy==read(root/'work/d3pol/linear_solver_validation.json')['policy'];names=['dielectric3d_fem_linear_solver.py']
    else:
        from dielectric3d_nested_solver import activate,policy as get_policy
        records=activate();policy=get_policy();names=['dielectric3d_nested_solver.py','dielectric3d_interface_solver.py']
        for n in (64,96):assert read(w/f'nested{n}/validation.json')['status']=='passed'
    ports=dict(sources=[d['source']],receivers=d['receivers'],axes=[2]);ri=[bc['ports']['receivers'].index(r) for r in d['receivers']];col=bc['ports']['sources'].index(d['source'])*3+2
    cfg=dict(resolution=resolution,solver=solver,policy=policy,order=8,contour=.5,qmax=24.,inner=2.5,pml=1.5,epsilon=d['epsilon'],ports=ports,
        mode_resolutions=[resolution]*32+[64]*32,tail=dict(folder=str(base.relative_to(root)),config_sha256=sha(base/'config.json'),receivers=ri,column=col),
        recovery='Paired original bilinear/central-gradient and cubic vacuum-stencil fields; common original FEM64 tail',
        sources={n:sha(Path(__file__).with_name(n)) for n in names+['dielectric3d_fem.py','dielectric3d_sampling_audit.py','dielectric3d_synthesis.py','run_dielectric3d_residual_reference.py']})
    out=w/f'fem{resolution}_{solver}';out.mkdir(exist_ok=True)
    if (out/'config.json').exists():assert read(out/'config.json')==cfg
    else:save(out/'config.json',cfg)
    model=SamplingAuditFEM(resolution);nodes,weights=quadrature(8);indices=range(64) if modes is None else modes
    for i in indices:
        p=out/f'mode_{i:03d}.npz';m=p.with_suffix('.json')
        if p.exists() and m.exists():assert sha(p)==read(m)['sha256']
        else:
            if i<32:
                f,meta=model.solve(nodes[i],complex(*d['epsilon']),[d['source']],d['receivers'],(2,));c=model.cubic_field
                if records:meta['interface_solver']=records[-1]
                meta['process_memory']=memory()
            else:
                source=base/p.name;detail=read(source.with_suffix('.json'));assert sha(source)==detail['field_sha256']
                f=np.load(source)['field'][ri,:,col,None];c=f.copy();meta=dict(detail,source_mode=str(source.relative_to(root)),source_sha256=sha(source),common_tail=True)
            assert np.isfinite(f).all() and np.isfinite(c).all() and meta['linear_residual']<1e-9
            np.savez_compressed(p,field=f,cubic=c);meta['sha256']=sha(p);save(m,meta)
        print('REFERENCE',resolution,solver,i+1,'/64',flush=True)
    if not all((out/f'mode_{i:03d}.json').exists() for i in range(64)):
        save(out/'partial.json',dict(status='partial',completed=len(list(out.glob('mode_*.npz')))));return
    total={key:np.zeros((len(ri),3,1),complex) for key in ('field','cubic')};dz=np.asarray(d['receivers'])[:,2]-d['source'][2];details=[]
    for i,(q,weight) in enumerate(zip(nodes,weights)):
        p=out/f'mode_{i:03d}.npz';meta=read(p.with_suffix('.json'));assert sha(p)==meta['sha256'];details.append(meta)
        with np.load(p) as archive:
            for key in total:
                f=archive[key]
                for axis in range(3):total[key][:,axis,0]+=weight/np.pi*(1j*np.sin(q*dz) if axis!=2 else np.cos(q*dz))*f[:,axis,0]
    for key in total:
        for j,r in enumerate(d['receivers']):total[key][j,:,0]+=free_dyadic(d['source'],r)[:,2]
        total[key]*=1.5
    save(out/'result.json',dict(status='completed',config=cfg,field=pairs(total['field']),cubic=pairs(total['cubic']),
        maximum_linear_residual=max(v['linear_residual'] for v in details),maximum_peak_working_set_bytes=max(v.get('process_memory',{}).get('peak_working_set_bytes',0) for v in details)))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--resolution',type=int,required=True);p.add_argument('--solver',choices=['direct','nested'],default='direct');p.add_argument('--modes');a=p.parse_args()
    main(a.root.resolve(),a.resolution,a.solver,[int(i) for i in a.modes.split(',')] if a.modes else None)

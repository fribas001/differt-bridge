"""Localize the weak y-to-z error using archived independent Fourier modes."""
import hashlib,json,sys
from pathlib import Path
import numpy as np
from dielectric3d_refinement import spectral_quadrature,electric_free
from analyze_dielectric3d import read,z,pairs,rel

def main(root):
    work=root/'work/d3weak';work.mkdir(parents=True,exist_ok=True)
    old=root/'work/d3shadow';cfg=read(old/'holdout_b_standard_product_modes/group_00/config.json')
    cases=read(old/'holdout_b_cases.json')['cases'];case=next(c for c in cases if c['name']=='holdout_b_s1_yz_h0.7')
    source=case['tx'];si=cfg['sources'].index(source);angles=np.array(case['study']['angles']);sel=np.where(angles>251.27)[0]
    receivers=[case['receivers'][i] for i in sel];ri=[cfg['receivers'].index(r) for r in receivers]
    nodes,weights=spectral_quadrature();dz=np.array(receivers)[:,2]-source[2]
    terms={};modes={}
    for label,folder in [('bie32',old/'holdout_b_standard_product_modes/group_00'),('fem32',old/'holdout_b_fem32'),('fem48',old/'holdout_b_fem48')]:
        mm=[];tt=[]
        for i,(q,w) in enumerate(zip(nodes,weights)):
            f=folder/f'mode_{i:03d}.npz';meta=read(f.with_suffix('.json'));assert hashlib.sha256(f.read_bytes()).hexdigest()==meta['field_sha256']
            v=np.load(f)['field'][ri,2,si*3+1];mm.append(v);tt.append(1.5*w/np.pi*1j*np.sin(q*dz)*v)
        modes[label]=np.array(mm);terms[label]=np.array(tt)
    free=np.array([1.5*electric_free(source,r)[2,1] for r in receivers]);total={k:free+v.sum(axis=0) for k,v in terms.items()}
    error=terms['bie32']-terms['fem48'];ranking=np.argsort(np.linalg.norm(error,axis=1))[::-1]
    result=dict(status='completed',case=case['name'],source=source,receivers=receivers,angles=angles[sel].tolist(),epsilon=cfg['epsilon'],
        free=pairs(free),total={k:pairs(v) for k,v in total.items()},baseline_rms=rel(total['bie32'],total['fem48']),reference_refinement=rel(total['fem32'],total['fem48']),
        cancellation_ratio=(abs(free)+np.sum(abs(terms['fem48']),axis=0))/abs(total['fem48']),
        intervals=[dict(q_range=[a,b],error_norm=float(np.linalg.norm(error[i*8:(i+1)*8].sum(axis=0))),error=pairs(error[i*8:(i+1)*8].sum(axis=0))) for i,(a,b) in enumerate(zip([0,2,4,5.5,7,9,12,16],[2,4,5.5,7,9,12,16,24]))],
        modes=[dict(index=int(i),q=[nodes[i].real,nodes[i].imag],error_norm=float(np.linalg.norm(error[i])),bie=pairs(modes['bie32'][i]),fem=pairs(modes['fem48'][i]),fem_mesh_change=float(np.linalg.norm(modes['fem32'][i]-modes['fem48'][i]))) for i in ranking])
    result['cancellation_ratio']=result['cancellation_ratio'].tolist()
    (work/'diagnostics.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('total','free','modes')}));print('Largest modes:',[(m['index'],m['q'],m['error_norm']) for m in result['modes'][:8]])

if __name__=='__main__':main(Path(sys.argv[1]).resolve())

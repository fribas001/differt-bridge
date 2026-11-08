"""Archive every resolution, quadrature and absorbing-boundary control."""
import json,sys
from pathlib import Path
import numpy as np
from analyze_dielectric3d import read,z,rel

def main(root):
    w=root/'work/d3weak';d=read(w/'diagnostics.json');mm={m['index']:m for m in d['modes']};rows=[]
    for i in (5,11,20,26):
        reference=np.load(w/'fem64'/f'mode_{i:03d}.npz')['field'][:,2,0];v={'bie32':z(mm[i]['bie'])}
        for label in ('bie16','bie24','bie48','bie64','bie32quad24','bie32core5','bie32tail5'):v[label]=np.load(w/label/f'mode_{i:03d}.npz')['field'][:,2,0]
        for a,b in ((16,32),(24,48),(32,64)):v[f'rich{a}_{b}']=2*v[f'bie{b}']-v[f'bie{a}']
        rows.append(dict(index=i,q=mm[i]['q'],relative_errors={k:rel(a,reference) for k,a in v.items()},self_convergence_order=float(np.log2(np.linalg.norm(v['bie16']-v['bie32'])/np.linalg.norm(v['bie32']-v['bie64']))),quadrature_change=rel(v['bie32quad24'],v['bie32']),core_change=rel(v['bie32core5'],v['bie32']),tail_change=rel(v['bie32tail5'],v['bie32'])))
    result=dict(status='completed',rows=rows,scope='Four preselected representative propagating modes; first-order behavior is strongest in dominant low-q modes, not a uniform asymptotic proof. Every extrapolation uses fixed weights from the resolution ratio, never a fit to FEM.')
    (w/'probe_analysis.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))

if __name__=='__main__':main(Path(sys.argv[1]).resolve())

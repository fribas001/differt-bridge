"""Independent enlarged-domain FEM control at four selected weak-port modes."""
import json,sys
from pathlib import Path
import numpy as np
from analyze_dielectric3d import read,z,rel

def main(root):
    w=root/'work/d3weak';d=read(w/'diagnostics.json');m={r['index']:r for r in d['modes']};rows=[]
    for i in (5,11,20,26):
        f=np.load(w/'fem48domain'/f'mode_{i:03d}.npz')['field'][:,2,0];rows.append(dict(index=i,q=m[i]['q'],relative_mode_change=rel(f,z(m[i]['fem']))))
    result=dict(status='passed' if max(r['relative_mode_change'] for r in rows)<.005 else 'failed',rows=rows,scope='FEM48 unstretched half-domain enlarged from 2.5 to 3.5 wavelengths; PML thickness, strength, q, material and dipole ports unchanged. Four representative modes, not a complete field-error bound.',diagnostic_limit=.005)
    (w/'domain_validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
    if result['status']!='passed':raise SystemExit('Independent reference domain sensitivity needs investigation')

if __name__=='__main__':main(Path(sys.argv[1]).resolve())

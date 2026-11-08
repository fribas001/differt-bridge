"""Unfitted first-order spatial extrapolation of the scoped Maxwell companion.

For F(h)=F(0)+c*h+..., 2 F(h)-F(2h) cancels the leading term.
Both fields come from the same BIE equations. No FEM field, learned coefficient,
completed-channel reciprocity projection or geometry filtering is involved.
"""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from dielectric3d_refinement import refine,validate

def source_hashes():
    return {n:hashlib.sha256(Path(__file__).with_name(n).read_bytes()).hexdigest() for n in ('dielectric3d_converged.py','dielectric3d_refinement.py','dielectric3d_bem.py')}

def combine(coarse,fine):
    assert coarse['status']==fine['status']=='completed'
    assert coarse['panels']==16 and fine['panels']==32 and coarse['order']==fine['order']==8
    assert coarse['source_hashes']==fine['source_hashes']
    assert len(coarse['groups'])==len(fine['groups'])
    for a,b in zip(coarse['groups'],fine['groups']):
        for key in ('epsilon','sources','receivers','order','contour','qmax','source_hashes'):assert a[key]==b[key],key
    a={r['name']:r['field'] for r in coarse['results']};assert len(a)==len(coarse['results'])==len(fine['results'])
    assert set(a)=={r['name'] for r in fine['results']}
    rows=[]
    for r in fine['results']:
        value=2*np.asarray(r['field'])-np.asarray(a[r['name']]);assert np.isfinite(value).all()
        rows.append(dict(name=r['name'],field=value.tolist()))
    return dict(status='completed',mode='optional_3d_dielectric_converged',domain=fine['domain'],reference_used=False,native_exports_modified=False,shared_solver=True,
        scope='Shared full-wave infinite solid dielectric quadrant; fixed 2*BIE32-BIE16 spatial extrapolation. Separate from native UTD and restricted to the existing guarded domain.',
        panels=32,coarse_panels=16,order=8,extrapolation=dict(order=1,weights=[-1.,2.],fitted=False),source_hashes=source_hashes(),groups=fine['groups'],results=rows)

def refine_converged(cases,checkpoint,fine_checkpoint=None,coarse_checkpoint=None):
    for c in cases:validate(c) # Fail closed before creating outputs or starting either solve.
    coarse=refine(cases,coarse_checkpoint or checkpoint/'coarse16',panels=16)
    fine=refine(cases,fine_checkpoint or checkpoint/'fine32',panels=32)
    return combine(coarse,fine)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('manifest',type=Path);ap.add_argument('output',type=Path);ap.add_argument('--fine-checkpoint',type=Path);ap.add_argument('--coarse-checkpoint',type=Path);a=ap.parse_args()
    result=refine_converged(json.loads(a.manifest.read_text(encoding='utf-8'))['cases'],a.output.parent/(a.output.stem+'_modes'),a.fine_checkpoint,a.coarse_checkpoint)
    a.output.write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')

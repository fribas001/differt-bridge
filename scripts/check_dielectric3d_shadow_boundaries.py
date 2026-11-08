"""Diagnostic boundary stencils, without fitting or post-hoc acceptance gates."""
import json,sys
from pathlib import Path
import numpy as np
from analyze_dielectric3d import read,z,rel

def main(root):
    work=root/'work/d3shadow';analysis=read(work/'analysis.json');assert analysis['status']=='passed'
    rows=[]
    for row in analysis['comparisons']:
        if row['campaign']!='holdout':continue
        source=row['tx'];boundary=np.rad2deg((np.arctan2(source[1],source[0])-np.pi/2)%(2*np.pi))+180
        angles=np.array(row['study']['angles']);indices=np.where(abs(angles-boundary)<.011)[0]
        assert len(indices)==3
        ref=z(row['reference'])[indices];field=z(row['field'])[indices];ray=z(row['ray'])[indices]
        scale=max(float(np.linalg.norm(ref)/np.sqrt(3)),1e-12)
        delta_ref=ref[-1]-ref[0]
        rows.append(dict(name=row['name'],engine=row['engine'],angles=angles[indices].tolist(),
            finite=bool(np.isfinite(field).all() and np.isfinite(ray).all()),
            stencil_reference_rms=rel(field,ref),ray_reference_rms=rel(ray,ref),
            reference_span_normalized=float(abs(delta_ref)/scale),
            refined_span_normalized=float(abs(field[-1]-field[0])/scale),
            ray_span_normalized=float(abs(ray[-1]-ray[0])/scale),
            refined_span_error_normalized=float(abs(field[-1]-field[0]-delta_ref)/scale),
            ray_span_error_normalized=float(abs(ray[-1]-ray[0]-delta_ref)/scale),
            reference_rms_amplitude=scale))
    active=[r for r in rows if r['engine']=='sionna' and r['reference_rms_amplitude']>1e-9]
    result=dict(status='passed' if all(r['finite'] for r in rows) else 'failed',rows=rows,
        unique_stencils=len(rows)//2,nonnull_stencils=len(active),
        maximum_refined_stencil_rms=max(r['stencil_reference_rms'] for r in active),
        maximum_refined_span_error=max(r['refined_span_error_normalized'] for r in active),
        maximum_ray_span_error=max(r['ray_span_error_normalized'] for r in active),
        scope='Diagnostic three-point shadow-boundary stencils at +/-0.01 degrees, new materials and positions. Finite values and measured FEM agreement; not a proof of continuity or a fitted boundary correction. Span errors are normalized by the FEM stencil RMS, excluding numerical nulls from aggregate maxima.')
    (work/'boundary_validation.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}))
    if result['status']!='passed':raise SystemExit('Nonfinite boundary field')

if __name__=='__main__':main(Path(sys.argv[1]).resolve())

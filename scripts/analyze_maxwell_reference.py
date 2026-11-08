"""Convergence, analytic controls and independent Maxwell comparison of ray formulas."""
import argparse,json
from pathlib import Path
import numpy as np
from ray_wedge2d import field

read=lambda p:json.loads(p.read_text())
z=lambda a:np.asarray(a)[...,0]+1j*np.asarray(a)[...,1]
pair=lambda a:np.stack([a.real,a.imag],axis=-1).tolist()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('work',type=Path);ap.add_argument('output',type=Path);args=ap.parse_args()
    results=[]
    for file in sorted(args.work.glob('*_80.json')):
        stem=file.stem[:-3];rows={p:read(args.work/(stem+'_'+str(p)+'.json')) for p in (40,60,80)}
        assert all(r['sources']==rows[80]['sources'] and r['receivers']==rows[80]['receivers'] for r in rows.values())
        u={p:z(r['field']) for p,r in rows.items()}
        e1=(60**2*u[60]-40**2*u[40])/(60**2-40**2)
        e2=(80**2*u[80]-60**2*u[60])/(80**2-60**2)
        norm=lambda a:float(np.linalg.norm(a))
        row=dict(name=stem,finest_rms_change=norm(u[80]-u[60])/norm(u[80]),extrapolation_rms_change=norm(e2-e1)/norm(e2),
            observed_difference_ratio=norm(u[60]-u[40])/norm(u[80]-u[60]),max_linear_residual=max(r['linear_residual'] for r in rows.values()),max_reciprocity=max(r['reciprocity_residual'] for r in rows.values()),extrapolated_field=pair(e2),
            scope='Richardson estimates require the observed sequence and analytic/PML controls; not an unconditional error bound.')
        if rows[80]['analytic'] is not None:
            exact=z(rows[80]['analytic']);row['analytic_extrapolation_rms_error']=norm(e2-exact)/norm(exact)
            row['analytic_finest_rms_error']=norm(u[80]-exact)/norm(exact)
        if not stem.startswith('free'):
            epsilon=complex(*rows[80]['epsilon']) if not stem.startswith('pec') else 1-1e12j
            pol=rows[80]['polarization'];comparisons=[]
            for profile in ('sionna-native','differt-native','sionna-kp_depth','sionna-reciprocal'):
                predicted=np.full(e2.shape,np.nan+1j*np.nan);entries=[]
                for i,s in enumerate(rows[80]['sources']):
                    for j,r in enumerate(rows[80]['receivers']):
                        try:value,go,diff=field(s,r,epsilon,pol,profile)
                        except ValueError:continue
                        predicted[i,j]=value
                        entries.append(dict(source=i,receiver=j,predicted=[value.real,value.imag],reference=pair(e2[i,j]),go=[go.real,go.imag],diffracted=[diff.real,diff.imag],exact_face_grazing=any(abs(v)<1e-12 for v in s+r)))
                mask=np.isfinite(predicted);relative=abs(predicted[mask]-e2[mask])/np.maximum(abs(e2[mask]),1e-12)
                gain=20*np.log10(np.maximum(abs(predicted[mask]),1e-20)/np.maximum(abs(e2[mask]),1e-20));phase=np.angle(predicted[mask]/e2[mask])
                nongrazing=np.array([[not any(abs(v)<1e-12 for v in s+r) for r in rows[80]['receivers']] for s in rows[80]['sources']])&mask
                comparisons.append(dict(profile=profile,cases=int(mask.sum()),rms_complex_error=norm(predicted[mask]-e2[mask])/norm(e2[mask]),
                    nongrazing_rms_complex_error=norm(predicted[nongrazing]-e2[nongrazing])/norm(e2[nongrazing]),
                    median_relative_error=float(np.median(relative)),p95_relative_error=float(np.percentile(relative,95)),median_abs_gain_error_db=float(np.median(abs(gain))),p95_abs_gain_error_db=float(np.percentile(abs(gain),95)),p95_abs_phase_error_rad=float(np.percentile(abs(phase),95)),entries=entries))
            row['ray_model_comparisons']=comparisons
        results.append(row)
    args.output.write_text(json.dumps(dict(scope='Independent FDFD Maxwell solutions of an infinite solid right-angle dielectric wedge, broadside Ez and Hz. Thin slab and arbitrary 3D skew accuracy are not established by this reference.',results=results),indent=2,allow_nan=False),encoding='utf-8')
    for row in results:
        print(row['name'],'gridchange',row['finest_rms_change'],'extrapchange',row['extrapolation_rms_change'],'analytic',row.get('analytic_extrapolation_rms_error'))
        for m in row.get('ray_model_comparisons',[]):print(' ',m['profile'],'rms',m['rms_complex_error'],'nongrazing',m['nongrazing_rms_complex_error'],'p95db',m['p95_abs_gain_error_db'])

if __name__=='__main__':main()

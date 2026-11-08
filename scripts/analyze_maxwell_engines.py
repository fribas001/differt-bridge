"""Compare actual engine output, converted ray by ray, against Maxwell fields."""
import argparse,json
from pathlib import Path
import numpy as np
from ray_wedge2d import green,field

def analyze(work,reference,pml):
    read=lambda p:json.loads(p.read_text())
    z=lambda a:np.asarray(a)[...,0]+1j*np.asarray(a)[...,1]
    models={r['name']:r for r in read(reference)['results']}
    cases={c['name']:c for c in read(work/'cases.json')['cases']}
    report=[]
    for receipt in read(work/'receipt.json')['processes']:
        assert receipt['passed']
        profile=receipt['profile'];data=read(work/profile/receipt['output'])
        groups={}
        for row in data['cases']:
            assert row['status']=='completed'
            c=cases[row['name']];meta=c['study'];name=meta['material']+'_'+meta['polarization']
            i=meta['source_index'];ref=z(models[name]['extrapolated_field'])[i]
            sign=1 if meta['polarization']=='Ez' else -1
            for j,rx in enumerate(c['receivers']):
                value=0j;ud=0j;go=0j;count=0
                for path in [p for p in row['paths'] if p['rx']==j]:
                    a=complex(*path['a']);length=path['geometric_length_m']
                    if path['interactions']==[8]:
                        q=np.asarray(path['points'][1]);assert np.linalg.norm(q)<1e-5,'Not the central broadside edge'
                        si=np.linalg.norm(c['tx']);s=np.linalg.norm(rx)
                        v=sign*a*(4*np.pi*np.sqrt(si*s*(si+s)))*green(si)*np.exp(-2j*np.pi*s)/np.sqrt(s)
                        ud+=v;count+=1
                    elif path['interactions'] in ([],[1]):
                        v=sign*a*(4*np.pi*length)*green(length);go+=v
                    else:raise AssertionError('Unexpected ray chain')
                    value+=v
                assert count==1,(profile,c['name'],j,count)
                try:formula=field(c['tx'][:2],rx[:2],complex(*meta['epsilon']),meta['polarization'],profile)[0]
                except ValueError:formula=None
                groups.setdefault(name,[]).append(dict(source=i,receiver=j,reference=[ref[j].real,ref[j].imag],prediction=[value.real,value.imag],formula=[formula.real,formula.imag] if formula is not None else None,go=[go.real,go.imag],diffracted=[ud.real,ud.imag]))
        for name,entries in groups.items():
            a=z([e['prediction'] for e in entries]);b=z([e['reference'] for e in entries]);f=z([e['formula'] or [0,0] for e in entries]);fm=np.array([e['formula'] is not None for e in entries]);go=z([e['go'] for e in entries])
            norm=lambda x:float(np.linalg.norm(x))
            gain=20*np.log10(abs(a/b));phase=np.angle(a/b)
            report.append(dict(profile=profile,material_polarization=name,samples=len(entries),rms_complex_error=norm(a-b)/norm(b),
                rms_scattered_residual_error=norm(a-b)/norm(b-go),formula_rms_difference=norm((a-f)[fm])/norm(f[fm]),formula_samples=int(fm.sum()),
                p95_abs_gain_error_db=float(np.percentile(abs(gain),95)),p95_abs_phase_error_rad=float(np.percentile(abs(phase),95)),entries=entries))
    controls=[]
    for file in sorted(pml.glob('*_60.json')):
        original=read(pml.parent/'maxwell'/file.name);other=read(file)
        u,v=z(original['field']),z(other['field'])
        controls.append(dict(name=file.stem,rms_relative_change=float(np.linalg.norm(u-v)/np.linalg.norm(u))))
    return dict(scope='Actual engine coefficients converted from 3D point-source rays to 2D line-source rays. Independent reference solves Maxwell equations for a homogeneous solid lossy right-angle wedge. This validates that approximation only, not finite slabs or arbitrary 3D accuracy.',comparisons=report,pml_controls=controls)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('work',type=Path);ap.add_argument('reference',type=Path);ap.add_argument('pml',type=Path);ap.add_argument('output',type=Path);args=ap.parse_args()
    data=analyze(args.work,args.reference,args.pml);args.output.write_text(json.dumps(data,indent=2,allow_nan=False))
    for r in data['comparisons']:print(r['profile'],r['material_polarization'],r['rms_complex_error'],r['formula_rms_difference'])

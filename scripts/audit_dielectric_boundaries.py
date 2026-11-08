"""Check GO presence on both sides, including samples unsuitable for a jump ratio."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from analyze_dielectric import boundary_go
from dielectric_model import go_coefficient

read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('work',type=Path);ap.add_argument('output',type=Path);args=ap.parse_args()
    receipt=read(args.work/'receipt.json');assert receipt['status']=='passed'
    assert hashlib.sha256((args.work/'cases.json').read_bytes()).hexdigest()==receipt['manifest_sha256']
    cases={c['name']:c for c in read(args.work/'cases.json')['cases']}
    checks=[]
    for process in receipt['processes']:
        path=args.work/process['profile']/process['output']
        assert hashlib.sha256(path.read_bytes()).hexdigest()==process['output_sha256']
        for row in read(path)['cases']:
            c=cases[row['name']];meta=c['study']
            if meta['kind']!='boundary' or meta['material']=='air':continue
            for rx,offset in enumerate(meta['offsets_deg']):
                if offset==0:continue
                reference=go_coefficient(c,meta['boundary'],rx)
                # A physically present null channel cannot test a path-export filter.
                if reference is not None and abs(reference[0])<1e-10:continue
                expected=reference is not None
                observed=[p for p in boundary_go(c,row,rx) if abs(complex(*p['a']))>=1e-10]
                entry=dict(profile=process['profile'],name=c['name'],boundary=meta['boundary'],offset_deg=offset,expected_go=expected,observed_go=len(observed),passed=len(observed)==int(expected))
                if not entry['passed']:
                    entry['paths']=observed
                    if meta['boundary']!='incident':
                        axis=0 if meta['boundary']=='reflection0' else 1;other=1-axis
                        rot=np.asarray(c['physics']['rotation']);tx=rot.T@np.asarray(c['tx']);dest=rot.T@np.asarray(c['receivers'][rx])
                        image=tx.copy();image[axis]*=-1
                        t=-image[axis]/(dest[axis]-image[axis]);ideal=image+t*(dest-image)
                        entry['ideal_reflection_point']=(rot@ideal).tolist()
                        entry['ideal_reflection_distance_inside_face_m']=float(ideal[other])
                        entry['observed_point_error_m']=[float(np.linalg.norm(np.asarray(p['points'][1])-rot@ideal)) for p in observed]
                        entry['reflection_distance_inside_face_m']=[float((np.asarray(c['physics']['rotation']).T@np.asarray(p['points'][1]))[other]) for p in observed]
                checks.append(entry)
    summary={}
    for profile in [p['profile'] for p in receipt['processes']]:
        selected=[r for r in checks if r['profile']==profile];bad=[r for r in selected if not r['passed']]
        summary[profile]=dict(checks=len(selected),failed=len(bad),failed_offsets_deg=sorted({r['offset_deg'] for r in bad}),
            failed_boundaries=sorted({r['boundary'] for r in bad}),
            max_ideal_point_distance_outside_face_m=max([-r.get('ideal_reflection_distance_inside_face_m',0.) for r in bad]+[0.]),
            max_observed_point_error_m=max([max(r.get('observed_point_error_m',[])+[0.]) for r in bad]+[0.]))
    result=dict(scope='Independent image-method/segment GO presence on non-air fixtures, away from nominal exact boundaries and nonzero when physically present. Tests visibility separately from field-jump ratios.',summary=summary,checks=checks)
    args.output.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(summary,indent=2))

if __name__=='__main__':main()

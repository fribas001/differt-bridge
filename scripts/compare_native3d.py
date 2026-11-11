"""Retain actual Sionna/DiffeRT CIR exports and add guarded 3D PEC Hertz-UTD."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
from shared_sionna import DEFAULT_PYTHON
from hertz_pec3d import validate,refine

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def main():
    ap=argparse.ArgumentParser();ap.add_argument('workspace',type=Path);ap.add_argument('--manifest',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--reuse-rays',type=Path);a=ap.parse_args();root=a.workspace.resolve()
    cases=read(a.manifest)['cases']
    for c in cases:validate(c)
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=True);rays=a.reuse_rays.resolve() if a.reuse_rays else out/'rays'
    if not a.reuse_rays:
        command=[sys.executable,'-B',str(Path(__file__).with_name('run_dielectric.py')),'--differt-python',str(root/'work/runtime/Scripts/python.exe'),'--sionna-python',str(DEFAULT_PYTHON),'--output',str(rays),'--profiles','sionna-reciprocal,differt-reciprocal','--precision','float32','--manifest',str(a.manifest.resolve())]
        subprocess.run(command,check=True)
    receipt=read(rays/'receipt.json');assert receipt['status']=='passed'
    available={c['name']:c for c in read(rays/'cases.json')['cases']}
    assert all(available[c['name']]==c for c in cases),'Mismatched reused inputs'
    assert {'sionna-reciprocal','differt-reciprocal'}<={r['profile'] for r in receipt['processes']}
    product=refine(cases);fields={r['name']:r['field'] for r in product['results']};rows=[];hashes={}
    for record in receipt['processes']:
        path=rays/record['profile']/record['output'];digest=hashlib.sha256(path.read_bytes()).hexdigest();assert digest==record['output_sha256'];hashes[record['profile']]=digest
        raw={r['name']:r for r in read(path)['cases']}
        for c in cases:
            row=raw[c['name']];assert row['status']=='completed';values=[]
            for j in range(len(c['receivers'])):
                u=sum(complex(*p['cir']) for p in row['paths'] if p['rx']==j);values.append([u.real,u.imag])
            rows.append(dict(profile=record['profile'],name=c['name'],native_3d_cir=values,optional_3d_pec=fields[c['name']]))
        assert hashlib.sha256(path.read_bytes()).hexdigest()==digest
    (out/'refinement.json').write_text(json.dumps(product,indent=2),encoding='utf-8')
    (out/'comparison.json').write_text(json.dumps(dict(status='passed',reference_used=False,engine_outputs_unchanged=hashes,shared_correction=True,comparisons=rows),indent=2),encoding='utf-8')
    print('NATIVE3D_COMPARISON_PASS',out,flush=True)

if __name__=='__main__':main()

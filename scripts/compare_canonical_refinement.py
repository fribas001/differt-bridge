"""Run both configured ray tracers and add a separate canonical 2D full-wave field."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
from canonical_maxwell_refinement import validate,refine_cases
from line_source_comparison import channel

def main():
    ap=argparse.ArgumentParser();ap.add_argument('workspace',type=Path);ap.add_argument('--manifest',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--reuse-rays',type=Path);args=ap.parse_args()
    root=args.workspace.resolve();cases=json.loads(args.manifest.read_text())['cases']
    for c in cases:validate(c)
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=True);rays=args.reuse_rays.resolve() if args.reuse_rays else output/'rays'
    if not args.reuse_rays:
        command=[sys.executable,'-B',str(Path(__file__).with_name('run_dielectric.py')),'--differt-python',str(root/'work/runtime/Scripts/python.exe'),'--sionna-python',str(root/'work/sionna-runtime/Scripts/python.exe'),'--llvm-library','C:/Program Files/LLVM/bin/LLVM-C.dll','--output',str(rays),'--profiles','sionna-reciprocal,differt-reciprocal','--precision','float32','--manifest',str(args.manifest.resolve())]
        subprocess.run(command,check=True)
    receipt=json.loads((rays/'receipt.json').read_text());assert receipt['status']=='passed'
    assert {'sionna-reciprocal','differt-reciprocal'}<={r['profile'] for r in receipt['processes']},'Both reciprocal engine outputs are required'
    assert json.loads((rays/'cases.json').read_text())['cases']==cases,'Reused rays belong to another scene'
    hashes={r['profile']:hashlib.sha256((rays/r['profile']/r['output']).read_bytes()).hexdigest() for r in receipt['processes']}
    for r in receipt['processes']:assert hashes[r['profile']]==r['output_sha256']
    refinement=refine_cases(cases,24);lookup={name:(r,i) for r in refinement['results'] for i,name in enumerate(r['case_names'])};byname={c['name']:c for c in cases};comparisons=[]
    for record in receipt['processes']:
        if not record['profile'].endswith('reciprocal'):continue
        for row in json.loads((rays/record['profile']/record['output']).read_text())['cases']:
            c=byname[row['name']];refined,i=lookup[row['name']];values=[]
            for j in range(len(c['receivers'])):
                u,_,_=channel(c,row,j);values.append([u.real,u.imag])
            comparisons.append(dict(profile=record['profile'],case=row['name'],native_3d_paths_retained=True,ray_2d_comparison=values,fullwave_2d=refined['field'][i]))
    for r in receipt['processes']:assert hashlib.sha256((rays/r['profile']/r['output']).read_bytes()).hexdigest()==hashes[r['profile']]
    (output/'refinement.json').write_text(json.dumps(refinement,indent=2,allow_nan=False))
    (output/'comparison.json').write_text(json.dumps(dict(status='passed',scope=refinement['scope'],reference_used=False,engine_outputs_unchanged=hashes,comparisons=comparisons),indent=2,allow_nan=False))
    print('CANONICAL_REFINEMENT_PASS',output,flush=True)

if __name__=='__main__':main()

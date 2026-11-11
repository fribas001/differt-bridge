"""Run both native workflows and a separate guarded solid-wedge Maxwell field."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
from shared_sionna import DEFAULT_PYTHON
from dielectric3d_refinement import validate,refine
from dielectric3d_converged import refine_converged

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('workspace',type=Path);ap.add_argument('--manifest',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--panels',type=int,default=32);ap.add_argument('--reuse-rays',type=Path);ap.add_argument('--checkpoint-folder',type=Path);ap.add_argument('--coarse-checkpoint-folder',type=Path);ap.add_argument('--accuracy',choices=['standard','converged'],default='converged');a=ap.parse_args();root=a.workspace.resolve();cases=read(a.manifest)['cases']
    for c in cases:validate(c)
    if a.accuracy=='converged' and a.panels!=32:raise ValueError('The validated converged mode uses BIE16/BIE32; select --accuracy standard for other panel counts.')
    if a.accuracy=='standard' and a.coarse_checkpoint_folder:raise ValueError('A coarse checkpoint applies only to converged mode.')
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=True);rays=a.reuse_rays.resolve() if a.reuse_rays else out/'rays'
    if not a.reuse_rays:
        command=[sys.executable,'-B',str(Path(__file__).with_name('run_dielectric.py')),'--differt-python',str(root/'work/runtime/Scripts/python.exe'),'--sionna-python',str(DEFAULT_PYTHON),'--output',str(rays),'--profiles','sionna-reciprocal,differt-reciprocal','--precision','float32','--manifest',str(a.manifest.resolve())]
        subprocess.run(command,check=True)
    receipt=read(rays/'receipt.json');assert receipt['status']=='passed';available={c['name']:c for c in read(rays/'cases.json')['cases']}
    def physics(c):return {k:v for k,v in c.items() if k!='maxwell_domain'}
    assert all(c['name'] in available and physics(available[c['name']])==physics(c) for c in cases),'Mismatched ray inputs'
    assert {'sionna-reciprocal','differt-reciprocal'}<={r['profile'] for r in receipt['processes']}
    if a.accuracy=='converged':
        result=refine_converged(cases,out/'modes',a.checkpoint_folder.resolve() if a.checkpoint_folder else None,a.coarse_checkpoint_folder.resolve() if a.coarse_checkpoint_folder else None)
    else:result=refine(cases,a.checkpoint_folder.resolve() if a.checkpoint_folder else out/'modes',panels=a.panels)
    result['manifest_sha256']=sha(a.manifest);fields={r['name']:r['field'] for r in result['results']};rows=[];hashes={}
    for process in receipt['processes']:
        path=rays/process['profile']/process['output'];assert sha(path)==process['output_sha256'];hashes[process['profile']]=sha(path);raw={r['name']:r for r in read(path)['cases']}
        for c in cases:
            row=raw[c['name']];assert row['status']=='completed';values=[]
            for j in range(len(c['receivers'])):
                value=sum(complex(*p['cir']) for p in row['paths'] if p['rx']==j);values.append([value.real,value.imag])
            rows.append(dict(profile=process['profile'],name=c['name'],ray_cir=values,optional_3d_dielectric=fields[c['name']]))
        assert sha(path)==hashes[process['profile']]
    (out/'refinement.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    (out/'comparison.json').write_text(json.dumps(dict(status='passed',accuracy=a.accuracy,reference_used=False,engine_outputs_unchanged=hashes,shared_solver=True,manifest_sha256=sha(a.manifest),comparisons=rows),indent=2),encoding='utf-8')
    print('DIELECTRIC3D_COMPARISON_PASS',out,flush=True)

if __name__=='__main__':main()

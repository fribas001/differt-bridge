"""Portable generated diffraction runs; native baselines are always retained."""
import argparse
from datetime import datetime,timezone
import hashlib,json,os,subprocess,time
from pathlib import Path
import numpy as np
from diffraction_cases import pilot_cases
from diffraction_physics_cases import cases as physics_cases,pec_channel
from shared_sionna import command as runtime_command, is_shared, require_native, worker_environment
ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--differt-python',type=Path,required=True);ap.add_argument('--sionna-python',type=Path)
    ap.add_argument('--llvm-library',type=Path);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--suite',choices=['pilot','physics'],default='pilot');ap.add_argument('--only',default='')
    ap.add_argument('--experimental-sionna',choices=['kp_assembly','kp_depth'])
    args=ap.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    if args.experimental_sionna and not args.sionna_python:ap.error('An experimental Sionna profile requires --sionna-python')
    if args.sionna_python and is_shared(args.sionna_python):require_native(args.experimental_sionna or 'native')
    cases=physics_cases() if args.suite=='physics' else pilot_cases()
    if args.only:
        names=set(args.only.split(','));cases=[c for c in cases if c['name'] in names]
        if {c['name'] for c in cases}!=names:ap.error('Unknown fixture name in --only')
    manifest=out/'cases.json';manifest.write_text(json.dumps({'cases':cases},indent=2),encoding='utf-8')
    jobs=[('differt','native',args.differt_python)]
    if args.sionna_python:jobs.append(('sionna','native',args.sionna_python))
    if args.experimental_sionna:jobs.append(('sionna',args.experimental_sionna,args.sionna_python))
    receipts=[];checks=[]
    for engine,profile,python in jobs:
        folder=out/(engine+'-'+profile);folder.mkdir(exist_ok=True)
        command=[str(python.resolve()),'-B',str(ROOT/'scripts/diffraction_physics_worker.py'),profile,engine,str(manifest),str(folder),'--precision','native','--diffraction-geometry','validated']
        env=os.environ.copy()
        if args.llvm_library:env['DRJIT_LIBLLVM_PATH']=str(args.llvm_library.resolve())
        if engine=='sionna' and is_shared(python):
            command=runtime_command(python,command[1:]);env=worker_environment(env)
        started=time.perf_counter()
        with (folder/'process.log').open('w',encoding='utf-8') as log:p=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT)
        path=folder/(engine+'_native.json');data=json.loads(path.read_text()) if path.exists() else {}
        errors=[c for c in data.get('cases',[]) if c['status']!='completed']
        guard=(p.returncode==2 and engine=='differt' and bool(errors) and all('Candidate upper bound ' in c.get('error','') and 'exceeds budget' in c['error'] for c in errors))
        record=dict(engine=engine,profile=profile,command=command,returncode=p.returncode,seconds=time.perf_counter()-started,
                    requested_cases=len(cases),completed_cases=sum(c['status']=='completed' for c in data.get('cases',[])),
                    recognized_search_limits=[c['name'] for c in errors] if guard else [],
                    numerical_status=data.get('status'),output_sha256=hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None)
        record['accepted_outcome']=len(data.get('cases',[]))==len(cases) and ((p.returncode==0 and data.get('status')=='completed') or (guard and data.get('status')=='completed_with_errors'))
        receipts.append(record);print(json.dumps({k:v for k,v in record.items() if k!='command'}),flush=True)
        for c,row in zip(cases,data.get('cases',[])):
            m=c.get('physics',{})
            if m.get('material')!='pec' or m.get('boundary') or row['status']!='completed':continue
            ref=pec_channel(c);paths=[p for p in row['paths'] if p['interactions']==[8]]
            result=dict(engine=engine,profile=profile,name=c['name'],coefficient_dtype=row.get('coefficient_dtype'),reference=[ref.real,ref.imag],paths=len(paths),reference_null=abs(ref)<1e-10)
            if len(paths)==1:
                value=complex(*paths[0]['a']);result['absolute_complex_error']=abs(value-ref)
                result['relative_complex_error']=abs(value-ref)/abs(ref) if abs(ref)>=1e-10 else None
                result['phase_error_rad']=float(np.angle(value/ref)) if abs(ref)>=1e-10 and abs(value)>=1e-10 else None
            checks.append(result)
    result=dict(generated_utc=datetime.now(timezone.utc).isoformat(),suite=args.suite,
                scope='Fresh generated fixtures; actual coefficient dtype retained; no installed physics changes',
                status='completed_with_search_limits' if any(r['recognized_search_limits'] for r in receipts) else 'completed',processes=receipts,pec_checks=checks)
    if not all(r['accepted_outcome'] for r in receipts):result['status']='failed'
    (out/'receipt.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    if result['status']=='failed':raise SystemExit(1)

if __name__=='__main__':main()

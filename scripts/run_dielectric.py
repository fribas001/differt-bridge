"""Generate and run dielectric reciprocity/boundary diagnostics in separate processes."""
import argparse,hashlib,json,os,subprocess,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from dielectric_cases import cases

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--differt-python',type=Path,required=True);ap.add_argument('--sionna-python',type=Path,required=True)
    ap.add_argument('--llvm-library',type=Path);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--profiles',default='differt-native,sionna-native',help='Candidates require an explicit profile list; see the dielectric report')
    ap.add_argument('--precision',choices=['float32','float64','native'],default='native');ap.add_argument('--only',default='')
    ap.add_argument('--manifest',type=Path,help='Use an explicit fixture manifest instead of the standard 286 cases')
    args=ap.parse_args()
    profiles=args.profiles.split(',')
    allowed={'differt-native','sionna-native','sionna-kp_depth','differt-polarization','differt-incident','differt-symmetric_cosine','differt-reciprocal','sionna-reciprocal'}
    if not profiles or len(profiles)!=len(set(profiles)) or not set(profiles)<=allowed:
        ap.error('Choose unique profiles from: '+','.join(sorted(allowed)))
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    selected=json.loads(args.manifest.read_text(encoding='utf-8-sig'))['cases'] if args.manifest else cases()
    if args.only:
        wanted=set(args.only.split(','));selected=[c for c in selected if c['name'] in wanted]
        assert {c['name'] for c in selected}==wanted,'Unknown case'
    manifest=out/'cases.json';manifest.write_text(json.dumps(dict(cases=selected),indent=2),encoding='utf-8')
    def run(label):
        engine,profile=label.split('-',1);folder=out/label;folder.mkdir(exist_ok=True)
        python=args.differt_python if engine=='differt' else args.sionna_python
        precision=args.precision if engine=='differt' else 'float32'
        cmd=[str(python.resolve()),'-B',str(Path(__file__).with_name('dielectric_worker.py')),profile,engine,str(manifest),str(folder),'--precision',precision,'--diffraction-geometry','validated']
        env=os.environ.copy();env['DIFFERT_FIELD_PRECISION']='float64' if args.precision=='float64' else 'float32'
        env['RADIO_DIELECTRIC_PROFILE']='native'  # Explicit process-local profile below; never inherit a corrected baseline.
        if args.llvm_library:env['DRJIT_LIBLLVM_PATH']=str(args.llvm_library.resolve())
        start=time.perf_counter()
        with (folder/'process.log').open('w',encoding='utf-8') as log:p=subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT)
        datafile=folder/(engine+'_'+precision+'.json');data=json.loads(datafile.read_text()) if datafile.exists() else {}
        receipt=dict(profile=label,returncode=p.returncode,elapsed_seconds=time.perf_counter()-start,requested=len(selected),completed=sum(c['status']=='completed' for c in data.get('cases',[])),
                     status=data.get('status'),output=datafile.name,output_sha256=hashlib.sha256(datafile.read_bytes()).hexdigest() if datafile.exists() else None)
        receipt['passed']=p.returncode==0 and receipt['completed']==len(selected) and receipt['status']=='completed'
        (folder/'receipt.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt),flush=True);return receipt
    with ThreadPoolExecutor(max_workers=2) as pool:receipts=list(pool.map(run,profiles))
    result=dict(status='passed' if all(r['passed'] for r in receipts) else 'failed',manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),processes=receipts)
    (out/'receipt.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    if result['status']!='passed':raise SystemExit(1)

if __name__=='__main__':main()

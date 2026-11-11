"""Offline RT 2.1 recovery. Setup/probe do not trace paths or solve fields."""
from __future__ import annotations
import argparse,hashlib,json,os,platform,runpy,subprocess,sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def digest(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,data):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
def inside(root,name):
    p=(root/name).resolve()
    if not p.is_relative_to(root.resolve()):raise ValueError('Path escapes package: '+str(name))
    return p
def verify():
    data=read(ROOT/'MANIFEST.json')
    def one(item):
        name,row=item
        p=inside(ROOT,name)
        if not p.is_file() or p.stat().st_size!=row['bytes'] or digest(p)!=row['sha256']:
            raise ValueError('Missing or changed recovery payload: '+name)
    with ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(one,data['files'].items()))
    print('RECOVERY_PAYLOAD_VERIFIED',len(data['files']),flush=True)
    return data
def environment(profile='native'):
    env={k:v for k,v in os.environ.items() if not k.startswith(('PYTHON','PIP_','RADIO_','DIFFERT_','SIONNA_','DRJIT_','JAX_','XLA_'))}
    temp=ROOT/'local/temp';temp.mkdir(parents=True,exist_ok=True)
    env.update(TEMP=str(temp),TMP=str(temp),PYTHONNOUSERSITE='1',PYTHONDONTWRITEBYTECODE='1',
               PIP_CONFIG_FILE=os.devnull,PIP_DISABLE_PIP_VERSION_CHECK='1',OPENBLAS_NUM_THREADS='1',
               DRJIT_LIBLLVM_PATH=str(ROOT/'vendor/llvm/LLVM-C.dll'),DRJIT_CACHE_DIR=str(temp/'jit'),
               RADIO_DIELECTRIC_PROFILE='reciprocal' if profile=='reciprocal' else 'native',
               RADIO_SEGMENT_PROFILE='shared_1mm' if profile=='phase' else 'native',
               SIONNA_GEOMETRY_PROFILE='unshifted_float64' if profile=='phase' else 'native')
    # Do not fall back to the old interpreter, LLVM installation or Blender DLLs.
    env['PATH']=os.pathsep.join([str(ROOT/'vendor/python313/bin'),str(ROOT/'vendor/llvm'),
                               str(Path(os.environ['SystemRoot'])/'System32'),os.environ['SystemRoot']])
    return env
def python():return ROOT/'local/runtime/Scripts/python.exe'
def execute(label,command,profile='native'):
    log=ROOT/'local/logs'/(label+'.log');log.parent.mkdir(parents=True,exist_ok=True)
    with log.open('w',encoding='utf-8') as f:
        p=subprocess.run(list(map(str,command)),cwd=ROOT,env=environment(profile),stdout=f,stderr=subprocess.STDOUT)
    if p.returncode:
        print(log.read_text(encoding='utf-8',errors='replace')[-6000:]);raise RuntimeError(label+' failed; see '+str(log))
    print('PASS',label,flush=True)
def check_restored():
    site=ROOT/'local/runtime/Lib/site-packages';spec=read(ROOT/'patches.json')
    relocated={}
    for r in spec['files']:
        if r['relocate_llvm']:
            data=read(ROOT/'patches'/r['path']);data['original_llvm']=str(ROOT/'vendor/llvm/LLVM-C.dll')
            relocated[r['path']]=hashlib.sha256((json.dumps(data,indent=2)+'\n').encode()).hexdigest()
    inventory=read(ROOT/'scientific-files.json')
    def one(item):
        name,expected=item
        path=inside(site,name)
        if not path.is_file() or digest(path)!=relocated.get(name,expected):
            raise ValueError('Restored scientific file mismatch: '+name)
    with ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(one,inventory.items()))
    return dict(scientific_files=len(inventory),relocations=list(relocated),passed=True)
def setup():
    if os.name!='nt' or platform.machine().lower() not in ('amd64','x86_64'):raise RuntimeError('Windows x64 required')
    verify();target=ROOT/'local/runtime';receipt=ROOT/'local/setup.json'
    if target.exists():raise ValueError('Restore target already exists; extract the archive to a fresh directory')
    execute('create',[ROOT/'vendor/python313/bin/python.exe','-I','-B','-m','venv',target])
    execute('install',[python(),'-I','-B','-m','pip','--no-cache-dir','install','--no-compile','--no-index','--require-hashes',
            '--only-binary=:all:','--find-links',ROOT/'wheelhouse/sionna','-r',ROOT/'wheelhouse/sionna.lock'])
    execute('dependencies',[python(),'-I','-B','-m','pip','check'])
    planned=[];site=target/'Lib/site-packages'
    for row in read(ROOT/'patches.json')['files']:
        source=inside(ROOT/'patches',row['path']);destination=inside(site,row['path'])
        if digest(source)!=row['after_sha256']:raise ValueError('Changed patch: '+row['path'])
        current=digest(destination) if destination.is_file() else None
        if current!=row['before_sha256']:raise ValueError('Unexpected pre-patch file: '+row['path'])
        data=source.read_bytes()
        if row['relocate_llvm']:
            value=json.loads(data);value['original_llvm']=str(ROOT/'vendor/llvm/LLVM-C.dll')
            data=(json.dumps(value,indent=2)+'\n').encode()
        planned.append((destination,data))
    for destination,data in planned:
        destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(data)
    checks=check_restored()
    save(receipt,dict(status='passed',bundle_manifest_sha256=digest(ROOT/'MANIFEST.json'),**checks))
    print('OFFLINE_RESTORE_COMPLETE',checks,flush=True)
def require_setup():
    r=read(ROOT/'local/setup.json')
    if r['status']!='passed' or r['bundle_manifest_sha256']!=digest(ROOT/'MANIFEST.json'):raise ValueError('Run setup for this package first')
    return check_restored()
def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    sub.add_parser('verify');sub.add_parser('setup')
    probe=sub.add_parser('probe');probe.add_argument('--profile',choices=('native','phase','reciprocal'),default='native')
    run=sub.add_parser('run',help='Explicitly run a historical script; it may perform simulations')
    run.add_argument('--profile',choices=('native','phase','reciprocal'),default='native');run.add_argument('arguments',nargs=argparse.REMAINDER)
    a=p.parse_args()
    if a.action=='verify':verify();return
    if a.action=='setup':setup();return
    verify();require_setup()
    if a.action=='probe':
        execute('probe-'+a.profile,[python(),'-I','-B',ROOT/'probe.py',ROOT,ROOT/'local'/('probe-'+a.profile+'.json')],a.profile)
    else:
        args=a.arguments[1:] if a.arguments[:1]==['--'] else a.arguments
        if not args:p.error('A script or -m module is required after --')
        execute('historical-run',[python(),'-I','-B',ROOT/'run_script.py',*args],a.profile)
if __name__=='__main__':main()

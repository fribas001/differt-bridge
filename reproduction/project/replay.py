"""Verify/recover the Windows release; calculations require an explicit run command."""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT=Path(__file__).resolve().parent
WORK=ROOT/'workspace'
PROJECT=WORK/'work/github-update/differt-bridge'

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,data):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
def inside(root,name):
    p=(root/name).resolve()
    if not p.is_relative_to(root.resolve()):raise ValueError('Path escapes package: '+str(name))
    return p
def python(engine):return WORK/'work'/('runtime' if engine=='differt' else 'rt22-runtime')/'Scripts/python.exe'

def verify(only=None):
    manifests=sorted((ROOT/'_manifests').glob('*.json'))
    if only:manifests=[p for p in manifests if p.name==only+'.json']
    if not manifests:raise ValueError('No release manifests found; extract the required archives together')
    def one(item):
        name,record=item;p=inside(ROOT,name)
        if not p.is_file() or p.stat().st_size!=record['bytes'] or sha(p)!=record['sha256']:
            raise ValueError('Missing/changed release file: '+name)
    count=0
    for manifest in manifests:
        rows=read(manifest)['files']
        with ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(one,rows.items()))
        count+=len(rows)
    print('VERIFIED',count,'files',flush=True)
    return count

def environment(profile='native'):
    env={k:v for k,v in os.environ.items() if not k.startswith(('PYTHON','PIP_','RADIO_','DIFFERT_','SIONNA_','DRJIT_','JAX_','XLA_'))}
    temp=ROOT/'local/temp';temp.mkdir(parents=True,exist_ok=True)
    env.update(TEMP=str(temp),TMP=str(temp),PYTHONNOUSERSITE='1',PYTHONDONTWRITEBYTECODE='1',
               PIP_CONFIG_FILE=os.devnull,PIP_DISABLE_PIP_VERSION_CHECK='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',
               JAX_PLATFORMS='cpu',RADIO_RT22_PROFILE=profile,
               RADIO_DIELECTRIC_PROFILE='reciprocal' if profile=='reciprocal' else 'native',
               RADIO_SEGMENT_PROFILE='shared_1mm' if profile=='phase' else 'native',
               SIONNA_GEOMETRY_PROFILE='unshifted_float64' if profile=='phase' else 'native',
               DIFFERT_ARITHMETIC_PROFILE='sionna_order' if profile=='phase' else 'native',
               DIFFERT_FIELD_PRECISION='float32',DIFFERT_DIFFRACTION_GEOMETRY='validated',
               SIONNA_SHARED_PYTHON=str(python('rt22')))
    system=Path(os.environ['SystemRoot'])
    env['PATH']=os.pathsep.join([str(ROOT/'vendor/python312'),str(system/'System32'),str(system)])
    return env

def execute(label,args,profile='native',env=None,cwd=None):
    log=ROOT/'local/logs'/(label+'.log');log.parent.mkdir(parents=True,exist_ok=True)
    print('RUN',label,flush=True)
    with log.open('w',encoding='utf-8') as stream:
        result=subprocess.run(list(map(str,args)),cwd=cwd or WORK,env=env or environment(profile),stdout=stream,stderr=subprocess.STDOUT)
    if result.returncode:
        print(log.read_text(encoding='utf-8',errors='replace')[-7000:]);raise RuntimeError(label+' failed: '+str(log))
    print('PASS',label,flush=True)

def restored_files():
    site=python('differt').parents[1]/'Lib/site-packages'
    inventory=read(ROOT/'runtime_payload/differt/spec.json')['scientific_files']
    checks=[(site/name,h) for name,h in inventory.items()]
    manifest=read(ROOT/'_manifests/project-runtimes-windows-x64.zip.json')['files']
    target=python('rt22').parents[1]
    for name,row in manifest.items():
        if name.startswith('runtime_payload/rt22/site/'):
            checks.append((target/'Lib/site-packages'/name.removeprefix('runtime_payload/rt22/site/'),row['sha256']))
        elif name.startswith('runtime_payload/rt22/native/'):
            checks.append((target/'native'/name.removeprefix('runtime_payload/rt22/native/'),row['sha256']))
    def one(row):
        path,h=row
        if not path.is_file() or sha(path)!=h:raise ValueError('Restored file mismatch: '+str(path))
    with ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(one,checks))
    return len(checks)

def setup():
    if os.name!='nt':raise RuntimeError('Windows x64 required')
    verify('project-runtimes-windows-x64.zip')
    if not (PROJECT/'scripts/rt22_profiles/manifest.json').is_file():raise RuntimeError('Extract project-source.zip first')
    if any(python(e).parents[1].exists() for e in ('differt','rt22')):raise ValueError('Use a fresh extraction; existing environments are never overwritten')
    base=ROOT/'vendor/python312/python.exe'
    for engine in ('differt','rt22'):
        target=python(engine).parents[1]
        execute('create-'+engine,[base,'-I','-B','-m','venv',*(['--without-pip'] if engine=='rt22' else []),target])
        site=target/'Lib/site-packages'
        if engine=='differt':
            payload=ROOT/'runtime_payload/differt'
            execute('install-differt',[python(engine),'-I','-B','-m','pip','--no-cache-dir','install','--no-index','--no-compile',
                    '--require-hashes','--only-binary=:all:','--find-links',payload/'wheels','-r',payload/'requirements.lock'])
            for row in read(payload/'spec.json')['patches']:
                dst=inside(site,row['path']);src=inside(payload/'patches',row['path'])
                actual=sha(dst) if dst.is_file() else None
                if actual!=row['before'] or sha(src)!=row['after']:raise ValueError('Unexpected patch source/target: '+row['path'])
                dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
        else:
            shutil.copytree(ROOT/'runtime_payload/rt22/site',site,dirs_exist_ok=True)
            shutil.copytree(ROOT/'runtime_payload/rt22/native',target/'native')
        execute('dependencies-'+engine,[python(engine),'-I','-B','-m','pip','check'])
    count=restored_files()
    save(ROOT/'local/setup.json',{'passed':True,'scientific_files_verified':count,'simulations_run':False,
         'runtime_manifest_sha256':sha(ROOT/'_manifests/project-runtimes-windows-x64.zip.json')})
    print('OFFLINE_SETUP_COMPLETE',count,'verified scientific files',flush=True)

def require_setup():
    r=read(ROOT/'local/setup.json')
    if not r['passed'] or r['runtime_manifest_sha256']!=sha(ROOT/'_manifests/project-runtimes-windows-x64.zip.json'):raise ValueError('Setup receipt mismatch')

def rt_command(arguments,profile):
    args=[python('rt22'),'-I','-B','-m','codex_sionna_runtime']
    if profile!='native':args.extend([PROJECT/'scripts/rt22_research_worker.py','--profile',profile,'--'])
    return [*args,*arguments]

def blender(a):
    executable=a.blender.resolve()
    if not executable.is_file():raise FileNotFoundError(executable)
    profile=ROOT/'local/blender-profile'
    extensions=profile/'extensions/user_default'
    extensions.mkdir(parents=True,exist_ok=True)
    for name in ('differt_bridge','sionnart_bridge'):
        if not (extensions/name).exists():shutil.copytree(ROOT/'extensions'/name,extensions/name)
    env=environment(a.profile)
    for variable,folder in [('BLENDER_USER_CONFIG','config'),('BLENDER_USER_SCRIPTS','scripts'),('BLENDER_USER_EXTENSIONS','extensions')]:
        path=profile/folder;path.mkdir(parents=True,exist_ok=True);env[variable]=str(path)
    command=[executable,*(['--background'] if a.action=='blender-check' else []),'--factory-startup','--python-exit-code','1',
             '--python',ROOT/'blender_session.py','--',ROOT,a.profile]
    if a.action=='blender-check':command.append('--check')
    if a.action=='blender-check':execute('blender-'+a.profile,command,a.profile,env)
    else:subprocess.Popen(list(map(str,command)),cwd=WORK,env=env)

def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='action',required=True)
    sub.add_parser('verify');sub.add_parser('setup')
    p=sub.add_parser('probe');p.add_argument('--profile',choices=('native','phase','reciprocal'),default='native')
    for action in ('blender','blender-check'):
        p=sub.add_parser(action);p.add_argument('--profile',choices=('native','phase','reciprocal'),default='native')
        p.add_argument('--blender',type=Path,required=True)
    p=sub.add_parser('run',help='Explicitly run a scientific script; may perform simulations')
    p.add_argument('--engine',choices=('differt','rt22'),required=True)
    p.add_argument('--profile',choices=('native','phase','reciprocal'),default='native')
    p.add_argument('arguments',nargs=argparse.REMAINDER)
    a=parser.parse_args()
    if a.action=='verify':verify();return
    if a.action=='setup':setup();return
    require_setup()
    if a.action=='probe':
        for engine in ('differt','rt22'):
            command=[python(engine),'-I','-B',ROOT/'probe.py',engine,ROOT,a.profile]
            if engine=='rt22':command=rt_command([ROOT/'probe.py',engine,ROOT,a.profile],a.profile)
            execute('probe-'+engine+'-'+a.profile,command,a.profile)
    elif a.action in ('blender','blender-check'):blender(a)
    else:
        args=a.arguments[1:] if a.arguments[:1]==['--'] else a.arguments
        if not args:parser.error('A script or module command is required after --')
        command=rt_command(args,a.profile) if a.engine=='rt22' else [python('differt'),'-B',*args]
        execute('explicit-'+a.engine+'-'+a.profile,command,a.profile)
if __name__=='__main__':main()

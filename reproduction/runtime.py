"""Offline setup and guarded commands for a relocatable reproduction bundle."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def contained(root, relative):
    path=(root/relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Path escapes the bundle: '+str(relative))
    return path


def verify(root):
    manifest=read(root/'MANIFEST.json')
    if manifest['schema_version']!=1:raise ValueError('Unsupported bundle manifest')
    def one(row):
        name,record=row;path=contained(root,name)
        if not path.is_file() or path.stat().st_size!=record['bytes'] or sha(path)!=record['sha256']:
            raise ValueError('Missing or changed bundle file: '+name)
    with ThreadPoolExecutor(max_workers=4) as pool:
        for _ in pool.map(one,manifest['files'].items()):pass
    print('BUNDLE_VERIFIED',len(manifest['files']),'files',flush=True)
    return manifest


def environment(root, tag='commands'):
    env={k:v for k,v in os.environ.items() if not k.startswith(('PYTHON','PIP_','RADIO_','DIFFERT_','SIONNA_','DRJIT_','JAX_','XLA_'))}
    temp=contained(root,'local/temp/'+tag);temp.mkdir(parents=True,exist_ok=True)
    cache=contained(root,'local/cache/'+tag);cache.mkdir(parents=True,exist_ok=True)
    env.update(TEMP=str(temp),TMP=str(temp),TMPDIR=str(temp),PYTHONNOUSERSITE='1',PYTHONDONTWRITEBYTECODE='1',
        PIP_CONFIG_FILE=os.devnull,PIP_DISABLE_PIP_VERSION_CHECK='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',
        MKL_NUM_THREADS='1',JAX_PLATFORMS='cpu',CUDA_VISIBLE_DEVICES='',WP_CACHE_DIR=str(cache/'warp'),
        DRJIT_CACHE_DIR=str(cache/'drjit'),DRJIT_LIBLLVM_PATH=str(root/'vendor/llvm/LLVM-C.dll'),
        RADIO_DIELECTRIC_PROFILE='native',RADIO_SEGMENT_PROFILE='native',SIONNA_GEOMETRY_PROFILE='native',
        DIFFERT_ARITHMETIC_PROFILE='native')
    env['PATH']=os.pathsep.join([str(root/'vendor/python312'),str(root/'vendor/blender'),
                               str(root/'vendor/blender/blender.shared'),env.get('PATH','')])
    return env


def execute(root, command, label, env=None):
    log=contained(root,'local/logs/'+label+'.log');log.parent.mkdir(parents=True,exist_ok=True)
    print('RUN',label,flush=True);started=time.monotonic()
    with log.open('w',encoding='utf-8') as stream:
        completed=subprocess.run(list(map(str,command)),env=env or environment(root,label),cwd=root,stdout=stream,stderr=subprocess.STDOUT)
    record=dict(command=list(map(str,command)),returncode=completed.returncode,seconds=time.monotonic()-started,
                log=log.relative_to(root).as_posix())
    save(log.with_suffix('.json'),record)
    if completed.returncode:
        print(log.read_text(encoding='utf-8',errors='replace')[-7000:])
        raise RuntimeError(f'{label} failed; see {log}')
    print('PASS',label,round(record['seconds'],1),'seconds',flush=True)
    return record


def interpreter(root, engine, profile='research'):
    return root/'local/runtimes'/f'{engine}-{profile}'/'Scripts/python.exe'


def apply_patches(root, engine, profile, target):
    specification=read(root/'patches'/f'{engine}.json');site=target/'Lib/site-packages';planned=[]
    for row in specification['files']:
        if profile=='native' and row['category']!='reliability':continue
        source=contained(root/'patches'/engine,row['path']);destination=contained(site,row['path'])
        data=source.read_bytes()
        if hashlib.sha256(data).hexdigest()!=row['after_sha256']:raise ValueError('Patch payload changed: '+row['path'])
        if row['relocate_llvm']:
            value=json.loads(data);value['original_llvm']=str(root/'vendor/llvm/LLVM-C.dll')
            data=(json.dumps(value,indent=2)+'\n').encode()
        digest=hashlib.sha256(data).hexdigest()
        current=sha(destination) if destination.is_file() else None
        if current not in (row['before_sha256'],digest):
            raise ValueError('Refusing to overwrite unknown runtime contents: '+row['path'])
        planned.append((destination,data,dict(path=row['path'],category=row['category'],before=row['before_sha256'],after=digest,
                                           template_sha256=row['after_sha256'],relocated=row['relocate_llvm'])))
    for destination,data,_ in planned:
        destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(data)
    save(target/'patch-receipt.json',dict(engine=engine,profile=profile,files=[row for _,_,row in planned]))


def setup(root):
    if os.name!='nt' or platform.machine().lower() not in ('amd64','x86_64'):
        raise RuntimeError('This package targets Windows x64 CPU execution')
    verify(root)
    if shutil.disk_usage(root).free<5*1024**3:raise RuntimeError('At least 5 GiB free disk is required before setup')
    for engine in ('differt','sionna'):
        base=root/('vendor/python312/python.exe' if engine=='differt' else 'vendor/blender/5.2/python/bin/python.exe')
        for profile in ('native','research'):
            label=f'{engine}-{profile}';target=root/'local/runtimes'/label;receipt=target/'setup.json'
            specification=dict(bundle_manifest_sha256=sha(root/'MANIFEST.json'),engine=engine,profile=profile,
                               base=str(base),target=str(target),lock_sha256=sha(root/'wheelhouse'/f'{engine}.lock'))
            if receipt.exists():
                old=read(receipt)
                if old['configuration']!=specification:raise ValueError('Existing environment belongs to a different bundle/location: '+label)
                print('REUSING',label,flush=True)
            else:
                if target.exists():raise ValueError('Incomplete environment exists. Move it aside before repeating setup: '+str(target))
                execute(root,[base,'-I','-m','venv',target],'create-'+label)
                python=interpreter(root,engine,profile)
                execute(root,[python,'-I','-m','pip','--no-cache-dir','install','--no-index','--require-hashes','--only-binary=:all:',
                              '--find-links',root/'wheelhouse'/engine,'-r',root/'wheelhouse'/f'{engine}.lock'],'install-'+label)
                execute(root,[python,'-I','-m','pip','check'],'dependencies-'+label)
                apply_patches(root,engine,profile,target)
                save(receipt,dict(status='installed',configuration=specification))
            execute(root,[interpreter(root,engine,profile),'-B',root/'runner/probe_runtime.py',engine,
                          root/'local'/f'{label}-probe.json'],'probe-'+label)
    save(root/'local/setup.json',dict(status='passed',platform=platform.platform(),bundle_manifest_sha256=sha(root/'MANIFEST.json')))
    print('SETUP_COMPLETE: four isolated environments; installed workstation runtimes unchanged',flush=True)


def require_setup(root):
    status=read(root/'local/setup.json')
    if status['status']!='passed' or status['bundle_manifest_sha256']!=sha(root/'MANIFEST.json'):
        raise RuntimeError('Run setup for this bundle first')


def main(root):
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('verify',help='Verify every immutable package file')
    sub.add_parser('setup',help='Build four isolated environments entirely offline')
    compare=sub.add_parser('compare',help='Run fresh Sionna and DiffeRT fixtures')
    compare.add_argument('--suite',choices=['pilot','dielectric','holdout','concrete'],default='pilot')
    compare.add_argument('--profile',choices=['native','workstation','reciprocal'],default='native')
    sub.add_parser('replay',help='Recompute the latest Maxwell analysis from shipped checkpoints')
    maxwell=sub.add_parser('maxwell',help='Fresh independent Maxwell solves; never silently reuse them')
    maxwell.add_argument('--mode',choices=['smoke','full'],default='smoke')
    sub.add_parser('report',help='Regenerate the latest report from reproduced analysis')
    sub.add_parser('animation',help='Regenerate the comparison animation and Blender timeline')
    sub.add_parser('blender-check',help='Check both extensions in isolated Blender')
    launch=sub.add_parser('blender',help='Open an isolated Blender workflow with both engines configured')
    launch.add_argument('--profile',choices=['native','research'],default='research')
    launch.add_argument('--scene',type=Path)
    args=parser.parse_args()
    if args.command=='verify':verify(root);return
    if args.command=='setup':setup(root);return
    require_setup(root)
    from campaigns import dispatch
    dispatch(root,args)

"""Download verified release parts and reconstruct the original recovery ZIPs.

Only Python's standard library is needed. No environments or simulations run.
"""
from __future__ import annotations
import argparse, hashlib, json, re, shutil, time, urllib.request, zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE=Path(__file__).resolve().parent

def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def filename(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*',value):
        raise ValueError('Unsafe asset filename')
    return value

def contained(root,name):
    path=(root/name).resolve()
    if not path.is_relative_to(root.resolve()):raise ValueError('Path escapes destination')
    return path

def correct(path,row):return path.is_file() and path.stat().st_size==row['bytes'] and sha(path)==row['sha256']

def download(row,cache,prefix):
    name=filename(row['name']);path=contained(cache,name)
    if path.exists():
        if correct(path,row):return path
        raise ValueError('Existing cached part has an unexpected hash: '+name)
    if not row['url'].startswith(prefix):raise ValueError('Unexpected download origin')
    temporary=contained(cache,name+'.partial')
    for attempt in range(3):
        try:
            request=urllib.request.Request(row['url'],headers={'User-Agent':'differt-project-recovery'})
            with urllib.request.urlopen(request,timeout=90) as response,temporary.open('wb') as stream:
                shutil.copyfileobj(response,stream,1024*1024)
            if not correct(temporary,row):raise ValueError('Downloaded part failed integrity: '+name)
            temporary.replace(path);return path
        except Exception:
            if attempt==2:raise
            time.sleep(2*(attempt+1))

def assemble(asset,cache,destination):
    name=filename(asset['name']);target=contained(destination,name)
    if target.exists():
        if correct(target,asset):return target
        raise ValueError('Refusing to overwrite an existing file: '+name)
    temporary=contained(cache,name+'.joining')
    with temporary.open('wb') as output:
        for part in asset['parts']:
            source=contained(cache,filename(part['name']))
            if not correct(source,part):raise ValueError('Part failed integrity before joining: '+part['name'])
            with source.open('rb') as stream:shutil.copyfileobj(stream,output,1024*1024)
    if not correct(temporary,asset):raise ValueError('Reconstructed archive failed integrity: '+name)
    temporary.replace(target)
    # Only verified downloaded parts owned by this invocation are disposable.
    for part in asset['parts']:contained(cache,filename(part['name'])).unlink()
    print('VERIFIED_ARCHIVE',name,flush=True)
    return target

def extract(archive,destination):
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            target=contained(destination,info.filename)
            if (info.external_attr>>16)&0o170000==0o120000:raise ValueError('Symbolic link in archive')
            if info.is_dir():target.mkdir(parents=True,exist_ok=True);continue
            if target.exists():
                with z.open(info) as stream:expected=hashlib.file_digest(stream,'sha256').hexdigest()
                if not target.is_file() or sha(target)!=expected:raise ValueError('Existing extraction differs: '+str(target))
                continue
            target.parent.mkdir(parents=True,exist_ok=True)
            with z.open(info) as source,target.open('wb') as output:shutil.copyfileobj(source,output,1024*1024)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,default=HERE/'assets.json')
    parser.add_argument('--destination',type=Path,required=True)
    parser.add_argument('--historical',action='store_true',help='Also download the separate RT 2.1 recovery ZIP')
    parser.add_argument('--all',action='store_true',help='Also download individual media and audit files')
    parser.add_argument('--extract',action='store_true',help='Extract the four main project ZIPs after verification')
    args=parser.parse_args();manifest=json.loads(args.manifest.read_text(encoding='utf-8'))
    if manifest['schema']!=2 or manifest['repository']!='fribas001/differt-bridge':raise ValueError('Unsupported release manifest')
    prefix='https://github.com/fribas001/differt-bridge/releases/download/'+filename(manifest['release'])+'/'
    destination=args.destination.resolve();destination.mkdir(parents=True,exist_ok=True)
    cache=contained(destination,'.downloads');cache.mkdir(exist_ok=True)
    selected=set(manifest['required'])
    if args.historical:selected.update(manifest['optional_historical'])
    if args.all:selected={a['name'] for a in manifest['assets']}
    assets=[a for a in manifest['assets'] if a['name'] in selected]
    if {a['name'] for a in assets}!=selected:raise ValueError('Manifest is missing a selected asset')
    for asset in assets:
        if sum(p['bytes'] for p in asset['parts'])!=asset['bytes']:raise ValueError('Invalid part lengths')
        target=contained(destination,filename(asset['name']))
        if not correct(target,asset):
            with ThreadPoolExecutor(max_workers=6) as pool:
                list(pool.map(lambda row:download(row,cache,prefix),asset['parts']))
            target=assemble(asset,cache,destination)
        print('READY',asset['name'],flush=True)
        if args.extract and asset['name'] in manifest['required']:extract(target,destination)
    print('Recovery files ready. Run Replay.cmd verify, then Replay.cmd setup.',flush=True)
if __name__=='__main__':main()

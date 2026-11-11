"""Package audited local results and pinned Windows runtimes; never run simulations.

Archives are release assets, not Git objects. Original files are only read.
"""
from __future__ import annotations
import argparse, email, hashlib, json, os, re, subprocess, zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SKIP_PARTS = {'.git', '__pycache__', '.pytest_cache', 'gh-config', 'site-packages',
              'frames', 'decoded', 'temp', 'tmp', 'cache', 'jit-cache', 'node_modules'}
WORK_EXCLUDE = {'runtime', 'sionna-runtime', 'github-update', 'repro-build', 'project-archive',
                'rt21-restore-check', 'sionna-source', 'sionnart-reference'}
TEXT = {'.py', '.ps1', '.md', '.txt', '.html', '.json', '.csv', '.toml', '.xml', '.log', '.c', '.h', '.def', '.patch', '.js', '.css'}
DATA = TEXT | {'.npz', '.npy', '.h5', '.hdf5', '.ply', '.obj', '.mtl', '.blend', '.png', '.jpg', '.jpeg', '.svg', '.pdf', '.zip', '.sha256'}
SECRET = re.compile(rb'gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')

def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def read(path): return json.loads(path.read_text(encoding='utf-8-sig'))
def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')

def walk(root):
    for current, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in {'.git', '__pycache__', '.pytest_cache'} and not (Path(current)/d).is_symlink()]
        for name in sorted(names):
            p = Path(current)/name
            if not p.is_symlink() and p.suffix not in {'.pyc', '.pyo'}: yield p

def archive(output, name, files, metadata=None, generated=None):
    destination = output/name
    if destination.exists(): raise ValueError('Refusing to overwrite an archive: '+str(destination))
    def record(item):
        target, source = item
        if source.suffix.lower() in TEXT and source.stat().st_size < 20_000_000 and SECRET.search(source.read_bytes()):
            raise ValueError('Credential-like content requires review: '+str(source))
        return target, {'bytes':source.stat().st_size, 'sha256':sha(source)}
    with ThreadPoolExecutor(max_workers=8) as pool: records = dict(pool.map(record, sorted(files.items())))
    generated = generated or {}
    for target, data in generated.items():
        if target in records: raise ValueError('Duplicate generated target')
        records[target] = {'bytes':len(data), 'sha256':hashlib.sha256(data).hexdigest()}
    manifest = {'schema':1, 'asset':name, 'metadata':metadata or {}, 'files':records}
    print('PACK', name, len(records), 'files', flush=True)
    with zipfile.ZipFile(destination, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as z:
        for target, source in sorted(files.items()):
            z.write(source, target)
        for target, data in generated.items(): z.writestr(target, data)
        z.writestr('_manifests/'+name+'.json', json.dumps(manifest, indent=2)+'\n')
    # Validate content from the actual compressed archive, without a second full copy.
    with zipfile.ZipFile(destination) as z:
        for target, item in records.items():
            with z.open(target) as stream: actual = hashlib.file_digest(stream, 'sha256').hexdigest()
            if actual != item['sha256']: raise ValueError('Archive verification failed: '+target)
    result = {'name':name, 'bytes':destination.stat().st_size, 'sha256':sha(destination),
              'files':len(records), 'uncompressed_bytes':sum(r['bytes'] for r in records.values()), 'verified':True}
    save(output/(name+'.manifest.json'),manifest)
    print('VERIFIED', name, result['bytes'], flush=True)
    return result

def result_files(root, inventory):
    selected = {}; excluded = []; movies = {}
    for item in inventory['files']:
        name = item['path']; p = Path(name); parts = p.parts
        reason = None
        if any(v.lower() in SKIP_PARTS or v.lower().startswith('pytest-') for v in parts): reason='generated cache/frame sequence or installed dependency'
        elif parts[0]=='work' and (len(parts)<3 or parts[1] in WORK_EXCLUDE):
            if len(parts)==2 and p.suffix.lower() in TEXT: pass
            else: reason='runtime, packaging tools, upstream checkout or credential-bearing publishing tools'
        elif name.startswith('outputs/reproduction-windows-x64/') or name.startswith('outputs/rt21-recovery-windows-x64'): reason='separate runtime asset'
        elif name.startswith('work/retire-rt21/package/'): reason='temporary package copy'
        elif p.suffix.lower() in ('.mp4', '.webm'):
            if name.startswith('outputs/differt-bridge/examples/'): movies['workspace/'+name]=root/name
            reason='separate animations asset'
        elif p.suffix.lower() not in DATA: reason='non-scientific/generated payload type'
        if reason:
            excluded.append({'path':name,'bytes':item['bytes'],'reason':reason})
        else:
            source=root/name
            if source.is_file(): selected['workspace/'+name]=source
    return selected, movies, excluded

def runtime_files(root, shared):
    files={}; generated={}
    deps=read(root/'work/repro-build/differt-dependencies.json')['packages']
    baseline={}; sources={}; wheels={}
    for wheel in sorted((root/'outputs/reproduction-windows-x64/wheelhouse/differt').glob('*.whl')):
        with zipfile.ZipFile(wheel) as z:
            meta=email.message_from_bytes(z.read(next(n for n in z.namelist() if n.endswith('.dist-info/METADATA'))))
            name=re.sub(r'[-_.]+','-',meta['Name']).lower()
            if name not in deps or meta['Version']!=deps[name]['version']: raise ValueError('Unexpected dependency: '+wheel.name)
            wheels[name]={'name':meta['Name'],'version':meta['Version'],'file':wheel.name,'sha256':sha(wheel)}
            files['runtime_payload/differt/wheels/'+wheel.name]=wheel
            for n in z.namelist():
                if n.endswith('/') or '.data/' in n or '.dist-info/' in n: continue
                baseline[n]=hashlib.sha256(z.read(n)).hexdigest()
                sources[n]=Path(deps[name]['root'])/n
    if set(wheels)!=set(deps): raise ValueError('DiffeRT wheels incomplete')
    site=root/'work/runtime/Lib/site-packages'
    for p in walk(site):
        rel=p.relative_to(site)
        if rel.parts[0] in ('differt','_radio_dielectric_profile') or p.name=='radio_dielectric_profile.pth': sources[rel.as_posix()]=p
    def scientific(item):
        name, p=item
        if not p.is_file():raise ValueError('Missing installed scientific file: '+str(p))
        return name,sha(p)
    with ThreadPoolExecutor(max_workers=8) as pool: inventory=dict(pool.map(scientific, sorted(sources.items())))
    patches=[]
    for name,h in inventory.items():
        if baseline.get(name)!=h:
            files['runtime_payload/differt/patches/'+name]=sources[name]
            patches.append({'path':name,'before':baseline.get(name),'after':h})
    generated['runtime_payload/differt/requirements.lock']=''.join(f"{r['name']}=={r['version']} --hash=sha256:{r['sha256']}\n" for r in wheels.values()).encode()
    generated['runtime_payload/differt/spec.json']=json.dumps({'packages':wheels,'patches':patches,'scientific_files':inventory},indent=2).encode()
    # Capture the exact shared installation read-only. Restoration creates a fresh
    # venv and copies only its scientific package/native payload, never pyvenv.cfg
    # or old executable launchers. No original shared package is modified.
    for folder, target in [('Lib/site-packages','site'),('native','native')]:
        for p in walk(shared/folder):
            files['runtime_payload/rt22/'+target+'/'+p.relative_to(shared/folder).as_posix()]=p
    packages=read(shared/'environment-manifest.json')['packages']
    generated['runtime_payload/rt22/spec.json']=json.dumps({'packages':packages,'method':'exact installed package snapshot into a fresh isolated venv; console-script executables excluded'},indent=2).encode()
    base=Path(read(root/'work/repro-build/differt-dependencies.json')['base_prefix'])
    for p in walk(base):
        rel=p.relative_to(base)
        if 'site-packages' in rel.parts or p.suffix in ('.pdb','.lib'):continue
        if len(rel.parts)==1 or rel.parts[0] in ('Lib','DLLs'):
            files['vendor/python312/'+rel.as_posix()]=p
    for p in walk(REPO/'reproduction/rt21/licenses'): files['licenses/'+p.name]=p
    files['licenses/project-GPL-3.0.txt']=REPO/'LICENSE'
    for p in walk(root/'outputs/differt-bridge/scripts/runtime_profiles'):
        if p.suffix in ('.py','.c','.h','.txt'):files['licenses-and-sources/arithmetic/'+p.name]=p
    for name in ('replay.py','probe.py','blender_session.py','Replay.cmd','README.md'):
        files[name]=HERE/name
    addons=Path(os.environ['APPDATA'])/'Blender Foundation/Blender/5.2/extensions/user_default'
    for addon in ('differt_bridge','sionnart_bridge'):
        for p in walk(addons/addon):files['extensions/'+addon+'/'+p.relative_to(addons/addon).as_posix()]=p
    return files,generated,{'differt_packages':len(wheels),'differt_scientific_files':len(inventory),'differt_overlays':len(patches),'rt22_packages':len(packages)}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace',type=Path,required=True);p.add_argument('--shared',type=Path,required=True)
    p.add_argument('--inventory',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--part',choices=('results','runtimes','source'),required=True)
    a=p.parse_args();root=a.workspace.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    if a.part=='results':
        data,movies,excluded=result_files(root,read(a.inventory))
        save(out/'selection-exclusions.json',excluded)
        assets=[archive(out,'project-results.zip',data,{'scope':'historical evidence, inputs, reports and Blender scenes; no simulations rerun'}),
                archive(out,'project-animations.zip',movies,{'videos':len(movies)})]
        save(out/'results-assets.json',assets)
    elif a.part=='runtimes':
        files,generated,meta=runtime_files(root,a.shared.resolve())
        asset=archive(out,'project-runtimes-windows-x64.zip',files,meta,generated)
        save(out/'runtime-asset.json',asset)
    else:
        names=subprocess.check_output(['git','-C',str(REPO),'ls-files','--cached','--others','--exclude-standard','-z']).decode().split('\0')
        files={'workspace/work/github-update/differt-bridge/'+n:REPO/n for n in set(names) if n and (REPO/n).is_file()}
        meta={'base_commit':subprocess.check_output(['git','-C',str(REPO),'rev-parse','HEAD'],text=True).strip(),
              'provenance':'Exact working-tree snapshot; the manifest hashes identify all source files, including pending retirement work.'}
        asset=archive(out,'project-source.zip',files,meta)
        save(out/'source-asset.json',asset)
if __name__=='__main__':main()

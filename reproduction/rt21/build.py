"""Build a self-contained RT 2.1 recovery kit without executing scientific code."""
from __future__ import annotations
import argparse,email,hashlib,importlib.util,json,re,shutil,subprocess,zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE=Path(__file__).resolve().parent
PROJECT=HERE.parents[1]
def digest(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,data):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
def copy(a,b):b.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(a,b)
def tree(a,b,accept=lambda p:True):
    for p in a.rglob('*'):
        rel=p.relative_to(a)
        if p.is_file() and '__pycache__' not in rel.parts and p.suffix!='.pyc' and accept(rel):copy(p,b/rel)
def canonical(name):return re.sub(r'[-_.]+','-',name).lower()
def build(a):
    root=a.workspace.resolve();out=a.output.resolve();site=root/'work/sionna-runtime/Lib/site-packages'
    if out.exists() and (not a.resume or (out/'MANIFEST.json').exists()):raise ValueError('Use a fresh build directory, or --resume for an unsealed build')
    if out==root or root.is_relative_to(out) or out.is_relative_to(site):raise ValueError('Unsafe build directory')
    out.mkdir(parents=True,exist_ok=a.resume)
    deps=json.loads((a.audit/'sionna-dependencies.json').read_text())
    expected=deps['packages'];found={};baseline={}
    for wheel in sorted(a.wheelhouse.glob('*.whl')):
        with zipfile.ZipFile(wheel) as z:
            meta=email.message_from_bytes(z.read(next(n for n in z.namelist() if n.endswith('.dist-info/METADATA'))))
            name=canonical(meta['Name'])
            if name not in expected or meta['Version']!=expected[name]['version'] or name in found:raise ValueError('Unexpected wheel: '+wheel.name)
            found[name]=dict(name=meta['Name'],version=meta['Version'],file=wheel.name,sha256=digest(wheel))
            for n in z.namelist():
                if n.endswith('/') or '.data/' in n or '.dist-info/' in n:continue
                if '..' in Path(n).parts or Path(n).is_absolute():raise ValueError('Unsafe wheel path')
                baseline[n]=hashlib.sha256(z.read(n)).hexdigest()
        copy(wheel,out/'wheelhouse/sionna'/wheel.name)
    if set(found)!=set(expected):raise ValueError('Incomplete dependency wheelhouse')
    print('DEPENDENCY_WHEELS_VERIFIED',len(found),flush=True)
    (out/'wheelhouse/sionna.lock').write_text(''.join(f"{r['name']}=={r['version']} --hash=sha256:{r['sha256']}\n" for r in found.values()))
    save(out/'dependencies.json',dict(python=deps['python'],packages=found))
    # Compare all dependency payloads to the installed environment, not just
    # the previously audited Sionna/Dr.Jit packages. Also include opt-in hooks.
    names=set(baseline)
    names.update(p.relative_to(site).as_posix() for p in site.rglob('*') if p.is_file()
        and '__pycache__' not in p.parts and p.suffix!='.pyc'
        and (p.relative_to(site).parts[0] in ('sionna','drjit','mitsuba','_radio_dielectric_profile')
             or p.name=='radio_dielectric_profile.pth'))
    patches=[];inventory={}
    def installed_hash(name):
        source=site/name
        if not source.is_file():raise ValueError('Installed dependency file missing: '+name)
        return name,digest(source)
    with ThreadPoolExecutor(max_workers=8) as pool: hashes=list(pool.map(installed_hash,sorted(names)))
    print('SCIENTIFIC_FILES_HASHED',len(hashes),flush=True)
    for name,h in hashes:
        source=site/name;inventory[name]=h
        if baseline.get(name)!=h:
            copy(source,out/'patches'/name)
            patches.append(dict(path=name,before_sha256=baseline.get(name),after_sha256=h,
                                relocate_llvm=name=='drjit/_bridge_llvm/manifest.json'))
    save(out/'scientific-files.json',inventory);save(out/'patches.json',dict(files=patches))
    print('OVERLAYS_CAPTURED',len(patches),flush=True)
    base=Path(json.loads((a.audit/'sionna-audit.json').read_text())['base_prefix'])
    tree(base,out/'vendor/python313',lambda p:'site-packages' not in p.parts and p.suffix not in ('.pdb','.lib'))
    copy(a.llvm,out/'vendor/llvm/LLVM-C.dll')
    llvm=json.loads((site/'drjit/_bridge_llvm/manifest.json').read_text())
    if digest(a.llvm)!=llvm['original_llvm_sha256']:raise ValueError('LLVM binary changed')
    # Include source/license notices for the runtime adapter and copied CPython.
    tree(root/'outputs/differt-bridge/runtime_patches',out/'sources/runtime_patches',lambda p:p.suffix in ('.c','.py','.def','.json','.txt'))
    copy(PROJECT/'scripts/rt22_profiles/LICENSE.apache-2.0',out/'licenses/Apache-2.0.txt')
    copy(PROJECT/'LICENSE',out/'licenses/project-GPL-3.0.txt')
    tree(HERE/'licenses',out/'licenses')
    blender=base.parents[1]
    if (blender/'copyright.txt').exists():copy(blender/'copyright.txt',out/'licenses/Blender-copyright.txt')
    # Freeze the committed project as it existed before launcher retirement.
    commit=subprocess.check_output(['git','-C',str(PROJECT),'rev-parse','HEAD'],text=True).strip()
    archive=out/'project-source.zip'
    subprocess.run(['git','-C',str(PROJECT),'archive','--format=zip','-o',str(archive),commit],check=True)
    with zipfile.ZipFile(archive) as z:z.extractall(out/'project')
    # One authoritative source copy in the final kit; exclude the intermediate ZIP.
    archive.unlink()
    backup=root/'work/retire-rt21/launchers-before'
    if backup.exists():tree(backup,out/'historical-launchers')
    else:
        for p in root.glob('*.ps1'):copy(p,out/'historical-launchers'/p.name)
        for p in (root/'outputs/differt-bridge/examples').rglob('Launch*.ps1'):copy(p,out/'historical-launchers'/p.relative_to(root))
    for folder in ('work/dielectric-corrections/final','work/d3res'):
        tree(root/folder,out/'reference'/folder,lambda p:p.suffix in ('.json','.npz','.npy','.xml','.ply','.csv'))
    phase=root/'outputs/differt-bridge/examples/segment_length_aligned'
    for name in ('analysis.json','coefficients.npz','blender_validation.json','installed_validation.json','rerun_validation.json','Shared_Segment_Length_Workbench.blend','index.html'):
        if (phase/name).is_file():copy(phase/name,out/'reference/phase'/name)
    for p in (root/'work/migrate-research22').glob('*comparison.json'):copy(p,out/'reference/migration'/p.name)
    for p in HERE.iterdir():
        if p.is_file() and p.name!='build.py':copy(p,out/p.name)
    save(out/'BUNDLE.json',dict(schema=1,scope='Historical Sionna RT 2.1 Windows x64 recovery',source_commit=commit,
         python=deps['python'],dependency_packages=len(found),scientific_files=len(inventory),overlays=len(patches),
         simulations_run=False,llvm_sha256=digest(a.llvm),old_environment_bytes=sum(p.stat().st_size for p in (root/'work/sionna-runtime').rglob('*') if p.is_file())))
    print('PAYLOAD_COPIED',flush=True)
    def record(p):return p.relative_to(out).as_posix(),dict(bytes=p.stat().st_size,sha256=digest(p))
    with ThreadPoolExecutor(max_workers=8) as pool:manifest=dict(pool.map(record,sorted(p for p in out.rglob('*') if p.is_file())))
    save(out/'MANIFEST.json',dict(schema=1,files=manifest))
    print(json.dumps(dict(bundle=str(out),files=len(manifest),bytes=sum(x['bytes'] for x in manifest.values()),overlays=len(patches)),indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--resume',action='store_true')
    for key in ('workspace','output','audit','wheelhouse','llvm'):p.add_argument('--'+key,type=Path,required=True)
    build(p.parse_args())

"""Assemble an offline Windows reproduction bundle from an audited workspace.

No installed runtime is modified. Wheel downloads are supplied separately;
the archive contains exact wheels, portable tools, overlays and reference data.
"""
from __future__ import annotations
import argparse
import email
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tomllib
import zipfile

PROJECT = Path(__file__).resolve().parents[1]


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def copy(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists() or sha(destination) != sha(source):
        shutil.copyfile(source, destination)


def tree(source, destination, accept=lambda p: True):
    count = size = 0
    for path in source.rglob('*'):
        if not path.is_file() or '__pycache__' in path.parts or path.suffix == '.pyc':
            continue
        relative = path.relative_to(source)
        if accept(relative):
            copy(path, destination / relative)
            count += 1; size += path.stat().st_size
    return dict(files=count, bytes=size)


def canonical(name):
    return re.sub(r'[-_.]+', '-', name).lower()


def wheels(bundle, audit, engine):
    dependencies = read(audit / f'{engine}-dependencies.json')['packages']
    found = {}; paths = {}; licenses = []
    for path in sorted((bundle / 'wheelhouse' / engine).glob('*.whl')):
        with zipfile.ZipFile(path) as archive:
            info = next(name for name in archive.namelist() if name.endswith('.dist-info/METADATA'))
            metadata = email.message_from_bytes(archive.read(info))
            name = canonical(metadata['Name'])
            if name not in dependencies or metadata['Version'] != dependencies[name]['version']:
                raise ValueError('Unexpected wheel: ' + path.name)
            if name in found:
                raise ValueError('Multiple wheels for ' + name)
            found[name] = dict(name=metadata['Name'], version=metadata['Version'],
                               file=path.relative_to(bundle).as_posix(), sha256=sha(path))
            paths[name] = path
            for member in archive.namelist():
                if not member.endswith('/') and '.dist-info/' in member and any(t in member.lower() for t in ('license', 'copying', 'notice')):
                    licenses.append(dict(wheel=path.name, member=member))
    if set(found) != set(dependencies):
        raise ValueError('Missing wheels: ' + str(set(dependencies) - set(found)))
    lock = '\n'.join(f"{item['name']}=={item['version']} --hash=sha256:{item['sha256']}" for item in found.values()) + '\n'
    (bundle / 'wheelhouse' / f'{engine}.lock').write_text(lock, encoding='utf-8')
    save(bundle / 'wheelhouse' / f'{engine}.json', dict(packages=list(found.values()), licenses_in_wheels=licenses))
    return paths


def patches(bundle, audit, workspace, engine, wheel_paths):
    result = []
    for row in read(audit / f'{engine}-audit.json')['changes']:
        name = row['path']; source = Path(row['source']); before = None
        wheel = wheel_paths[canonical(row['distribution'])]
        with zipfile.ZipFile(wheel) as archive:
            if name in archive.namelist():
                before = hashlib.sha256(archive.read(name)).hexdigest()
        if sha(source) != row['sha256']:
            raise ValueError('Audited runtime changed: ' + name)
        destination = bundle / 'patches' / engine / name
        copy(source, destination)
        reliability = engine == 'sionna' and (name.startswith('drjit/') or name in
            ('sionna/rt/__init__.py', 'sionna/rt/_bridge_llvm_lifetime.py'))
        result.append(dict(path=name, before_sha256=before, after_sha256=row['sha256'],
                           category='reliability' if reliability else 'research',
                           relocate_llvm=name == 'drjit/_bridge_llvm/manifest.json'))
    site = workspace / 'work' / ('runtime' if engine == 'differt' else 'sionna-runtime') / 'Lib/site-packages'
    for source in [site / 'radio_dielectric_profile.pth', *sorted((site / '_radio_dielectric_profile').glob('*.py'))]:
        relative = source.relative_to(site).as_posix()
        copy(source, bundle / 'patches' / engine / relative)
        result.append(dict(path=relative, before_sha256=None, after_sha256=sha(source), category='research', relocate_llvm=False))
    save(bundle / 'patches' / f'{engine}.json', dict(engine=engine, files=result))
    return len(result)


def references(workspace, bundle):
    scientific = {'mer','mre','dcr','dw','di','n3f','n3g','n3h','n3ps','n3r','n3smoke'}
    prefixes = ('d3','dielectric','native3d','maxwell','model-error','refinement','diffraction','rc')
    suffixes = {'.json','.npz','.npy','.ply','.xml','.csv','.ps1'}
    def accept(path):
        return path.suffix.lower() in suffixes and not any(
            'cache' in part.lower() or part.startswith('pytest') or part in ('temp','frames','decoded','previews') for part in path.parts)
    inventory = {}
    for folder in sorted((workspace / 'work').iterdir()):
        if folder.is_dir() and (folder.name.startswith(prefixes) or folder.name in scientific) and 'test-temp' not in folder.name:
            inventory['work/' + folder.name] = tree(folder, bundle / 'reference/work' / folder.name, accept)
    # Include baseline reports and validation receipts, without duplicate videos,
    # historical source snapshots or disposable image sequences.
    examples = workspace / 'outputs/differt-bridge/examples'
    for folder in sorted(examples.iterdir()):
        if folder.is_dir() and folder.name.startswith(('dielectric','native3d','maxwell','diffraction','model_error')):
            inventory['examples/' + folder.name] = tree(folder, bundle / 'reference/outputs/differt-bridge/examples' / folder.name,
                lambda p: p.suffix.lower() in {'.json','.html','.png','.svg'} and not any(x in ('frames','decoded','previews','src','scripts','runtime-profile') for x in p.parts))
    save(bundle / 'reference/inventory.json', inventory)
    return dict(files=sum(v['files'] for v in inventory.values()), bytes=sum(v['bytes'] for v in inventory.values()))


def extension(source, destination):
    manifest = tomllib.loads((source / 'blender_manifest.toml').read_text(encoding='utf-8'))
    for name in ['blender_manifest.toml', *manifest['build']['paths']]:
        copy(source / name, destination / name)
    return dict(id=manifest['id'], version=manifest['version'])


def build(args):
    workspace = args.workspace.resolve(); bundle = args.output.resolve(); audit = args.audit.resolve()
    if bundle == workspace or bundle == PROJECT or workspace.is_relative_to(bundle):
        raise ValueError('Bundle must be a distinct child/output directory')
    bundle.mkdir(parents=True, exist_ok=True)
    metadata = dict(schema_version=1, platform='windows-x64', source_commit=subprocess.check_output(
        ['git','-C',str(PROJECT),'rev-parse','HEAD'],text=True).strip(), patches={})
    for engine in ('differt','sionna'):
        paths = wheels(bundle, audit, engine)
        metadata['patches'][engine] = patches(bundle,audit,workspace,engine,paths)
    python_base = Path(read(audit / 'differt-audit.json')['base_prefix'])
    metadata['python312'] = tree(python_base, bundle / 'vendor/python312',
        lambda p: (len(p.parts)==1 and p.suffix.lower() in ('.exe','.dll','.txt')) or
        (p.parts[0] in ('Lib','DLLs') and 'site-packages' not in p.parts and p.suffix not in ('.pdb','.lib')))
    metadata['blender'] = tree(args.blender.resolve(), bundle / 'vendor/blender',
        lambda p: p.suffix.lower() not in ('.pdb','.lib') and p.name.lower() != 'uninstall.exe')
    copy(args.llvm.resolve(), bundle / 'vendor/llvm/LLVM-C.dll')
    metadata['llvm_sha256'] = sha(args.llvm.resolve())
    tracked = subprocess.check_output(['git','-C',str(PROJECT),'ls-files','-z']).decode().split('\0')
    for name in tracked:
        if name: copy(PROJECT/name,bundle/'project'/name)
    tree(PROJECT/'reproduction',bundle/'runner',lambda p:p.suffix in ('.py','.md'))
    for name in ('reproduce.py','Reproduce.cmd','README.md'):
        copy(PROJECT/'reproduction'/name,bundle/name)
    metadata['extensions'] = [extension(PROJECT/'src/differt_bridge',bundle/'extensions/differt_bridge'),
        extension(args.sionna_extension.resolve(),bundle/'extensions/sionnart_bridge')]
    metadata['references'] = references(workspace,bundle)
    tree(workspace/'outputs/differt-bridge/scripts/runtime_profiles',bundle/'patches/sources/arithmetic',
         lambda p:p.suffix in ('.c','.h','.py','.txt'))
    tree(workspace/'outputs/differt-bridge/runtime_patches',bundle/'patches/sources/llvm',
         lambda p:p.suffix in ('.c','.py','.def','.json'))
    # Exact interpreter and solver provenance, without workstation path strings.
    metadata['interpreters'] = {'differt':read(audit/'differt-dependencies.json')['python'],
                               'sionna':read(audit/'sionna-dependencies.json')['python']}
    metadata['scope'] = 'CPU reproduction; native baselines, historical research overlays and independent Maxwell reference are separately labelled.'
    save(bundle/'bundle.json',metadata)
    print(json.dumps(metadata,indent=2),flush=True)


if __name__=='__main__':
    raise SystemExit('Four-runtime bundle remains a draft. Use reproduction/rt21 for the completed RT 2.1 recovery kit.')
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('workspace','output','audit','blender','llvm','sionna-extension'):
        p.add_argument('--'+key,type=Path,required=True)
    build(p.parse_args())

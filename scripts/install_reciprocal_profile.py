"""Install an opt-in profile without overwriting any engine or extension file."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path

FILES=('radio_dielectric_bootstrap.py','reciprocal_corrections.py','reciprocal_geometry.py',
       'reciprocal_jax.py','reciprocal_boundary.py','diffraction_physics_worker.py')
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def install(root):
    raise RuntimeError('Historical installation retired; use the RT 2.1 recovery package. Shared RT 2.2 uses process-local profiles.')
    root=root.resolve();source=Path(__file__).resolve().parent
    target=root/'outputs/differt-bridge/validation/reciprocal_profile.json'
    prior=json.loads(target.read_text()) if target.exists() else {'added_files':{}}
    added={};engines={}
    for engine,folder in [('differt','runtime'),('sionna','sionna-runtime')]:
        runtime=root/'work'/folder;python=runtime/'Scripts/python.exe';site=runtime/'Lib/site-packages'
        if not python.is_file() or not site.is_dir():raise RuntimeError('Missing local runtime '+str(runtime))
        package=site/'_radio_dielectric_profile'
        payload={package/name:(source/name).read_bytes() for name in FILES}
        payload[site/'radio_dielectric_profile.pth']=b'_radio_dielectric_profile\nimport radio_dielectric_bootstrap; radio_dielectric_bootstrap.activate()\n'
        for path,data in payload.items():
            name=path.relative_to(root).as_posix()
            if path.exists() and path.read_bytes()!=data:
                if name not in prior['added_files'] or digest(path)!=prior['added_files'][name]:
                    raise RuntimeError('Refusing to overwrite unowned or modified file: '+str(path))
        for path,data in payload.items():
            path.parent.mkdir(exist_ok=True);path.write_bytes(data);added[path.relative_to(root).as_posix()]=digest(path)
        engines[engine]=dict(python=str(python),activation='RADIO_DIELECTRIC_PROFILE=reciprocal',default='native')
    receipt=dict(status='installed',profile='reciprocal',scope='Opt-in bridge runtime approximation; see dielectric_corrections report for independent validation and limits.',
                 engines=engines,added_files=added,source_files={name:digest(source/name) for name in FILES},
                 rollback='Unset RADIO_DIELECTRIC_PROFILE to restore native behavior immediately. To uninstall, remove only the 14 added_files listed here after verifying their hashes. No existing engine source or installed Blender extension was overwritten.')
    target.write_text(json.dumps(receipt,indent=2),encoding='utf-8');print(target)

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('workspace',type=Path);args=ap.parse_args();install(args.workspace)

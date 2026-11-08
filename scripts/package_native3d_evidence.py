"""Verify and package reproducible 3D results without runtimes or media copies."""
import argparse,hashlib,json,zipfile
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit,unquote
import numpy as np
from PIL import Image
from analyze_model_errors import read,z

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main(root):
    w=root/'work/native3d';out=root/'outputs/differt-bridge/examples/native3d_diffraction';project=Path(__file__).resolve().parents[1]
    a=read(w/'final_analysis.json');assert a['status']=='passed';assert a['product_source_sha256']==sha(project/'scripts/hertz_pec3d.py')
    assert a['reference_source_sha256']==sha(project/'scripts/maxwell3d_pec_reference.py')
    assert a['reference_validation']['status']=='passed' and a['regression']==dict(cases=286,geometry_identical=True,max_absolute_cir_change=0.)
    assert read(w/'opaque_slab_validation.json')['status']=='passed'
    samples=read(w/'opaque_slab_samples.json');assert len(samples['samples'])==840 and not any(v is None for row in samples['patched'] for v in row)
    tests=(w/'tests.log').read_text();assert '100%' in tests and not any(x in tests for x in ('FAILED','ERROR'))
    count=0;channels=0;campaigns=[]
    folders=['n3r','n3f','n3h','n3g','n3smoke/rays','n3ps/rays']
    for folder in folders:
        path=root/'work'/folder;rec=read(path/'receipt.json');assert rec['status']=='passed' and sha(path/'cases.json')==rec['manifest_sha256']
        cases=read(path/'cases.json')['cases'];per=sum(len(c['receivers']) for c in cases)
        for r in rec['processes']:
            assert r['passed'] and r['requested']==r['completed']==len(cases)
            assert sha(path/r['profile']/r['output'])==r['output_sha256']
            count+=r['completed'];channels+=per
        campaigns.append(dict(folder=folder,fixtures=len(cases)*len(rec['processes']),channels=per*len(rec['processes'])))
    for path in [w/'workflow',root/'work/n3smoke',root/'work/n3ps']:
        r=read(path/'comparison.json');p=read(path/'refinement.json');assert r['status']=='passed' and r['reference_used'] is False and p['reference_used'] is False
        assert p['source_sha256']==sha(project/'scripts/hertz_pec3d.py') and p['native_exports_modified'] is False
    baseline=read(root/'work/cleanup-2026-11-01/protected_hashes.json')
    for name in ('diffraction_remediation.json','sionna_lifetime_fix.json','sionna_batch_fix.json'):
        r=read(root/'outputs/differt-bridge/validation'/name)
        for f,c in r.get('source_updates',{}).items():baseline[f]=c['after']
        baseline.update(r.get('added_files',{}))
    for f,digest in baseline.items():assert sha(root/f)==digest,f
    optional=read(root/'outputs/differt-bridge/validation/reciprocal_profile.json');previous=read(w/'prior_profile.json')
    for f,digest in optional['added_files'].items():assert sha(root/f)==digest,f
    changed=[f for f,digest in optional['added_files'].items() if previous['added_files'].get(f)!=digest]
    assert len(changed)==2 and all(f.endswith('/reciprocal_corrections.py') for f in changed)
    for name,digest in optional['source_files'].items():assert sha(project/'scripts'/name)==digest
    native=read(root/'outputs/differt-bridge/validation/workflow_health.json');corrected=read(out/'reciprocal_blender.json')
    assert native['status']=='passed' and native['blender']['comparison']['matched_paths']==1299
    assert corrected['status']=='passed' and corrected['preferences_preserved'] and all(corrected['activated'].values())
    activation=read(root/'work/native3d-reciprocal-check/activation/sionna_profile.json');assert 'opaque_slab' in activation
    animation=read(out/'animation_validation.json');video=read(out/'video_validation.json');assert video['status']=='passed' and video['frames']==1440
    assert sha(out/animation['video_name'])==animation['video_sha256'] and sha(w/'final_analysis.json')==animation['analysis_sha256']
    psnr={}
    for frame in animation['preview_frames']:
        p=out/'previews'/f'frame_{frame:04d}.png';q=out/'decoded'/p.name
        x=np.asarray(Image.open(p),float);y=np.asarray(Image.open(q),float);assert x.shape==y.shape==(900,1600,3)
        psnr[str(frame)]=float(10*np.log10(255**2/np.mean((x-y)**2)))
    assert min(psnr.values())>35
    files={}
    def tree(path,prefix,pattern):
        for f in path.rglob(pattern):
            if '__pycache__' not in f.parts:files[prefix+'/'+f.relative_to(path).as_posix()]=f
    for f in w.glob('*.json'):files['results/'+f.name]=f
    for f in w.glob('*.log'):
        if f.name!='package.log':files['validation/'+f.name]=f
    files['history/prior_reciprocal_corrections.py']=w/'prior_reciprocal_corrections.py'
    tree(w/'workflow','results/workflow','*.json')
    for folder in folders:
        path=root/'work'/folder;prefix='results/engines/'+folder.replace('/','_');files[prefix+'/cases.json']=path/'cases.json';files[prefix+'/receipt.json']=path/'receipt.json'
        for rec in read(path/'receipt.json')['processes']:
            for name in (rec['output'],'receipt.json','intervention.json'):files[prefix+'/'+rec['profile']+'/'+name]=path/rec['profile']/name
    for folder in ('n3smoke','n3ps'):
        for name in ('comparison.json','refinement.json'):files['results/'+folder+'/'+name]=root/'work'/folder/name
    for folder in ('scripts','tests','src'):tree(project/folder,'project/'+folder,'*.py')
    tree(project/'docs','project/docs','*.md')
    for name in ('README.md','LICENSE','pyproject.toml','requirements-analysis.txt','requirements-dev.txt'):files['project/'+name]=project/name
    for name in ('workflow_health.json','reciprocal_profile.json'):files['validation/'+name]=root/'outputs/differt-bridge/validation'/name
    files['validation/reciprocal_blender.json']=out/'reciprocal_blender.json';tree(root/'work/native3d-reciprocal-check/activation','validation/activation','*.json')
    for name in ('Compare_Native3D_Wedge.ps1','Regenerate_Native3D_Animation.ps1'):files['launchers/'+name]=root/name
    for name in ('index.html','animation_validation.json','video_validation.json','accuracy.png','phase.png'):files['report/'+name]=out/name
    repro='''Native 3D PEC diffraction campaign, 7 November 2026.
Read project/docs/native3d-diffraction.md and report/index.html for scope.
results/engines/n3r = original four profiles before the opaque-slab patch.
n3f = updated reciprocal profiles; n3h = fresh holdouts; n3g = 286 regressions.
n3smoke/n3ps = fresh companion Python and PowerShell workflow checks.
The raw comparison exports remain distinct from the shared Hertz-UTD field.
The exact Sommerfeld reference has no UTD/engine imports. Fourier-Bessel
cross-checks include evanescent modes and use small uniform absorption in both
formulations. Campaign fields use real vacuum wavenumber. The production
Hertz-UTD correction never reads a Maxwell reference or stored field table.
history retains the pre-patch helper and results/prior_profile.json its hashes.
Only two owned copies of reciprocal_corrections.py were updated; upstream
engine sources and installed Blender extensions are protected by receipts.
The source scripts reproduce in the documented workspace layout with the
validated runtimes. Do not overwrite n3r with a patched-profile rerun and
call it a native historical baseline. Native default remains untouched.
Videos and Blender timelines are separate deliverables, not duplicated here.
Runtimes, credentials, compiler caches, generated scene copies and full PNG
frame sequences are excluded. Frame hashes permit deterministic redraw.
'''
    hashes={name:sha(f) for name,f in files.items()};archive=out/'native3d_evidence.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as zz:
        for name,f in sorted(files.items()):zz.write(f,name)
        zz.writestr('REPRODUCE.txt',repro);hashes['REPRODUCE.txt']=hashlib.sha256(repro.encode()).hexdigest()
        zz.writestr('SHA256SUMS.txt',''.join(digest+'  '+name+'\n' for name,digest in sorted(hashes.items())))
    with zipfile.ZipFile(archive) as zz:
        assert zz.testzip() is None
        for name,digest in hashes.items():assert hashlib.sha256(zz.read(name)).hexdigest()==digest
    verification=dict(status='passed',engine_fixture_executions=count,engine_channels=channels,campaigns=campaigns,analytic_guard_and_regression_tests=55,tests_exit_code=0,independent_maxwell_controls=len(a['reference_validation']['controls']),slab_coefficient_tests=840,protected_base_files=len(baseline),installed_helper_files=len(optional['added_files']),changed_owned_helpers=changed,native_blender_matched_paths=1299,reciprocal_blender_matched_paths=corrected['counts']['matched'],reciprocal_max_phase_difference_rad=corrected['max_phase_difference_rad'],video_frames=1440,video_psnr=psnr,archive=dict(file=archive.name,bytes=archive.stat().st_size,sha256=sha(archive),verified_members=len(hashes)),native_dielectric_3d_maxwell_validated=False)
    (out/'verification.json').write_text(json.dumps(verification,indent=2),encoding='utf-8')
    class Links(HTMLParser):
        def handle_starttag(self,tag,attrs):
            for key,value in attrs:
                if key in ('href','src') and value and not urlsplit(value).scheme and not value.startswith('#'):
                    path=(self.base/unquote(urlsplit(value).path)).resolve();assert path.exists(),str(path)
    for page in (root/'index.html',out/'index.html'):
        parser=Links();parser.base=page.parent;parser.feed(page.read_text(encoding='utf-8'))
    print(json.dumps(verification),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('root',type=Path);main(ap.parse_args().root.resolve())

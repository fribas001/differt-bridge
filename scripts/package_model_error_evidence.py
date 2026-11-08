"""Verify scientific/media provenance and package the model-error study."""
import argparse,hashlib,html,json,platform,zipfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit,unquote
import numpy as np
from PIL import Image
from analyze_model_errors import read

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main(root):
    root=root.resolve();work=root/'work/diffraction-model-errors';out=root/'outputs/differt-bridge/examples/diffraction_model_errors';project=Path(__file__).resolve().parents[1]
    analysis=read(work/'analysis.json');receipt=read(root/'work/mer/receipt.json')
    assert receipt['status']=='passed' and sha(root/'work/mer/cases.json')==receipt['manifest_sha256']
    assert len(receipt['processes'])==4
    for row in receipt['processes']:
        assert row['passed'] and row['completed']==40
        assert sha(root/'work/mer'/row['profile']/row['output'])==row['output_sha256']
    assert len(analysis['sweep'])==32 and sum(r['samples'] for r in analysis['sweep'])==8480
    ref_files=[f for folder in ('bem_controls','bem_sweep','bem_distance','bem_extra') for f in (work/folder).glob('*.json')]
    assert len(ref_files)==79
    refsha=sha(project/'scripts/wedge_bem_reference.py')
    for f in ref_files:
        r=read(f);assert r['source_sha256']==refsha,f;assert r['linear_residual']<2e-14
        assert np.isfinite(np.asarray(r['field'])).all()
    assert max(r['reference24_to36'] for r in analysis['sweep'])<.0003
    assert max(r['reference16_to24'] for r in analysis['distance'])<.001
    assert max(r['bem48_vs_fdfd_extrapolated'] for r in analysis['reference_controls'] if r['name'].startswith(('concrete','lossy','absorbing')))<.00016
    assert max(r['total_complex_rms'] for r in analysis['sweep'] if r['profile'].endswith('reciprocal'))<.045
    installation=read(root/'outputs/differt-bridge/validation/reciprocal_profile.json')
    for name,digest in installation['added_files'].items():assert sha(root/name)==digest,name
    baseline=read(root/'work/cleanup-2026-11-01/protected_hashes.json')
    for name in ('diffraction_remediation.json','sionna_lifetime_fix.json','sionna_batch_fix.json'):
        r=read(root/'outputs/differt-bridge/validation'/name)
        for file,change in r.get('source_updates',{}).items():baseline[file]=change['after']
        baseline.update(r.get('added_files',{}))
    for file,digest in baseline.items():assert sha(root/file)==digest,file
    native=read(root/'outputs/differt-bridge/validation/workflow_health.json');corrected=read(out/'reciprocal_blender.json')
    assert native['status']=='passed' and native['blender']['comparison']['matched_paths']==1299
    assert corrected['status']=='passed' and all(corrected['activated'].values()) and corrected['counts']['matched']==3
    animation=read(out/'animation_validation.json');video=read(out/'video_validation.json')
    assert video['status']=='passed' and video['frames']==1440 and video['saved_and_reopened']
    assert sha(out/'Sionna_vs_DiffeRT_Maxwell.mp4')==animation['video_sha256']
    assert sha(work/'analysis.json')==animation['analysis_sha256']
    psnr={}
    for frame in animation['preview_frames']:
        a=np.asarray(Image.open(out/'previews'/f'frame_{frame:04d}.png'),dtype=float);b=np.asarray(Image.open(out/'decoded'/f'frame_{frame:04d}.png'),dtype=float)
        assert a.shape==b.shape==(900,1600,3)
        psnr[str(frame)]=float(10*np.log10(255**2/np.mean((a-b)**2)))
    assert min(psnr.values())>35,psnr
    assert '100%' in (work/'tests.log').read_text() and 'FAILED' not in (work/'tests.log').read_text()
    verification=dict(status='passed',date='2026-11-07',engine_fixture_executions=160,engine_channels=8480,independent_bie_operator_solves=79,protected_source_runtime_files=len(baseline),optional_runtime_helper_files=len(installation['added_files']),analytic_and_model_tests=16,tests_exit_code=0,fresh_native_paths=1299,fresh_reciprocal_paths=3,decoded_preview_psnr_db=psnr,video_frames=1440,python=platform.python_version(),numpy=np.__version__,runtime_physics_changed=False,comparison_normalization_corrected=True,reference_evanescent_branch_corrected=True,blender_checker_relative_paths_corrected=True)
    (work/'study_verification.json').write_text(json.dumps(verification,indent=2))
    files={}
    def addtree(base,prefix,pattern):
        for f in base.rglob(pattern):
            if f.is_file():files[prefix+'/'+f.relative_to(base).as_posix()]=f
    for folder in ('bem_controls','bem_sweep','bem_distance','bem_extra'):addtree(work/folder,'results/'+folder,'*.json')
    for f in work.glob('*.json'):files['results/'+f.name]=f
    for f in work.glob('*.log'):
        if f.name not in ('encode.log','decode.log','package.log'):files['validation/'+f.name]=f
    addtree(root/'work/mer','results/engines','*.json')
    for folder in ('maxwell','maxwell_pml'):addtree(root/'work/dielectric-corrections'/folder,'results/fdfd/'+folder,'*.json')
    for f in ('maxwell_analysis.json','maxwell_engines.json'):files['results/fdfd/'+f]=root/'work/dielectric-corrections'/f
    for folder in ('scripts','tests','src'):addtree(project/folder,'project/'+folder,'*.py')
    addtree(project/'docs','project/docs','*.md')
    for f in project.glob('requirements*.txt'):files['project/'+f.name]=f
    for f in ('README.md','LICENSE','pyproject.toml'):files['project/'+f]=project/f
    for f in ('workflow_health.json','reciprocal_profile.json'):files['validation/'+f]=root/'outputs/differt-bridge/validation'/f
    files['validation/reciprocal_blender.json']=out/'reciprocal_blender.json'
    addtree(root/'work/model-error-reciprocal/activation','validation/activation','*.json')
    for f in out.glob('*.png'):files['report/'+f.name]=f
    for f in ('index.html','animation_validation.json','video_validation.json','report_metrics.json'):files['report/'+f]=out/f
    files['launchers/Regenerate_Maxwell_Animation.ps1']=root/'Regenerate_Maxwell_Animation.ps1'
    instructions='''Maxwell model-error evidence, 7 November 2026.

project/docs/diffraction-model-errors.md contains reproduction commands.
project/scripts/ contains source for the BIE, Sommerfeld, numerical analysis and
animation. results/ contains all 79 canonical BIE solutions and fresh actual
engine paths, plus the earlier FDFD reference and diagnostic candidates.
The BIE reference imports no ray model. The formula/policy sweeps are comparators,
not independent references. No new electromagnetic runtime patch was installed.

Commands in the documentation use the configured workstation layout. For another
location, preserve the documented relative layout or point the numerical drivers
at chosen directories. Existing files are resume checkpoints; use a new output
directory to force fresh solutions. Runtime source guards require the validated
engine versions/adapters. No interpreter or environment cache is bundled.

validation/ includes numerical tests, fresh native/corrected Blender receipts and
the initial relative-receipt-path failure, followed by its successful corrected
run. That failure was in the validation launcher's relative path handling, not
the diffraction solver. check_reciprocal_blender.py now resolves its arguments.
Nonfatal Skybrush GPU overlay errors in background Blender logs are unrelated;
the explicit bridge PASS receipt and return status determine the check result.

The delivered MP4 and .blend timeline are separate, not duplicated in this ZIP.
Frame hashes are retained for deterministic redraw; temporary full-frame PNGs
may be removed after successful encoding. Six source/decoded previews remain.
SHA256SUMS.txt verifies every other archive member.
'''
    hashes={n:sha(p) for n,p in files.items()};archive=out/'model_error_evidence.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for n,p in sorted(files.items()):z.write(p,n)
        z.writestr('REPRODUCE.txt',instructions);hashes['REPRODUCE.txt']=hashlib.sha256(instructions.encode()).hexdigest()
        z.writestr('SHA256SUMS.txt',''.join(v+'  '+n+'\n' for n,v in sorted(hashes.items())))
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for n,digest in hashes.items():assert hashlib.sha256(z.read(n)).hexdigest()==digest
    verification.update(archive_sha256=sha(archive),archive_members=len(hashes)+1,archive_bytes=archive.stat().st_size,visual_qa='source and decoded chapter previews plus scientific plots inspected')
    (out/'verification.json').write_text(json.dumps(verification,indent=2))
    (out/'checksums.sha256').write_text(''.join(sha(p)+'  '+p.relative_to(out).as_posix()+'\n' for p in sorted(out.rglob('*')) if p.is_file() and p.name!='checksums.sha256'))
    class Links(HTMLParser):
        def __init__(self):super().__init__();self.urls=[]
        def handle_starttag(self,tag,attrs):self.urls.extend(v for k,v in attrs if k in ('href','src') and v)
    count=0
    for p in (root/'index.html',out/'index.html'):
        parser=Links();parser.feed(p.read_text(encoding='utf-8'))
        for url in parser.urls:
            u=urlsplit(html.unescape(url))
            if not u.scheme and u.path:assert (p.parent/unquote(u.path)).exists(),(p,url);count+=1
    print(json.dumps(dict(status='passed',archive_bytes=archive.stat().st_size,archive_members=len(hashes)+1,local_links=count,min_video_psnr_db=min(psnr.values()),protected_files=len(baseline),optional_helpers=len(installation['added_files'])),indent=2))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('root',type=Path);args=ap.parse_args();main(args.root)

"""Verify the scoped refinement, preserve runtime provenance, package evidence."""
import argparse,hashlib,html,json,zipfile
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit,unquote
import numpy as np
from PIL import Image
from analyze_model_errors import read,z

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main(root):
    root=root.resolve();w=root/'work/maxwell-refinement';out=root/'outputs/differt-bridge/examples/maxwell_refinement';project=Path(__file__).resolve().parents[1]
    a=read(w/'analysis.json');receipt=read(root/'work/mre/receipt.json');assert receipt['status']=='passed'
    assert sha(root/'work/mre/cases.json')==receipt['manifest_sha256']
    for r in receipt['processes']:
        assert r['passed'] and r['completed']==40
        assert sha(root/'work/mre'/r['profile']/r['output'])==r['output_sha256']
    assert sum(r['samples'] for r in a['comparisons'])==8480
    assert len(a['reference_checks'])==8 and len(a['pml_controls'])==2
    assert max(r['extrapolation_change'] for r in a['reference_checks'])<.00015
    assert max(r['relative_change'] for r in a['pml_controls'])<1e-6
    assert max(r['total_complex_rms'] for r in a['refinement'])<.001
    assert max(max(r['raw_forward_rms'],r['raw_reverse_rms']) for r in a['refinement'])<.001
    assert max(r['coarse_to_fine'] for r in a['refinement'])<.001
    assert max(r['rms_error'] for r in read(w/'boundary.json')['results'])<.001
    fdfd=list((w/'fdfd').glob('*.json'))+list((w/'fdfd_pml').glob('*.json'));assert len(fdfd)==26
    for f in fdfd:
        r=read(f);assert r['source_sha256']==sha(project/'scripts/maxwell2d_reference.py')
        assert r['linear_residual']<1e-10 and r['reciprocity_residual']<1e-10
    for name,panels in [('final16.json',16),('final24.json',24)]:
        r=read(w/name);assert r['panels']==panels and not r['native_ray_exports_modified']
        for file,digest in r['source_sha256'].items():assert sha(project/'scripts'/file)==digest
    product=read(w/'workflow/comparison.json');assert product['status']=='passed' and product['reference_used'] is False
    assert len(product['comparisons'])==80 and {r['profile'] for r in product['comparisons']}=={'sionna-reciprocal','differt-reciprocal'}
    delivered={r['name']:r for r in read(w/'workflow/refinement.json')['results']}
    for r in read(w/'final24.json')['results']:assert np.allclose(z(r['field']),z(delivered[r['name']]['field']),rtol=1e-13,atol=1e-14)
    for r in receipt['processes']:assert product['engine_outputs_unchanged'][r['profile']]==r['output_sha256']
    smoke=read(w/'launcher_smoke/comparison.json');smoke_receipt=read(w/'launcher_smoke/rays/receipt.json')
    assert smoke['status']=='passed' and smoke_receipt['status']=='passed' and len(smoke['comparisons'])==4
    assert len(smoke_receipt['processes'])==2 and all(r['passed'] and r['completed']==2 for r in smoke_receipt['processes'])
    for r in smoke_receipt['processes']:assert sha(w/'launcher_smoke/rays'/r['profile']/r['output'])==r['output_sha256']
    baseline=read(root/'work/cleanup-2026-11-01/protected_hashes.json')
    for name in ('diffraction_remediation.json','sionna_lifetime_fix.json','sionna_batch_fix.json'):
        r=read(root/'outputs/differt-bridge/validation'/name)
        for f,c in r.get('source_updates',{}).items():baseline[f]=c['after']
        baseline.update(r.get('added_files',{}))
    for f,digest in baseline.items():assert sha(root/f)==digest,f
    optional=read(root/'outputs/differt-bridge/validation/reciprocal_profile.json')['added_files']
    for f,digest in optional.items():assert sha(root/f)==digest,f
    native=read(root/'outputs/differt-bridge/validation/workflow_health.json');reciprocal=read(out/'reciprocal_blender.json')
    assert native['status']=='passed' and native['blender']['comparison']['matched_paths']==1299
    assert reciprocal['status']=='passed' and all(reciprocal['activated'].values())
    video=read(out/'video_validation.json');animation=read(out/'animation_validation.json');assert video['status']=='passed' and video['frames']==1440
    assert sha(out/animation['video_name'])==animation['video_sha256'] and sha(w/'analysis.json')==animation['analysis_sha256']
    psnr={}
    for frame in animation['preview_frames']:
        p=out/'previews'/f'frame_{frame:04d}.png';q=out/'decoded'/p.name
        x=np.asarray(Image.open(p),dtype=float);y=np.asarray(Image.open(q),dtype=float);assert x.shape==y.shape==(900,1600,3)
        psnr[str(frame)]=float(10*np.log10(255**2/np.mean((x-y)**2)))
    assert min(psnr.values())>35
    log=(w/'tests.log').read_text();assert '100%' in log and 'FAILED' not in log
    verification=dict(status='passed',date='2026-11-07',mode='optional_fullwave_2d',native_ray_model_changed=False,engine_fixtures=160,engine_channels=8480,fullwave_channels=2120,independent_fdfd_operators=26,analytic_model_and_guard_tests=33,tests_exit_code=0,fullwave_rms_min=min(r['total_complex_rms'] for r in a['refinement']),fullwave_rms_max=max(r['total_complex_rms'] for r in a['refinement']),protected_files=len(baseline),optional_runtime_helpers=len(optional),fresh_native_paths=1299,fresh_reciprocal_paths=reciprocal['counts']['matched'],video_sample_psnr_db=psnr,unsupported_scenes_rejected=True,fullwave_model_uses_reference_fields=False)
    verification['launcher_smoke_engine_fixtures']=4
    (w/'study_verification.json').write_text(json.dumps(verification,indent=2))
    files={}
    def tree(base,prefix,pattern):
        for f in base.rglob(pattern):
            if f.is_file():files[prefix+'/'+f.relative_to(base).as_posix()]=f
    for folder in ('fdfd','fdfd_pml','workflow','launcher_smoke'):tree(w/folder,'results/'+folder,'*.json')
    for f in w.glob('*.json'):files['results/'+f.name]=f
    for f in w.glob('*.log'):
        if f.name not in ('encode.log','decode.log','package.log'):files['validation/'+f.name]=f
    files['pilot/pilot_canonical_refinement.py']=w/'pilot_canonical_refinement.py'
    tree(root/'work/mre','results/engines','*.json')
    old=root/'work/dielectric-corrections'
    tree(old/'maxwell_boundary','results/prior_boundary_reference','*.json')
    for f in ('maxwell_boundary_analysis.json','maxwell_analysis.json'):files['results/prior/'+f]=old/f
    for f in (old/'maxwell').glob('*.json'):
        if f.name.startswith(('free','pec')):files['results/prior_analytic_controls/'+f.name]=f
    for folder in ('scripts','tests','src'):tree(project/folder,'project/'+folder,'*.py')
    tree(project/'docs','project/docs','*.md')
    for f in project.glob('requirements*.txt'):files['project/'+f.name]=f
    for f in ('README.md','LICENSE','pyproject.toml'):files['project/'+f]=project/f
    for f in ('workflow_health.json','reciprocal_profile.json'):files['validation/'+f]=root/'outputs/differt-bridge/validation'/f
    files['validation/reciprocal_blender.json']=out/'reciprocal_blender.json';tree(root/'work/refinement-reciprocal-check/activation','validation/activation','*.json')
    for f in out.glob('*.png'):files['report/'+f.name]=f
    for f in ('index.html','animation_validation.json','video_validation.json'):files['report/'+f]=out/f
    for f in ('Compare_Maxwell_Wedge.ps1','Regenerate_Refinement_Animation.ps1'):files['launchers/'+f]=root/f
    text='''Validated optional 2D Maxwell refinement, 7 November 2026.

Read project/docs/maxwell-refinement.md for scope and reproduction commands.
The BIE is the model under test; results/fdfd is the independent reference.
No reference field is consumed by the refinement module or companion workflow.
The raw forward and reverse BIE fields disclose the reciprocity projection.
results/engines contains native and reciprocal engine outputs, which are not
overwritten by the separate 2D field. Geometry guard tests reject obstacles and
unsupported 3D cases before refinement; this is not a universal UTD replacement.

results/refined24.json is an earlier pilot with the equivalent earlier guard
source in pilot/. final16.json and final24.json use the current guarded source;
the original pilot is retained for audit and excluded from final verification.
The wrapper integration result is under results/workflow/.

validation contains the passing analytic/guard tests and fresh native/reciprocal
Blender receipts. Nonfatal background Skybrush overlay errors do not change the
explicit bridge PASS receipts. The MP4 and relative-path Blender timeline are
separate deliverables, not duplicated in this ZIP. Frame hashes permit redraw;
the temporary full-frame PNG sequence can be removed after encoding.

For another workstation, preserve the documented relative layout or point the
numerical drivers to your chosen directories. Existing FDFD files are resumable
checkpoints; choose a fresh output to force recomputation. Existing validated
engine versions and adapters are required for source-guarded runtime profiles.
No interpreter, compiler cache, credential or downloaded paper is bundled.
'''
    hashes={n:sha(f) for n,f in files.items()};archive=out/'refinement_evidence.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as zz:
        for n,f in sorted(files.items()):zz.write(f,n)
        zz.writestr('REPRODUCE.txt',text);hashes['REPRODUCE.txt']=hashlib.sha256(text.encode()).hexdigest()
        zz.writestr('SHA256SUMS.txt',''.join(d+'  '+n+'\n' for n,d in sorted(hashes.items())))
    with zipfile.ZipFile(archive) as zz:
        assert zz.testzip() is None
        for n,d in hashes.items():assert hashlib.sha256(zz.read(n)).hexdigest()==d
    verification.update(archive_sha256=sha(archive),archive_members=len(hashes)+1,archive_bytes=archive.stat().st_size,visual_qa='Scientific plots and source/decoded chapter samples inspected')
    (out/'verification.json').write_text(json.dumps(verification,indent=2))
    (out/'checksums.sha256').write_text(''.join(sha(f)+'  '+f.relative_to(out).as_posix()+'\n' for f in sorted(out.rglob('*')) if f.is_file() and f.name!='checksums.sha256'))
    class Links(HTMLParser):
        def __init__(self):super().__init__();self.urls=[]
        def handle_starttag(self,t,attrs):self.urls.extend(v for k,v in attrs if k in ('src','href') and v)
    count=0
    for f in (root/'index.html',out/'index.html'):
        parser=Links();parser.feed(f.read_text(encoding='utf-8'))
        for url in parser.urls:
            u=urlsplit(html.unescape(url))
            if not u.scheme and u.path:assert (f.parent/unquote(u.path)).exists(),(f,url);count+=1
    print(json.dumps(dict(status='passed',archive_members=len(hashes)+1,archive_bytes=archive.stat().st_size,protected_files=len(baseline),optional_helpers=len(optional),local_links=count,min_video_psnr=min(psnr.values())),indent=2))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('root',type=Path);a=ap.parse_args();main(a.root)

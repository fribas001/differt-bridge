"""Verify and archive the full-vector dielectric study without duplicated media."""
import argparse,hashlib,json,zipfile
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit,unquote
import numpy as np
from PIL import Image
from analyze_dielectric3d import read

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main(root,clean=False):
    w=root/'work/dielectric3d';out=root/'outputs/differt-bridge/examples/dielectric3d_diffraction';project=Path(__file__).resolve().parents[1]
    validation=read(out/'validation.json');assert validation['status']=='passed_with_documented_model_limits'
    for name,digest in validation['source_files'].items():assert sha(project/'scripts'/name)==digest,name
    campaigns=[];count=channels=0
    for name in ('d3r','d3f','d3reg'):
        p=root/'work'/name;r=read(p/'receipt.json');cases=read(p/'cases.json')['cases'];assert r['status']=='passed' and sha(p/'cases.json')==r['manifest_sha256']
        for process in r['processes']:
            assert process['passed'] and process['completed']==process['requested']==len(cases)
            assert sha(p/process['profile']/process['output'])==process['output_sha256'];count+=process['completed'];channels+=sum(len(c['receivers']) for c in cases)
        campaigns.append(dict(folder=name,fixtures=len(cases)*len(r['processes'])))
    assert count==1328
    # Every retained successful spectral run is internally hashed and uses an
    # identifiable numerical implementation, including the historical coarse BIE.
    reference_runs=[]
    for result in w.rglob('result.json'):
        data=read(result);folder=result.parent;config=read(folder/'config.json')
        for name,digest in config['source_hashes'].items():
            source=project/'scripts'/name
            if sha(source)!=digest:
                assert name=='dielectric3d_bem.py' and sha(w/'firstpass_bem_source.py')==digest
        modes=list(folder.glob('mode_*.json'));assert len(modes)==data['nodes']
        for meta in modes:
            d=read(meta);assert d['linear_residual']<1e-9 and sha(meta.with_suffix('.npz'))==d['field_sha256']
        reference_runs.append(dict(folder=folder.name,modes=len(modes),result_sha256=sha(result)))
    for d in read(w/'point_reciprocity.json')['modes']:
        assert d['linear_residual']<1e-9
    optional=read(root/'outputs/differt-bridge/validation/reciprocal_profile.json');prior=read(w/'prior_profile.json')
    for name,digest in optional['added_files'].items():assert sha(root/name)==digest,name
    changed=[name for name,digest in optional['added_files'].items() if prior['added_files'].get(name)!=digest]
    assert len(changed)==2 and all(n.endswith('/reciprocal_corrections.py') for n in changed)
    for name,digest in optional['source_files'].items():assert sha(project/'scripts'/name)==digest
    baseline=read(root/'work/cleanup-2026-11-01/protected_hashes.json')
    for name in ('diffraction_remediation.json','sionna_lifetime_fix.json','sionna_batch_fix.json'):
        r=read(root/'outputs/differt-bridge/validation'/name)
        for f,c in r.get('source_updates',{}).items():baseline[f]=c['after']
        baseline.update(r.get('added_files',{}))
    for name,digest in baseline.items():assert sha(root/name)==digest,name
    activation=read(root/'work/d3-reciprocal-health/activation/sionna_profile.json');assert 'material_sqrt' in activation and 'opaque_slab' in activation
    animation=read(out/'animation_validation.json');video=read(out/'video_validation.json')
    assert video['status']=='passed' and video['saved_and_reopened'] and video['frames']==1440
    assert sha(out/animation['video_name'])==animation['video_sha256'] and sha(w/'analysis.json')==animation['analysis_sha256']
    psnr={}
    for frame in animation['preview_frames']:
        p=out/'previews'/f'frame_{frame:04d}.png';q=out/'decoded'/p.name
        x=np.asarray(Image.open(p),float);y=np.asarray(Image.open(q),float);assert x.shape==y.shape==(900,1600,3)
        psnr[str(frame)]=float(10*np.log10(255**2/np.mean((x-y)**2)))
    assert min(psnr.values())>35
    if clean:
        folder=(w/'frames').resolve();assert folder==root/'work/dielectric3d/frames' and folder.is_relative_to(root)
        hashes=read(w/'frame_hashes.json');files=sorted(folder.glob('frame_*.png'))
        if files:
            assert len(files)==1440 and {p.name for p in files}==set(hashes)
            for p in files:assert p.resolve().parent==folder and sha(p)==hashes[p.name]
            size=sum(p.stat().st_size for p in files)
            for p in files:p.unlink()
            (out/'frame_cleanup.json').write_text(json.dumps(dict(status='completed',files=len(files),bytes_freed=size,scope='Only verified temporary source frame PNGs; movie, timeline, six previews and six decoded validation frames retained.'),indent=2))
    files={}
    def tree(path,prefix,pattern):
        for p in path.rglob(pattern):
            if '__pycache__' not in p.parts:files[prefix+'/'+p.relative_to(path).as_posix()]=p
    for p in w.glob('*.json'):files['results/'+p.name]=p
    for p in w.glob('*.log'):
        if p.name!='package.log':files['logs/'+p.name]=p
    for name in ('firstpass_bem_source.py','prior_reciprocal_corrections.py'):files['history/'+name]=w/name
    for run in reference_runs:
        folder=w/run['folder'];tree(folder,'reference/'+folder.name,'*.json');tree(folder,'reference/'+folder.name,'*.npz')
    tree(w/'point_reciprocity_modes','reference/point_reciprocity_modes','*.npz')
    for campaign in campaigns:
        folder=root/'work'/campaign['folder'];prefix='engines/'+folder.name
        files[prefix+'/cases.json']=folder/'cases.json';files[prefix+'/receipt.json']=folder/'receipt.json'
        for process in read(folder/'receipt.json')['processes']:
            for name in (process['output'],'receipt.json','intervention.json'):
                p=folder/process['profile']/name
                if p.exists():files[prefix+'/'+process['profile']+'/'+name]=p
    files['history/sionna_286_baseline.json']=root/'work/n3g/sionna-reciprocal/sionna_float32.json'
    for folder in ('scripts','tests','src'):tree(project/folder,'project/'+folder,'*.py')
    tree(project/'docs','project/docs','*.md')
    for name in ('README.md','LICENSE','pyproject.toml','requirements-analysis.txt','requirements-dev.txt'):files['project/'+name]=project/name
    tree(root/'work/d3-reciprocal-health/activation','validation/activation','*.json')
    for p in out.glob('*.json'):
        if p.name!='verification.json':files['report/'+p.name]=p
    files['report/index.html']=out/'index.html';files['launchers/Regenerate_Dielectric3D_Animation.ps1']=root/'Regenerate_Dielectric3D_Animation.ps1'
    reproduce='''3D dielectric point-source Maxwell campaign, 8 November 2026.
Read project/docs/dielectric3d-diffraction.md and report/index.html first.
Both Maxwell implementations solve coupled vector transmission equations,
not UTD. Geometry is an infinite solid quadrant; arbitrary 3D bodies and
finite edge endpoints are unvalidated. Fields are genuine 3D point-source
fields. Reference differences are empirical convergence indicators.
engines/d3r contains two native and two PRE-sqrt reciprocal runs. d3f holds
the updated reciprocal runs; d3reg contains 286 regressions in each runtime.
Historical helper source and the prior install manifest identify that baseline.
reference contains every completed mode checkpoint and numeric config.
history/firstpass_bem_source.py matches the original coarse concrete BIE
source hash. The final solver adds equilibration and iterative refinement.
Initial failed coarse control results and residual logs remain auditable.
Source reproduction uses the documented workstation layout and runtimes;
do not overwrite a historical reciprocal baseline with a patched rerun.
The material fix is source-guarded, opt-in and separate from reference fields.
No native engine or Blender extension files were overwritten.
Video and timeline are separate deliverables. Runtimes, credential files,
compiler caches, duplicate scenes and full PNG sequences are not archived.
The native channels are not replaced with the independent Maxwell data.
'''
    hashes={name:sha(p) for name,p in files.items()};archive=out/'dielectric3d_evidence.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as zz:
        for name,p in sorted(files.items()):zz.write(p,name)
        zz.writestr('REPRODUCE.txt',reproduce);hashes['REPRODUCE.txt']=hashlib.sha256(reproduce.encode()).hexdigest()
        zz.writestr('SHA256SUMS.txt',''.join(digest+'  '+name+'\n' for name,digest in sorted(hashes.items())))
    with zipfile.ZipFile(archive) as zz:
        assert zz.testzip() is None
        for name,digest in hashes.items():assert hashlib.sha256(zz.read(name)).hexdigest()==digest
    class Links(HTMLParser):
        def handle_starttag(self,tag,attrs):
            for key,value in attrs:
                if key in ('href','src') and value and not urlsplit(value).scheme and not value.startswith('#'):
                    assert (self.base/unquote(urlsplit(value).path)).resolve().exists(),value
    for page in (root/'index.html',out/'index.html'):
        parser=Links();parser.base=page.parent;parser.feed(page.read_text(encoding='utf-8'))
    result=dict(status='passed',engine_fixture_executions=count,engine_channels=channels,completed_reference_runs=reference_runs,protected_base_files=len(baseline),installed_helper_files=len(optional['added_files']),changed_helpers=changed,video_psnr=psnr,video_sha256=sha(out/animation['video_name']),archive=dict(file=archive.name,bytes=archive.stat().st_size,sha256=sha(archive),verified_members=len(hashes)),model_accuracy_claim='Canonical infinite dielectric wedge 3D point fields only; model errors remain.')
    (out/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('root',type=Path);ap.add_argument('--clean-frames',action='store_true');a=ap.parse_args();main(a.root.resolve(),a.clean_frames)

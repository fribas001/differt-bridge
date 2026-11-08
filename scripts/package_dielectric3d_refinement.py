"""Verify numerical provenance, both workflows, animation and compact evidence."""
import argparse,hashlib,json,zipfile,xml.etree.ElementTree as ET
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit,unquote
import numpy as np
from PIL import Image
from analyze_dielectric3d import read

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main(root,clean=False):
    work=root/'work/d3shadow';out=root/'outputs/differt-bridge/examples/dielectric3d_refinement';project=Path(__file__).resolve().parents[1]
    analysis=read(work/'analysis.json');assert analysis['status']=='passed';assert read(work/'reciprocity_validation.json')['status']=='passed';assert read(work/'boundary_validation.json')['status']=='passed'
    plan=read(work/'study_plan.json');assert plan['production_panels']==32
    for name,digest in plan['source_sha256'].items():assert sha(project/'scripts'/name)==digest,name
    for name,digest in plan['manifest_sha256'].items():assert sha(work/name)==digest,name
    suite=next(ET.parse(work/'tests.xml').getroot().iter('testsuite'));assert suite.get('failures')==suite.get('errors')=='0';tests=int(suite.get('tests'))
    products=[]
    for name in ('concrete','lower','holdout_a','holdout_b','reciprocity'):
        path=work/(name+'_standard_product.json');data=read(path);assert data['status']=='completed' and data['panels']==32 and data['order']==8 and not data['reference_used'] and not data['native_exports_modified']
        for file,digest in data['source_hashes'].items():assert sha(project/'scripts'/file)==digest
        folder=work/(path.stem+'_modes')
        for group in folder.glob('group_*'):
            cfg=read(group/'config.json');assert cfg['panels']==32
            modes=list(group.glob('mode_*.json'));assert len(modes)==64
            for mode in modes:
                m=read(mode);assert m['linear_residual']<1e-9 and sha(mode.with_suffix('.npz'))==m['field_sha256']
        products.append(dict(name=name,cases=len(data['results']),sha256=sha(path)))
    reference=[]
    reference_sources={sha(project/'scripts/dielectric3d_fem.py'),sha(work/'prior_dielectric3d_fem.py'),sha(work/'pre_release_fem.py')}
    for folder in ['concrete_fem64','lower_fem48','holdout_a_fem32','holdout_a_fem48','holdout_b_fem32','holdout_b_fem48']:
        p=work/folder;result=read(p/'result.json');assert result['status']=='completed' and result['method']=='fem' and result['nodes']==64
        cfg=read(p/'config.json');assert cfg['source_hashes']['dielectric3d_fem.py'] in reference_sources
        assert cfg['source_hashes']['dielectric3d_synthesis.py']==sha(project/'scripts/dielectric3d_synthesis.py')
        modes=list(p.glob('mode_*.json'));assert len(modes)==64
        for mode in modes:
            m=read(mode);assert m['linear_residual']<1e-9 and sha(mode.with_suffix('.npz'))==m['field_sha256']
        reference.append(dict(folder=folder,sha256=sha(p/'result.json')))
    # Preserve the 48-panel control's original frozen wrapper, rather than
    # claiming its old source hash belongs to the new default wrapper.
    fine=read(work/'concrete_product.json');assert fine['panels']==48 and fine['source_hashes']['dielectric3d_refinement.py']==sha(work/'precision48_refinement_source.py')
    assert read(work/'resolution_validation.json')['status']=='completed'
    assert read(work/'fem_memory_fix.json')['fields_bit_identical']
    assert all(c['fields_bit_identical'] for c in read(work/'fem_workspace_memory_fix.json')['checks'])
    physics=read(work/'workflow/comparison.json');assert physics['status']=='passed' and physics['reference_used'] is False and physics['shared_solver'] is True
    workflow=read(work/'workflow/refinement.json');assert workflow['panels']==32 and workflow['source_hashes']['dielectric3d_refinement.py']==sha(project/'scripts/dielectric3d_refinement.py')
    campaigns=[];fixtures=0
    for p in (root/'work/d3sh',work/'workflow/rays'):
        receipt=read(p/'receipt.json');assert receipt['status']=='passed' and receipt['manifest_sha256']==sha(p/'cases.json')
        n=len(read(p/'cases.json')['cases'])
        for r in receipt['processes']:
            assert r['passed'] and r['requested']==r['completed']==n and sha(p/r['profile']/r['output'])==r['output_sha256'];fixtures+=n
        campaigns.append(dict(folder=str(p.relative_to(root)),cases=n,profiles=len(receipt['processes'])))
    base=read(root/'work/cleanup-2026-11-01/protected_hashes.json')
    for name in ('diffraction_remediation.json','sionna_lifetime_fix.json','sionna_batch_fix.json'):
        r=read(root/'outputs/differt-bridge/validation'/name)
        for f,c in r.get('source_updates',{}).items():base[f]=c['after']
        base.update(r.get('added_files',{}))
    for name,digest in base.items():assert sha(root/name)==digest,name
    optional=read(root/'outputs/differt-bridge/validation/reciprocal_profile.json');prior=read(root/'outputs/differt-bridge/examples/dielectric3d_diffraction/installed_profile.json')
    assert optional==prior
    for name,digest in optional['added_files'].items():assert sha(root/name)==digest,name
    native=read(out/'native_workflow_health.json');corrected=read(out/'reciprocal_blender.json')
    assert native['status']==corrected['status']=='passed' and native['blender']['preferences_preserved'] and corrected['preferences_preserved']
    animation=read(out/'animation_validation.json');video=read(out/'video_validation.json');assert video['status']=='passed' and video['frames']==1440 and video['saved_and_reopened']
    assert sha(out/animation['video_name'])==animation['video_sha256'] and sha(work/'analysis.json')==animation['analysis_sha256']
    psnr={}
    for frame in animation['preview_frames']:
        name=f'frame_{frame:04d}.png';a=np.asarray(Image.open(out/'previews'/name),float);b=np.asarray(Image.open(out/'decoded'/name),float);assert a.shape==b.shape==(900,1600,3)
        psnr[str(frame)]=float(10*np.log10(255**2/np.mean((a-b)**2)))
    assert min(psnr.values())>35
    if clean:
        folder=(work/'frames').resolve();assert folder==root/'work/d3shadow/frames' and folder.is_relative_to(root)
        files=sorted(folder.glob('frame_*.png'));hashes=read(work/'frame_hashes.json')
        if files:
            assert len(files)==1440 and {p.name for p in files}==set(hashes)
            for p in files:assert p.resolve().parent==folder and sha(p)==hashes[p.name]
            size=sum(p.stat().st_size for p in files)
            for p in files:p.unlink()
            (out/'frame_cleanup.json').write_text(json.dumps(dict(status='completed',files=len(files),bytes_freed=size,scope='Only hash-verified temporary PNG frames; media and six source/decoded previews preserved.'),indent=2))
        for frame in (121,361,601):
            p=work/f'layout_{frame}.png'
            if p.exists():
                assert p.resolve().parent==work and sha(p)==sha(out/'previews'/f'frame_{frame:04d}.png')
                p.unlink()
    files={}
    def tree(path,prefix,pattern):
        for p in path.rglob(pattern):
            if '__pycache__' not in p.parts:files[prefix+'/'+p.relative_to(path).as_posix()]=p
    for p in work.glob('*.json'):files['results/'+p.name]=p
    for p in work.glob('*.py'):files['history/'+p.name]=p
    for p in work.glob('*.log'):
        if p.name!='package.log':files['logs/'+p.name]=p
    files['validation/tests.xml']=work/'tests.xml'
    for r in products:
        folder=work/(r['name']+'_standard_product_modes');tree(folder,'product/'+folder.name,'*.json');tree(folder,'product/'+folder.name,'*.npz')
    tree(work/'concrete_product_modes','control/concrete48','*.json');tree(work/'concrete_product_modes','control/concrete48','*.npz')
    for r in reference:
        folder=work/r['folder'];tree(folder,'reference/'+folder.name,'*.json');tree(folder,'reference/'+folder.name,'*.npz')
    for name in ('concrete_fem48','lower_fem32'):
        for file in ('config.json','result.json'):files['reference/prior/'+name+'/'+file]=root/'work/dielectric3d'/name/file
    for p,prefix in [(root/'work/d3f','engines/prior_primary'),(root/'work/d3sh','engines/holdout'),(work/'workflow/rays','engines/fresh_workflow')]:
        files[prefix+'/cases.json']=p/'cases.json';files[prefix+'/receipt.json']=p/'receipt.json'
        for process in read(p/'receipt.json')['processes']:
            for name in (process['output'],'receipt.json','intervention.json'):
                path=p/process['profile']/name
                if path.exists():files[prefix+'/'+process['profile']+'/'+name]=path
    for name in ('comparison.json','refinement.json'):files['workflow/'+name]=work/'workflow'/name
    for folder in ('scripts','tests','src'):tree(project/folder,'project/'+folder,'*.py')
    tree(project/'docs','project/docs','*.md')
    for name in ('README.md','LICENSE','pyproject.toml','requirements-analysis.txt','requirements-dev.txt'):files['project/'+name]=project/name
    for p in out.glob('*.json'):
        if p.name!='verification.json':files['report/'+p.name]=p
    files['report/index.html']=out/'index.html'
    for name in ('Compare_Dielectric3D_Wedge.ps1','Regenerate_Dielectric3D_Refined_Animation.ps1'):files['launchers/'+name]=root/name
    reproduce='''Optional coupled 3D dielectric full-wave companion.
Read project/docs/dielectric3d-refinement.md and report/index.html for scope.
Primary native fields are retained from the preceding dielectric 3D study.
Fresh holdout and workflow batches use both installed reciprocal runtimes.
The separate optional BIE fields never consume the FEM reference values.
Standard mode uses 32 panels and 64 spectral nodes; the 48-panel concrete
control and its original wrapper source are retained. The initial 48-panel
plan was amended for resource cost before holdout reference results existed;
unchanged acceptance gates and both plans are included.
No native engine, optional-profile helper or Blender extension was modified.
FEM memory-only changes and cache migrations preserve numerical fields.
Reference mesh/refinement differences are empirical, not certified bounds.
Every completed numerical mode has its input/source config and content hash.
Run with the existing runtime interpreters and OPENBLAS_NUM_THREADS=1.
Videos, timelines, runtimes, caches and full PNG sequences are not duplicated.
Use the documented workspace layout; the launchers and report link to it.
'''
    hashes={name:sha(p) for name,p in files.items()};archive=out/'dielectric3d_refinement_evidence.zip'
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
    result=dict(status='passed',tests=tests,fresh_engine_fixture_executions=fixtures,campaigns=campaigns,products=products,reference_runs=reference,protected_base_files=len(base),optional_profile_files=len(optional['added_files']),optional_profile_changed=False,native_matched_paths=native['blender']['comparison']['matched_paths'],reciprocal_blender=corrected,video_psnr=psnr,video_sha256=animation['video_sha256'],archive=dict(file=archive.name,bytes=archive.stat().st_size,sha256=sha(archive),verified_members=len(hashes)),scope='Optional shared infinite dielectric-wedge field; native UTD remains unchanged.')
    (out/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    for page in (root/'index.html',out/'index.html'):
        parser=Links();parser.base=page.parent;parser.feed(page.read_text(encoding='utf-8'))
    print(json.dumps(result),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('root',type=Path);ap.add_argument('--clean-frames',action='store_true');a=ap.parse_args();main(a.root.resolve(),a.clean_frames)

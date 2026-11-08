"""Verify the promoted companion, native workflows, references and deliverables."""
import argparse,hashlib,json,zipfile,xml.etree.ElementTree as ET
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit,unquote
import numpy as np
from PIL import Image
from analyze_dielectric3d import read

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main(root,clean):
    w=root/'work/d3weak';out=root/'outputs/differt-bridge/examples/dielectric3d_weak';project=Path(__file__).resolve().parents[1]
    a=read(w/'analysis.json');assert a['status']=='passed' and all(g['passed'] for g in a['gates']);assert read(w/'domain_validation.json')['status']=='passed'
    assert read(w/'cli_validation.json')['status']=='passed'
    plan=read(w/'study_plan.json')
    for name,digest in plan['source_hashes'].items():assert sha(project/'scripts'/name)==digest,name
    assert sha(w/'new_holdout_cases.json')==plan['manifest_sha256']
    suite=next(ET.parse(w/'tests.xml').getroot().iter('testsuite'));assert suite.get('failures')==suite.get('errors')==suite.get('skipped')=='0';assert int(suite.get('tests'))==68
    files={};modes_verified=0
    def tree(path,prefix,patterns=('*.json','*.npz')):
        for pattern in patterns:
            for p in path.rglob(pattern):
                if p.is_file() and '__pycache__' not in p.parts:files[prefix+'/'+p.relative_to(path).as_posix()]=p
    def verify_modes(folder,count):
        nonlocal modes_verified
        modes=list(folder.glob('mode_*.json'));assert len(modes)==count,(folder,len(modes),count)
        for p in modes:
            m=read(p);assert m['linear_residual']<1e-9 and sha(p.with_suffix('.npz'))==m['field_sha256'];modes_verified+=1
    products=[]
    for material in ('concrete','lower','holdout_a','holdout_b','reciprocity','new_a','new_b'):
        p=w/f'{material}_converged.json';d=read(p);assert d['status']=='completed' and d['mode']=='optional_3d_dielectric_converged' and not d['reference_used'] and not d['native_exports_modified']
        for name,digest in d['source_hashes'].items():assert sha(project/'scripts'/name)==digest
        coarse=w/f'{material}_converged_modes/coarse16/group_00'
        fine=w/f'{material}_converged_modes/fine32/group_00' if material.startswith('new_') else root/f'work/d3shadow/{material}_standard_product_modes/group_00'
        for folder,resolution in ((coarse,16),(fine,32)):
            cfg=read(folder/'config.json');assert cfg['panels']==resolution and cfg['order']==8
            for name,digest in cfg['source_hashes'].items():assert sha(project/'scripts'/name)==digest
            verify_modes(folder,64);tree(folder,f'product/{material}/{resolution}')
        products.append(dict(material=material,cases=len(d['results']),sha256=sha(p)))
    references=[]
    for name,count in [('weak_fem64q8',64),('weak_fem48q12',96),('new_a_fem32',64),('new_a_fem48',64),('new_b_fem32',64),('new_b_fem48',64)]:
        folder=w/name;r=read(folder/'result.json');assert r['status']=='completed' and r['nodes']==count
        for source,digest in r['source_hashes'].items():assert sha(project/'scripts'/source)==digest
        verify_modes(folder,count);tree(folder,'reference/'+name);references.append(dict(name=name,sha256=sha(folder/'result.json')))
    for name in ('bie16','bie24','bie48','bie64','bie32quad24','bie32core5','bie32tail5','fem64','fem48domain'):
        folder=w/name;assert read(folder/'receipt.json')['status']=='completed';verify_modes(folder,4);tree(folder,'controls/'+name)
    # Preserve the previous comparison and its evidence instead of rewriting it.
    previous=root/'outputs/differt-bridge/examples/dielectric3d_refinement';old=read(previous/'verification.json')
    assert sha(previous/old['archive']['file'])==old['archive']['sha256'];assert sha(previous/'Sionna_vs_DiffeRT_Dielectric3D_Refined.mp4')==old['video_sha256']
    prior_evidence=dict(archive=old['archive'],video_sha256=old['video_sha256'])
    for material,res in [('concrete',64),('lower',48),('holdout_a',48),('holdout_b',48)]:
        folder=root/f'work/d3shadow/{material}_fem{res}'
        for name in ('result.json','config.json'):files[f'reference/prior/{material}/{name}']=folder/name
    # Original q-level reference fields used by the diagnosis.
    tree(root/'work/d3shadow/holdout_b_fem48','reference/prior/holdout_b_modes')
    for name in ('analysis.json','primary_cases.json','holdout_cases.json','reciprocity_cases.json'):
        files['prior/'+name]=root/'work/d3shadow'/name
    phy=read(w/'workflow/comparison.json');assert phy['status']=='passed' and phy['accuracy']=='converged' and not phy['reference_used']
    wf=read(w/'workflow/refinement.json');assert wf['mode']=='optional_3d_dielectric_converged' and wf['results']==read(w/'concrete_converged.json')['results']
    promotion=read(w/'promotion.json');assert promotion['status']=='applied_after_validation' and promotion['analysis_sha256']==sha(w/'analysis.json')
    for name,change in promotion['source_updates'].items():assert sha(root/name)==change['after']
    campaigns=[];fixtures=0
    for p in (root/'work/d3wr',w/'workflow/rays'):
        receipt=read(p/'receipt.json');assert receipt['status']=='passed' and receipt['manifest_sha256']==sha(p/'cases.json');n=len(read(p/'cases.json')['cases'])
        for process in receipt['processes']:
            assert process['passed'] and process['completed']==process['requested']==n and sha(p/process['profile']/process['output'])==process['output_sha256'];fixtures+=n
        campaigns.append(dict(folder=str(p.relative_to(root)),cases=n,profiles=len(receipt['processes'])))
    for p,prefix in [(root/'work/d3wr','engines/fresh_holdout'),(w/'workflow/rays','engines/fresh_workflow'),(root/'work/d3sh','engines/prior_holdout'),(root/'work/d3f','engines/prior_primary')]:
        for name in ('receipt.json','cases.json'):files[prefix+'/'+name]=p/name
        for process in read(p/'receipt.json')['processes']:
            for name in (process['output'],'receipt.json','intervention.json'):
                f=p/process['profile']/name
                if f.exists():files[prefix+'/'+process['profile']+'/'+name]=f
    base=read(root/'work/cleanup-2026-11-01/protected_hashes.json')
    for name in ('diffraction_remediation.json','sionna_lifetime_fix.json','sionna_batch_fix.json'):
        r=read(root/'outputs/differt-bridge/validation'/name)
        for f,c in r.get('source_updates',{}).items():base[f]=c['after']
        base.update(r.get('added_files',{}))
    for name,digest in base.items():assert sha(root/name)==digest,name
    optional=read(root/'outputs/differt-bridge/validation/reciprocal_profile.json');assert optional==read(root/'outputs/differt-bridge/examples/dielectric3d_diffraction/installed_profile.json')
    for name,digest in optional['added_files'].items():assert sha(root/name)==digest,name
    native=read(out/'native_workflow_health.json');reciprocal=read(out/'reciprocal_blender.json');assert native['status']==reciprocal['status']=='passed' and native['blender']['preferences_preserved'] and reciprocal['preferences_preserved']
    animation=read(out/'animation_validation.json');video=read(out/'video_validation.json');assert video['status']=='passed' and video['frames']==1440 and video['saved_and_reopened'];assert sha(out/animation['video_name'])==animation['video_sha256'];assert sha(w/'analysis.json')==animation['analysis_sha256']
    psnr={}
    for frame in animation['preview_frames']:
        name=f'frame_{frame:04d}.png';x=np.asarray(Image.open(out/'previews'/name),float);y=np.asarray(Image.open(out/'decoded'/name),float);assert x.shape==y.shape==(900,1600,3);psnr[str(frame)]=float(10*np.log10(255**2/np.mean((x-y)**2)))
    assert min(psnr.values())>35
    if clean:
        folder=(w/'frames').resolve();assert folder==root/'work/d3weak/frames' and folder.is_relative_to(root);frames=list(folder.glob('frame_*.png'));hashes=read(w/'frame_hashes.json')
        if frames:
            assert len(frames)==1440 and {p.name for p in frames}==set(hashes)
            for p in frames:assert p.resolve().parent==folder and sha(p)==hashes[p.name]
            size=sum(p.stat().st_size for p in frames)
            for p in frames:p.unlink()
            (out/'frame_cleanup.json').write_text(json.dumps(dict(status='completed',files=1440,bytes_freed=size,scope='Only hash-verified temporary PNG frames; source and decoded previews retained.'),indent=2))
        for frame in (121,361):
            p=w/f'layout_{frame}.png'
            if p.exists():
                assert p.resolve().parent==w and sha(p)==sha(out/'previews'/f'frame_{frame:04d}.png');p.unlink()
    for p in w.glob('*.json'):files['results/'+p.name]=p
    for p in w.glob('*.log'):
        if p.name!='package.log':files['logs/'+p.name]=p
    tree(w/'history','history',('*',));files['validation/tests.xml']=w/'tests.xml'
    for name in ('comparison.json','refinement.json'):files['workflow/'+name]=w/'workflow'/name
    for folder in ('scripts','tests','src'):tree(project/folder,'project/'+folder,('*.py',))
    tree(project/'docs','project/docs',('*.md',))
    for name in ('README.md','LICENSE','pyproject.toml','requirements-analysis.txt','requirements-dev.txt'):files['project/'+name]=project/name
    for name in ('Compare_Dielectric3D_Wedge.ps1','Regenerate_Dielectric3D_Weak_Animation.ps1'):files['launchers/'+name]=root/name
    for p in out.glob('*.json'):
        if p.name!='verification.json':files['report/'+p.name]=p
    files['report/index.html']=out/'index.html'
    hashes={name:sha(p) for name,p in files.items()};archive=out/'dielectric3d_weak_evidence.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as zz:
        for name,p in sorted(files.items()):zz.write(p,name)
        note='Read project/docs/dielectric3d-weak.md and report/index.html. Fixed, unfitted 2*BIE32-BIE16 shared companion; native UTD unchanged. Prior study archive and video hashes: '+json.dumps(prior_evidence)+'\nNo runtime or full PNG-sequence duplication. Historical checkpoint inputs and source hashes remain authoritative.\n'
        zz.writestr('REPRODUCE.txt',note);hashes['REPRODUCE.txt']=hashlib.sha256(note.encode()).hexdigest();zz.writestr('SHA256SUMS.txt',''.join(d+'  '+n+'\n' for n,d in sorted(hashes.items())))
    with zipfile.ZipFile(archive) as zz:
        assert zz.testzip() is None
        for name,digest in hashes.items():assert hashlib.sha256(zz.read(name)).hexdigest()==digest
    result=dict(status='checking_links',tests=int(suite.get('tests')),fresh_engine_fixture_executions=fixtures,campaigns=campaigns,products=products,reference_runs=references,numerical_modes_verified=modes_verified,protected_base_files=len(base),optional_profile_files=len(optional['added_files']),optional_profile_changed=False,native_matched_paths=native['blender']['comparison']['matched_paths'],reciprocal_blender=reciprocal,video_psnr=psnr,video_sha256=animation['video_sha256'],prior_artifacts_unchanged=prior_evidence,archive=dict(file=archive.name,bytes=archive.stat().st_size,sha256=sha(archive),verified_members=len(hashes)),scope='Optional shared spatially extrapolated infinite dielectric-wedge field; no native UTD changes.')
    (out/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    class Links(HTMLParser):
        def handle_starttag(self,tag,attrs):
            for key,value in attrs:
                if key in ('href','src') and value and not urlsplit(value).scheme and not value.startswith('#'):assert (self.base/unquote(urlsplit(value).path)).resolve().exists(),value
    for page in (root/'index.html',out/'index.html'):
        parser=Links();parser.base=page.parent;parser.feed(page.read_text(encoding='utf-8'))
    result['status']='passed';(out/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('root',type=Path);ap.add_argument('--clean-frames',action='store_true');a=ap.parse_args();main(a.root.resolve(),a.clean_frames)

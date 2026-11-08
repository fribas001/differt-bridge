"""Audit new Maxwell refinements, preserved products and decoded animation."""
import argparse,hashlib,json,zipfile,xml.etree.ElementTree as ET
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit,unquote
import numpy as np
from PIL import Image
from investigate_dielectric3d_polarization import read,save,sha
from dielectric3d_synthesis import quadrature


def main(root,clean):
    w=root/'work/d3res';out=root/'outputs/differt-bridge/examples/dielectric3d_residual';project=Path(__file__).resolve().parents[1]
    a=read(w/'analysis.json');assert a['status']=='passed' and all(v['passed'] for v in a['checks']) and not a['production_changed']
    plan=read(w/'plan.json');selection=read(w/'resource_selection.json');assert selection['status']=='passed'
    for name,digest in plan['sources'].items():assert sha(project/'scripts'/name)==digest,name
    for name,digest in {**plan['production'],**plan['prior_files']}.items():assert sha(root/name)==digest,name
    for name,digest in selection['sources'].items():assert sha(project/'scripts'/name)==digest,name
    environment=read(w/'execution_environment.json');assert sha(Path(environment['superlu_binary']))==environment['superlu_binary_sha256']
    test_notes=read(w/'test_execution_notes.json');assert sha(w/'tests.xml')==test_notes['final_tests']['sha256']
    for name in ('sampling_assessment','offgrid_validation'):assert read(w/(name+'.json'))['status']=='passed'
    assert not read(w/'sampling_assessment.json')['cubic_candidate_accepted']
    assert read(w/'sampling_assessment.json')['trial_sha256']==sha(w/'sampling_validation.json')
    offgrid=read(w/'offgrid_validation.json')
    for name,digest in offgrid['config']['sources'].items():assert sha(project/'scripts'/name)==digest
    tail_plan=read(w/'tail_execution_addendum.json')
    assert tail_plan['wrapper_sha256']==sha(project/'scripts/probe_dielectric3d_bounded_tail.py')
    height_plan=read(w/'height_synthesis_plan.json');height_check=read(w/'height_synthesis_validation.json')
    assert height_plan['source_sha256']==sha(project/'scripts/synthesize_dielectric3d_residual_heights.py')
    assert height_check['status']=='passed' and height_check['plan_sha256']==sha(w/'height_synthesis_plan.json')
    files={};verified=0;references=[]
    def tree(folder,prefix,patterns=('*.json','*.npz')):
        for pat in patterns:
            for p in folder.rglob(pat):
                if p.is_file() and '__pycache__' not in p.parts and p.name!='package.log' and not any(v.startswith('pytest-temp-') for v in p.parts):files[prefix+'/'+p.relative_to(folder).as_posix()]=p
    for n in (112,128):
        folder=w/f'fem{n}_bounded';cfg=read(folder/'config.json');result=read(folder/'result.json')
        assert result['status']=='completed' and cfg['policy']==selection['policy'] and cfg['mode_resolutions']==[n]*32+[64]*32
        for name,digest in cfg['sources'].items():assert sha(project/'scripts'/name)==digest,name
        tail=root/cfg['tail']['folder'];assert sha(tail/'config.json')==cfg['tail']['config_sha256']
        nodes,_=quadrature(cfg['order']);assert len(list(folder.glob('mode_*.npz')))==64
        for i,q in enumerate(nodes):
            p=folder/f'mode_{i:03d}.npz';m=read(p.with_suffix('.json'));assert sha(p)==m['sha256'] and m['linear_residual']<1e-9
            assert m['q']==[q.real,q.imag] and m['epsilon']==cfg['epsilon'] and m['ppw']==cfg['mode_resolutions'][i]
            with np.load(p) as z:
                field=z['field'];assert np.isfinite(field).all() and np.isfinite(z['cubic']).all()
                if i>=32:
                    source=root/m['source_mode'];assert sha(source)==m['source_sha256']
                    expected=np.load(source)['field'][cfg['tail']['receivers'],:,cfg['tail']['column'],None]
                    assert np.array_equal(field,expected) and np.array_equal(z['cubic'],expected)
                if 'source_validation' in m:
                    source=root/m['source_validation'];assert sha(source)==sha(p)
                    assert sha(source.parent/'config.json')==m['source_validation_config_sha256']
            verified+=1
        references.append(dict(name=folder.name,modes=64,sha256=sha(folder/'result.json'),maximum_linear_residual=result['maximum_linear_residual']))
        derived=read(w/f'fem{n}_heights.json');assert derived['status']=='completed' and derived['source_result_sha256']==sha(folder/'result.json')
        assert derived['source_config_sha256']==sha(folder/'config.json') and derived['plan_sha256']==sha(w/'height_synthesis_plan.json') and derived['original_height_reconstruction_error']<1e-12
    for foldername in ('bie64_full','fem128tail'):
        folder=w/foldername;cfg=read(folder/'config.json')
        if foldername=='bie64_full':
            result=read(folder/'result.json');assert result['status']=='completed' and result['nodes']==64
            assert read(folder/'execution.json')['source_sha256']==sha(project/'scripts/run_dielectric3d_residual_bie.py')
            for name,digest in cfg['source_hashes'].items():assert sha(project/'scripts'/name)==digest
            guard=read(folder/'guard.json');assert guard['status']=='passed' and sha(root/guard['manifest'])==guard['manifest_sha256']
        else:
            assert read(folder/'receipt.json')['status']=='completed' and cfg['linear_solver']==selection['policy']
            assert cfg['source_sha256']==sha(project/'scripts/dielectric3d_fem.py')
            assert cfg['indices']==tail_plan['indices'] and cfg['resolution']==tail_plan['resolution']
        for p in folder.glob('mode_*.npz'):
            m=read(p.with_suffix('.json'));assert sha(p)==m['field_sha256'] and m['linear_residual']<1e-9;assert np.isfinite(np.load(p)['field']).all();verified+=1
    for row in selection['controls']:
        folder=w/f"bounded{row['resolution']}";assert sha(folder/'validation.json')==row['validation_sha256']
        for r in read(folder/'validation.json')['rows']:
            p=folder/f"mode_{r['index']:03d}.npz";assert sha(p)==r['metadata']['sha256']
            assert r['metadata']['linear_residual']<1e-9 and (r['error'] is None or r['error']<1e-8);verified+=1
    for foldername in ('interface64','nested64','nested96'):
        v=read(w/foldername/'validation.json');assert v['status']=='passed'
        for r in v['rows']:
            p=w/foldername/f"mode_{r['index']:03d}.npz";assert sha(p)==r['metadata']['field_sha256'] and r['error']<1e-8;verified+=1
    base=read(root/'work/cleanup-2026-11-01/protected_hashes.json')
    for name in ('diffraction_remediation.json','sionna_lifetime_fix.json','sionna_batch_fix.json'):
        rr=read(root/'outputs/differt-bridge/validation'/name)
        for f,c in rr.get('source_updates',{}).items():base[f]=c['after']
        base.update(rr.get('added_files',{}))
    for name,digest in base.items():assert sha(root/name)==digest,name
    optional=read(root/'outputs/differt-bridge/validation/reciprocal_profile.json')
    assert optional==read(root/'outputs/differt-bridge/examples/dielectric3d_diffraction/installed_profile.json')
    for name,digest in optional['added_files'].items():assert sha(root/name)==digest,name
    suite=next(ET.parse(w/'tests.xml').getroot().iter('testsuite'));assert suite.get('errors')==suite.get('failures')==suite.get('skipped')=='0';assert int(suite.get('tests'))==68
    fixtures=0;campaigns=[]
    for folder in (w/'rays',w/'workflow/rays'):
        receipt=read(folder/'receipt.json');assert receipt['status']=='passed' and receipt['manifest_sha256']==sha(folder/'cases.json');n=len(read(folder/'cases.json')['cases'])
        for r in receipt['processes']:
            assert r['passed'] and r['requested']==r['completed']==n and sha(folder/r['profile']/r['output'])==r['output_sha256'];fixtures+=n
        campaigns.append(dict(path=str(folder.relative_to(root)),cases=n,engines=2))
    comparison=read(w/'workflow/comparison.json');assert comparison['status']=='passed' and comparison['accuracy']=='converged'
    assert read(w/'workflow/refinement.json')['results']==read(root/'work/d3weak/concrete_converged.json')['results']
    native=read(out/'native_workflow_health.json');reciprocal=read(out/'reciprocal_blender.json')
    assert native['status']==reciprocal['status']=='passed' and native['blender']['preferences_preserved'] and reciprocal['preferences_preserved']
    animation=read(out/'animation_validation.json');video=read(out/'video_validation.json')
    review=read(out/'visual_review.json');assert review['status']=='passed' and review['analysis_sha256']==sha(w/'analysis.json')
    assert review['renderer_sha256']==sha(project/'scripts/render_dielectric3d_residual_animation.py')
    for name,digest in review['preview_sha256'].items():assert sha(out/'previews'/name)==digest
    assert video['status']=='passed' and video['saved_and_reopened'] and video['frames']==1440
    assert animation['analysis_sha256']==sha(w/'analysis.json') and sha(out/animation['video_name'])==animation['video_sha256']
    psnr={}
    for frame in animation['preview_frames']:
        name=f'frame_{frame:04d}.png';x=np.asarray(Image.open(out/'previews'/name),float);y=np.asarray(Image.open(out/'decoded'/name),float)
        assert x.shape==y.shape==(900,1600,3);psnr[str(frame)]=float(10*np.log10(255**2/np.mean((x-y)**2)))
    assert min(psnr.values())>35
    media=[out/animation['video_name'],out/animation['timeline_name']]
    media += sorted((out/'previews').glob('frame_*.png'))+sorted((out/'decoded').glob('frame_*.png'))
    media_manifest=dict(scope='Media remain adjacent to the report and are not duplicated inside the evidence ZIP. Copy them beside an extracted report, or regenerate them using the workspace launcher.',files={p.relative_to(out).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in media})
    save(out/'media_manifest.json',media_manifest)
    if clean:
        folder=(w/'frames').resolve();assert folder==root/'work/d3res/frames' and folder.is_relative_to(root)
        frames=list(folder.glob('frame_*.png'));hashes=read(w/'frame_hashes.json')
        if frames:
            assert len(frames)==1440 and set(p.name for p in frames)==set(hashes)
            for p in frames:assert p.resolve().parent==folder and sha(p)==hashes[p.name]
            size=sum(p.stat().st_size for p in frames)
            for p in frames:p.unlink()
            save(out/'frame_cleanup.json',dict(status='completed',files=1440,bytes_freed=size,scope='Only hash-verified temporary frames; source and decoded previews retained.'))
    tree(w,'workspace/work/d3res',('*.json','*.npz','*.log','*.xml','*.ps1'))
    for name in ('analysis.json','diagnostics.json','study_plan.json','production_baseline.json','probe_analysis.json','linear_solver_validation.json'):
        files['workspace/work/d3pol/'+name]=root/'work/d3pol'/name
    for name in ('holdout_b_fem64q8','target_fem80q8_lowmem','target_fem96q8_lowmem','bie64','fem96tail'):
        tree(root/'work/d3pol'/name,'workspace/work/d3pol/'+name)
    for name in ('holdout_cases.json','holdout_b_cases.json'):files['workspace/work/d3shadow/'+name]=root/'work/d3shadow'/name
    for folder in ('scripts','tests','src'):tree(project/folder,'project/'+folder,('*.py',))
    tree(project/'docs','project/docs',('*.md',))
    for name in ('README.md','LICENSE','pyproject.toml','requirements-analysis.txt','requirements-dev.txt'):files['project/'+name]=project/name
    for name in ('Compare_Dielectric3D_Wedge.ps1','Refine_Dielectric3D_Residual.ps1','Regenerate_Dielectric3D_Residual_Animation.ps1'):files['launchers/'+name]=root/name
    for p in out.glob('*.json'):
        if p.name!='verification.json':files['report/'+p.name]=p
    files['report/index.html']=out/'index.html';hashes={name:sha(p) for name,p in files.items()};archive=out/'dielectric3d_residual_evidence.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as zz:
        for name,p in sorted(files.items()):zz.write(p,name)
        note='Read project/docs/dielectric3d-residual.md and report/index.html. Production unchanged. Mixed FEM128 low-q / FEM64 tail is explicit. Failed/partial and rejected experiments are retained and not accepted references. The original workspace and previous polarization evidence provide the preceding campaign. Restore workspace/ paths beneath that workspace; project/ is work/github-update/differt-bridge, launchers/ is the root. Media are not duplicated in the archive; report/media_manifest.json lists adjacent files to copy beside an extracted report. Previous artifact hashes are in results plan (workspace/work/d3res/plan.json).\n'
        zz.writestr('REPRODUCE.txt',note);hashes['REPRODUCE.txt']=hashlib.sha256(note.encode()).hexdigest();zz.writestr('SHA256SUMS.txt',''.join(d+'  '+n+'\n' for n,d in sorted(hashes.items())))
    with zipfile.ZipFile(archive) as zz:
        assert zz.testzip() is None
        for name,digest in hashes.items():assert hashlib.sha256(zz.read(name)).hexdigest()==digest
    receipt=dict(status='checking_links',production_changed=False,tests=int(suite.get('tests')),fresh_engine_fixture_executions=fixtures,campaigns=campaigns,reference_runs=references,numerical_modes_verified=verified,
        protected_base_files=len(base),optional_profile_files=len(optional['added_files']),native_matched_paths=native['blender']['comparison']['matched_paths'],reciprocal_blender=reciprocal,
        video_psnr=psnr,video_sha256=animation['video_sha256'],prior_files_unchanged=len(plan['prior_files']),prior_video_sha256=sha(root/'outputs/differt-bridge/examples/dielectric3d_polarization/Sionna_vs_DiffeRT_Polarization.mp4'),
        archive=dict(file=archive.name,bytes=archive.stat().st_size,sha256=sha(archive),verified_members=len(hashes)))
    save(out/'verification.json',receipt)
    class Links(HTMLParser):
        def handle_starttag(self,tag,attrs):
            for key,value in attrs:
                if key in ('href','src') and value and not urlsplit(value).scheme and not value.startswith('#'):assert (self.base/unquote(urlsplit(value).path)).resolve().exists(),value
    for page in (root/'index.html',out/'index.html'):
        parser=Links();parser.base=page.parent;parser.feed(page.read_text(encoding='utf-8'))
    receipt['status']='passed';save(out/'verification.json',receipt);print(json.dumps(receipt),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('root',type=Path);ap.add_argument('--clean-frames',action='store_true');a=ap.parse_args();main(a.root.resolve(),a.clean_frames)

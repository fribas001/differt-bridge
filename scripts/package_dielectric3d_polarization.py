"""Verify research provenance, unchanged products, live workflows and media."""
import argparse,hashlib,json,zipfile,xml.etree.ElementTree as ET
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit,unquote
import numpy as np
from PIL import Image
from investigate_dielectric3d_polarization import read,save,sha
from dielectric3d_synthesis import quadrature

def main(root,clean):
    w=root/'work/d3pol';out=root/'outputs/differt-bridge/examples/dielectric3d_polarization';project=Path(__file__).resolve().parents[1]
    a=read(w/'analysis.json');assert a['status']=='passed' and all(v['passed'] for v in a['checks']) and not a['production_changed']
    plan=read(w/'study_plan.json');baseline=read(w/'production_baseline.json')
    for name,digest in plan['source_hashes'].items():assert sha(project/'scripts'/name)==digest,name
    for name,digest in {**baseline,**plan['prior_artifacts']}.items():assert sha(root/name)==digest,name
    assert read(w/'reference_plan_addendum.json')['source_sha256']==sha(project/'scripts/run_dielectric3d_polarization_reference.py')
    assert read(w/'analytic_controls.json')['status']==read(w/'probe_analysis.json')['status']=='passed'
    linear=read(w/'linear_solver_validation.json');assert linear['status']=='passed'
    linear80=read(w/'linear80_crosscheck.json');assert linear80['status']=='passed'
    resource=read(w/'resource_validation.json')
    for source,digest in resource['source_hashes'].items():assert sha(project/'scripts'/source)==digest
    files={};verified=0;references=[]
    def tree(folder,prefix,patterns=('*.json','*.npz')):
        for pat in patterns:
            for p in folder.rglob(pat):
                if p.is_file() and '__pycache__' not in p.parts:files[prefix+'/'+p.relative_to(folder).as_posix()]=p
    for name,count in [('holdout_b_fem64q8',64),('holdout_a_fem64q8',64),('target_fem80q8_lowmem',64),('target_fem96q8_lowmem',64),('target_fem48q12',96)]:
        folder=w/name;cfg=read(folder/'config.json');result=read(folder/'result.json');assert result['status']=='completed' and result['nodes']==count
        for source,digest in cfg['source_hashes'].items():assert sha(project/'scripts'/source)==digest
        if cfg.get('mixed_resolution'):
            assert cfg['linear_solver']==linear['policy']
            tail=root/cfg['tail_provenance']['folder'];assert sha(tail/'config.json')==cfg['tail_provenance']['config_sha256']
            tailcfg=read(tail/'config.json');assert tailcfg['resolution']==64 and tailcfg['epsilon']==cfg['epsilon'] and tailcfg['order']==cfg['order']
        nodes,_=quadrature(cfg['order']);assert len(list(folder.glob('mode_*.npz')))==count
        for i,q in enumerate(nodes):
            p=folder/f'mode_{i:03d}.npz';m=read(p.with_suffix('.json'));assert sha(p)==m['field_sha256'] and m['linear_residual']<1e-9
            assert m['q']==[q.real,q.imag] and m['epsilon']==cfg['epsilon']
            assert m['ppw']==(cfg['mode_resolutions'][i] if cfg.get('mixed_resolution') else cfg['resolution'])
            f=np.load(p)['field'];assert np.isfinite(f).all()
            if 'source_mode' in m:
                source=root/m['source_mode'];assert sha(source)==m['source_mode_sha256'];sel=m['selection']
                assert np.array_equal(f,np.load(source)['field'][sel['receivers'],:,sel['column'],None])
            elif cfg.get('linear_solver'):assert m['linear_solver']==cfg['linear_solver']
            verified+=1
        references.append(dict(name=name,label=result.get('label',f'Uniform FEM{cfg["resolution"]}'),sha256=sha(folder/'result.json'),modes=count))
        tree(folder,'reference/'+name)
    diag=read(w/'diagnostics.json');fullcfg=read(w/'holdout_b_fem64q8/config.json');ri=[fullcfg['ports']['receivers'].index(v) for v in diag['receivers']]
    for p in (w/'linear64').glob('mode_*.npz'):
        meta=read(p.with_suffix('.json'));assert sha(p)==meta['field_sha256'] and meta['linear_residual']<1e-9 and meta['linear_solver']==linear['policy']
        aa=np.load(p)['field'];bb=np.load(w/'holdout_b_fem64q8'/p.name)['field'][ri,:,2,None]
        assert np.linalg.norm(aa-bb)/np.linalg.norm(bb)<1e-9;verified+=1
    for row in linear80['rows']:
        p=w/'target_fem80q8'/(row['mode']+'.npz');q=w/'target_fem80q8_lowmem'/p.name
        assert sha(p)==row['standard_sha256'] and sha(q)==row['new_sha256']
        aa=np.load(p)['field'];bb=np.load(q)['field'];assert np.linalg.norm(aa-bb)/np.linalg.norm(aa)<1e-9
    for name in ('compact64','target_fem80q8'):
        for p in (w/name).glob('mode_*.npz'):
            meta=read(p.with_suffix('.json'));assert sha(p)==meta['field_sha256'] and meta['linear_residual']<1e-9;verified+=1
    for name in ('linear64','compact64','target_fem80q8'):tree(w/name,'resource_controls/'+name)
    for name,count in [('bie64',4),('bie32quad24',4),('fem48domain',4),('fem48pml',4),('fem96tail',2)]:
        folder=w/name;cfg=read(folder/'config.json');assert read(folder/'receipt.json')['status']=='completed'
        if cfg.get('linear_solver'):assert cfg['linear_solver']==linear['policy']
        source='dielectric3d_bem.py' if cfg['method']=='bie' else 'dielectric3d_fem.py';assert cfg['source_sha256']==sha(project/'scripts'/source)
        assert len(list(folder.glob('mode_*.npz')))==count
        for p in folder.glob('mode_*.npz'):
            meta=read(p.with_suffix('.json'));assert sha(p)==meta['field_sha256'] and meta['linear_residual']<1e-9
            if cfg.get('linear_solver'):assert meta['linear_solver']==cfg['linear_solver']
            verified+=1
        tree(folder,'controls/'+name)
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
    for folder in (root/'work/d3pr',w/'workflow/rays'):
        receipt=read(folder/'receipt.json');assert receipt['status']=='passed' and receipt['manifest_sha256']==sha(folder/'cases.json');n=len(read(folder/'cases.json')['cases'])
        for r in receipt['processes']:
            assert r['passed'] and r['requested']==r['completed']==n and sha(folder/r['profile']/r['output'])==r['output_sha256'];fixtures+=n
        campaigns.append(dict(path=str(folder.relative_to(root)),cases=n,engines=2));tree(folder,'engines/'+folder.name)
    comparison=read(w/'workflow/comparison.json');assert comparison['status']=='passed' and comparison['accuracy']=='converged'
    assert read(w/'workflow/refinement.json')['results']==read(root/'work/d3weak/concrete_converged.json')['results']
    native=read(out/'native_workflow_health.json');reciprocal=read(out/'reciprocal_blender.json')
    assert native['status']==reciprocal['status']=='passed' and native['blender']['preferences_preserved'] and reciprocal['preferences_preserved']
    animation=read(out/'animation_validation.json');video=read(out/'video_validation.json')
    assert video['status']=='passed' and video['saved_and_reopened'] and video['frames']==1440
    assert animation['analysis_sha256']==sha(w/'analysis.json') and sha(out/animation['video_name'])==animation['video_sha256']
    psnr={}
    for frame in animation['preview_frames']:
        name=f'frame_{frame:04d}.png';x=np.asarray(Image.open(out/'previews'/name),float);y=np.asarray(Image.open(out/'decoded'/name),float)
        assert x.shape==y.shape==(900,1600,3);psnr[str(frame)]=float(10*np.log10(255**2/np.mean((x-y)**2)))
    assert min(psnr.values())>35
    if clean:
        folder=(w/'frames').resolve();assert folder==root/'work/d3pol/frames' and folder.is_relative_to(root)
        frames=list(folder.glob('frame_*.png'));hashes=read(w/'frame_hashes.json')
        if frames:
            assert len(frames)==1440 and set(p.name for p in frames)==set(hashes)
            for p in frames:assert p.resolve().parent==folder and sha(p)==hashes[p.name]
            size=sum(p.stat().st_size for p in frames)
            for p in frames:p.unlink()
            save(out/'frame_cleanup.json',dict(status='completed',files=1440,bytes_freed=size,scope='Only hash-verified temporary frames; source and decoded previews retained.'))
    for p in w.glob('*.json'):files['results/'+p.name]=p
    for p in w.glob('*.log'):
        if p.name!='package.log':files['logs/'+p.name]=p
    files['validation/tests.xml']=w/'tests.xml'
    files['validation/check_workflows.ps1']=w/'check_workflows.ps1'
    for name in ('comparison.json','refinement.json'):files['workflow/'+name]=w/'workflow'/name
    for material in ('holdout_a','holdout_b'):
        files[f'prior/{material}_product.json']=root/f'work/d3weak/{material}_converged.json'
        for resolution in (32,48):tree(root/f'work/d3shadow/{material}_fem{resolution}',f'prior/{material}_fem{resolution}')
    files['prior/analysis.json']=root/'work/d3weak/analysis.json'
    for folder in ('scripts','tests','src'):tree(project/folder,'project/'+folder,('*.py',))
    tree(project/'docs','project/docs',('*.md',))
    for name in ('README.md','LICENSE','pyproject.toml','requirements-analysis.txt','requirements-dev.txt'):files['project/'+name]=project/name
    for name in ('Compare_Dielectric3D_Wedge.ps1','Refine_Dielectric3D_Polarization_Reference.ps1','Regenerate_Dielectric3D_Polarization_Animation.ps1'):files['launchers/'+name]=root/name
    for p in out.glob('*.json'):
        if p.name!='verification.json':files['report/'+p.name]=p
    files['report/index.html']=out/'index.html';hashes={name:sha(p) for name,p in files.items()};archive=out/'dielectric3d_polarization_evidence.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as zz:
        for name,p in sorted(files.items()):zz.write(p,name)
        note='Read project/docs/dielectric3d-polarization.md and report/index.html. Production unchanged. Mixed FEM96 low-q / FEM64 tail is explicit; reference sensitivity is not a certified bound. Previous archive/video hashes: '+json.dumps(plan['prior_artifacts'])+'\n'
        zz.writestr('REPRODUCE.txt',note);hashes['REPRODUCE.txt']=hashlib.sha256(note.encode()).hexdigest();zz.writestr('SHA256SUMS.txt',''.join(d+'  '+n+'\n' for n,d in sorted(hashes.items())))
    with zipfile.ZipFile(archive) as zz:
        assert zz.testzip() is None
        for name,digest in hashes.items():assert hashlib.sha256(zz.read(name)).hexdigest()==digest
    receipt=dict(status='checking_links',production_changed=False,tests=int(suite.get('tests')),fresh_engine_fixture_executions=fixtures,campaigns=campaigns,reference_runs=references,numerical_modes_verified=verified,
       protected_base_files=len(base),optional_profile_files=len(optional['added_files']),native_matched_paths=native['blender']['comparison']['matched_paths'],
       reciprocal_blender=reciprocal,video_psnr=psnr,video_sha256=animation['video_sha256'],prior_artifacts_unchanged=plan['prior_artifacts'],
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

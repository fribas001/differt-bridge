"""Verify and package the authoritative correction evidence without runtime caches."""
import argparse,hashlib,html,json,zipfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit,unquote

read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('workspace',type=Path);args=ap.parse_args();root=args.workspace.resolve()
    work=root/'work/dielectric-corrections';out=root/'outputs/differt-bridge/examples/dielectric_corrections'
    analysis=read(work/'final_analysis.json');geom=read(work/'final_geometry.json');exact=read(work/'coincidence.json')
    for name in ('sionna-reciprocal','differt-reciprocal'):
        s=analysis['summary'][name];assert s['completed']==286 and s['max_reciprocity_gain_db']<.001
        assert s['boundary_checks_at_0_001_deg']==s['boundary_within_1_percent']==50
        assert geom['summary'][name]['checks']==580 and geom['summary'][name]['failed']==0
        rows=[r for r in exact if r['profile']==name and r['material'] not in ('air','pec')]
        assert len(rows)==54 and max(r['normalized_error'] for r in rows)<.001
    assert all(r['passed'] for r in analysis['obstacles'])
    mixed=read(work/'mixed_analysis.json');assert len(mixed['obstacle_controls'])==6 and all(r['passed'] for r in mixed['obstacle_controls'])
    reference=read(work/'maxwell_analysis.json');engine=read(work/'maxwell_engines.json');boundary=read(work/'maxwell_boundary_engines.json')
    assert max(r.get('analytic_extrapolation_rms_error',0) for r in reference['results'])<.001
    assert max(r['rms_relative_change'] for r in engine['pml_controls'])<1e-6
    assert all(r['rms_complex_error']<.06 for r in engine['comparisons'] if r['profile'].endswith('reciprocal'))
    assert all(r['rms_complex_error']<.05 for r in boundary['comparisons'] if r['profile'].endswith('reciprocal'))

    for folder in [work/'final',work/'reference_engines',root/'work/rczb',root/'work/rczm']:
        receipt=read(folder/'receipt.json');assert receipt['status']=='passed'
        assert sha(folder/'cases.json')==receipt['manifest_sha256']
        for p in receipt['processes']:
            assert p['passed'] and sha(folder/p['profile']/p['output'])==p['output_sha256']
    installation=read(root/'outputs/differt-bridge/validation/reciprocal_profile.json')
    for name,digest in installation['added_files'].items():assert sha(root/name)==digest,name
    baseline=read(root/'work/cleanup-2026-11-01/protected_hashes.json')
    for file in ('diffraction_remediation.json','sionna_lifetime_fix.json','sionna_batch_fix.json'):
        r=read(root/'outputs/differt-bridge/validation'/file)
        for name,change in r.get('source_updates',{}).items():baseline[name]=change['after']
        baseline.update(r.get('added_files',{}))
    for name,digest in baseline.items():assert sha(root/name)==digest,name

    files={}
    def addtree(path,prefix,pattern='*.json'):
        for f in path.rglob(pattern):
            if f.is_file():files[prefix+'/'+f.relative_to(path).as_posix()]=f
    for name in ('final','reference_engines','maxwell','maxwell_pml','maxwell_boundary'):
        addtree(work/name,'results/'+name)
    for name in ('final_analysis.json','final_geometry.json','maxwell_analysis.json','maxwell_engines.json','maxwell_boundary_analysis.json','maxwell_boundary_engines.json','coincidence.json','mixed_analysis.json','final_mixed_cases.json'):
        files['results/'+name]=work/name
    for name in ('rczb','rczm','rcm2','rcm'):
        source=root/'work'/name
        for f in source.glob('*.json'):files['results/'+name+'/'+f.name]=f
        for folder in source.iterdir():
            if folder.is_dir():
                for f in folder.glob('*.json'):files['results/'+name+'/'+folder.name+'/'+f.name]=f
    project=Path(__file__).resolve().parents[1]
    for folder in ('scripts','tests','src'):
        addtree(project/folder,'project/'+folder,'*.py')
    addtree(project/'docs','project/docs','*.md')
    for f in project.glob('requirements*.txt'):files['project/'+f.name]=f
    for name in ('README.md','LICENSE','pyproject.toml'):files['project/'+name]=project/name
    for name in ('reciprocal_profile.json','reciprocal_blender.json','workflow_health.json'):
        files['validation/'+name]=root/'outputs/differt-bridge/validation'/name
    for f in (root/'work/rcbl2/activation').glob('*.json'):files['validation/worker_activation/'+f.name]=f
    files['validation/python_regression.log']=root/'work/dielectric-final-tests-writable.log'
    files['validation/new_physical_tests.log']=root/'work/dielectric-correction-unit-tests.log'
    files['validation/historical_unrounded_scalar_control.log']=root/'work/dielectric-unrounded-tests.log'
    for name in ('Launch_Diffraction.ps1','Launch_Reciprocal_Diffraction.ps1'):files['launchers/'+name]=root/name
    for f in out.glob('*.png'):files['report/'+f.name]=f
    files['report/index.html']=out/'index.html';files['validation/study_verification.json']=out/'verification.json'
    hashes={name:sha(path) for name,path in sorted(files.items())}
    archive=out/'correction_evidence.zip'
    instructions='''Reproduction evidence, 6 November 2026.

project/ contains source, scripts and tests. results/ contains raw manifests,
engine receipts and independent reference solutions. validation/ contains the
runtime/Blender/native-workflow receipts. No interpreter, credentials, compiler
cache, downloaded paper, or generated animation is bundled.

Use the already configured workstation runtimes to reproduce the main campaign:
python project/scripts/run_dielectric.py --differt-python PATH_TO_DIFFERT_PYTHON
  --sionna-python PATH_TO_SIONNA_PYTHON --llvm-library PATH_TO_LLVM_DLL
  --output NEW_OUTPUT --precision float32
  --profiles differt-native,sionna-native,differt-reciprocal,sionna-reciprocal
(Put the arguments on one command line.)

Use --manifest results/reference_engines/cases.json, results/rczb/cases.json or
results/rczm/cases.json for the Maxwell main, boundary or mixed fixtures.
Runtimes need the pre-existing validated workstation precision/Windows adapters;
version/source guards deliberately refuse an incompatible stock installation.
The historical depth-5 DiffeRT budget rejections in results/rcm are not passes.

The independent reference needs only NumPy/SciPy:
python project/scripts/run_maxwell_reference.py NEW_REFERENCE --grids 40,60,80
python project/scripts/run_maxwell_reference.py NEW_PML --grids 60 --pml 2.5
python project/scripts/run_maxwell_boundaries.py NEW_BOUNDARY --only concrete_Ez,concrete_Hz
Large sparse factorizations need substantial RAM and can take several minutes.

analyze_dielectric.py and audit_dielectric_boundaries.py accept an engine-output
folder and an output JSON filename. analyze_maxwell_reference.py takes a
reference folder and output JSON. analyze_maxwell_engines.py takes engine output,
reference analysis, PML folder and output JSON. See each script's --help.
The HTML build/pack scripts use the original workstation layout; numerical
analyzers and input manifests can be run at another chosen destination.

The optional profile is a reciprocal bridge approximation, not an exact Maxwell
solver or upstream release. Both constraints and independent accuracy limits
must be considered. See project/docs/dielectric-corrections.md.
'''
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,path in sorted(files.items()):z.write(path,name)
        z.writestr('REPRODUCE.txt',instructions)
        hashes['REPRODUCE.txt']=hashlib.sha256(instructions.encode()).hexdigest()
        z.writestr('SHA256SUMS.txt',''.join(d+'  '+n+'\n' for n,d in sorted(hashes.items())))
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for name,digest in hashes.items():assert hashlib.sha256(z.read(name)).hexdigest()==digest
    receipt=read(out/'verification.json')
    receipt['delivery_integrity']=dict(status='passed',archive=archive.name,archive_sha256=sha(archive),archive_members=len(hashes)+1,
        protected_source_runtime_files_verified=len(baseline),optional_profile_files_verified=len(installation['added_files']),plots_visually_inspected=True)
    (out/'verification.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    (out/'checksums.sha256').write_text(''.join(sha(p)+'  '+p.name+'\n' for p in sorted(out.iterdir()) if p.is_file() and p.name!='checksums.sha256'))
    class Links(HTMLParser):
        def __init__(self):super().__init__();self.urls=[]
        def handle_starttag(self,tag,attrs):self.urls.extend(v for k,v in attrs if k in ('href','src') and v)
    count=0
    for page in [out/'index.html',root/'index.html',out.parent/'dielectric_diffraction/index.html']:
        parser=Links();parser.feed(page.read_text(encoding='utf-8'))
        for url in parser.urls:
            u=urlsplit(html.unescape(url))
            if not u.scheme and u.path:assert (page.parent/unquote(u.path)).exists(),(page,url);count+=1
    print(json.dumps(dict(status='passed',archive_bytes=archive.stat().st_size,archive_members=len(hashes)+1,local_links_checked=count,protected_files=len(baseline),optional_files=len(installation['added_files'])),indent=2))

if __name__=='__main__':main()

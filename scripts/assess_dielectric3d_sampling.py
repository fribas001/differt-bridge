"""Separate a rejected sampling candidate from primary-reference validation."""
import sys
from pathlib import Path
from investigate_dielectric3d_polarization import read,save,sha

def main(root):
    w=root/'work/d3res';trial=read(w/'sampling_validation.json')
    for name,digest in trial['sources'].items():assert sha(Path(__file__).with_name(name))==digest
    assert [r['q'] for r in trial['planes']]==[[1.525532409916329,.4977669015873694],[4.9,.5]]
    for row in trial['planes']:assert [r['resolution'] for r in row['levels']]==[32,64,96]
    checks=[dict(name='original vector errors contract at every mesh',passed=all(all(a['original_error']>b['original_error'] for a,b in zip(r['levels'],r['levels'][1:])) for r in trial['planes'])),
        dict(name='original FEM96 vector error below 0.2 percent',passed=all(r['levels'][-1]['original_error']<.002 for r in trial['planes'])),
        dict(name='original FEM96 z-to-x error below 0.5 percent',passed=all(r['levels'][-1]['original_zx_error']<.005 for r in trial['planes'])),
        dict(name='original full-system residuals below 1e-9',passed=all(v['metadata']['linear_residual']<1e-9 for r in trial['planes'] for v in r['levels'])),
        dict(name='vacuum field remains zero',passed=trial['vacuum_maximum']<1e-12)]
    result=dict(status='passed' if all(v['passed'] for v in checks) else 'failed',checks=checks,
        cubic_candidate_accepted=trial['status']=='passed',candidate_status=trial['status'],trial_sha256=sha(w/'sampling_validation.json'),
        decision='Retain original field recovery. The cubic candidate is diagnosed separately; its rejection is not a failure of the original Maxwell reference.')
    save(w/'sampling_assessment.json',result);print(result,flush=True);assert result['status']=='passed'

if __name__=='__main__':main(Path(sys.argv[1]).resolve())

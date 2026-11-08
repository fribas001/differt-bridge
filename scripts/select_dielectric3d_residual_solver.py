"""Record a validated resource policy without overwriting failed experiments."""
import sys
from pathlib import Path
from investigate_dielectric3d_polarization import read,save,sha
from dielectric3d_bounded_solver import activate

def main(root):
    w=root/'work/d3res';policy=activate();controls=[]
    for n,indices in ((64,[0,5,20,26,29,32,40]),(96,[0,5,26]),(112,[0]),(128,[5,26])):
        p=w/f'bounded{n}/validation.json';v=read(p)
        assert v['status']=='passed' and v['config']['policy']==policy
        assert [r['index'] for r in v['rows']]==indices
        assert all(r['metadata']['linear_residual']<1e-9 and (r['error'] is None or r['error']<1e-8) for r in v['rows'])
        profile=read(w/f'bounded{n}.profile.json');assert profile['status']=='passed'
        controls.append(dict(resolution=n,validation_sha256=sha(p),profile=profile,maximum_field_difference=max((r['error'] or 0) for r in v['rows']),scope='resource feasibility only' if n==112 else 'same-equation comparison against saved direct fields'))
    result=dict(status='passed',policy=policy,controls=controls,
        decision='Use a process-local, zero-drop SuperLU factorization with basic dropping disabled by zero tolerance, no secondary fill quota, initial fill allocation 3 and panel size 8. It agrees with saved direct fields at FEM64, FEM96 and FEM128 and passes the residual gate in the original Maxwell matrix. Full-LU and Schur trials remain in the evidence: some failed or were stopped at memory limits. Static pivoting passed FEM64 but its FEM96 attempt hit the memory guard and was not adopted. No equation, matrix assembly, source, geometry, PML, precision or selected sampler is changed.',
        initial_resource_selection_superseded=sha(w/'resource_validation.json'),
        guard_measurement_note='Early static64/static96 profiles measured the Windows venv launcher, so their per-worker memory counters are invalid. Global commit samples remain diagnostic. New runs launch the actual base interpreter and terminate their own process tree on resource limits.',
        sources={n:sha(Path(__file__).with_name(n)) for n in ('dielectric3d_bounded_solver.py','validate_dielectric3d_bounded_solver.py','run_dielectric3d_bounded_reference.py','guard_reference_process.py')},
        documentation=['https://docs.scipy.org/doc/scipy/reference/generated/scipy.sparse.linalg.spilu.html','https://raw.githubusercontent.com/scipy/scipy/v1.18.0/scipy/sparse/linalg/_dsolve/SuperLU/SRC/zgstrf.c'])
    save(w/'resource_selection.json',result);print('RESOURCE_POLICY_VALIDATED',flush=True)

if __name__=='__main__':main(Path(sys.argv[1]).resolve())

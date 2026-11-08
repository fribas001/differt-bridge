import copy,sys
from pathlib import Path
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from dielectric3d_refinement import validate,refine,Refiner,UnsupportedScene
from dielectric3d_shadow_cases import primary,holdout

@pytest.fixture
def case():return primary()[0]

def test_primary_and_unseen_material_ports_are_accepted_without_mutation():
    cases=primary()+holdout();before=copy.deepcopy(cases)
    for c in cases:validate(c)
    assert cases==before

@pytest.mark.parametrize('change',[
    lambda c:c.pop('maxwell_domain'),
    lambda c:c['maxwell_domain'].update(source='line_source'),
    lambda c:c['meshes'].append(copy.deepcopy(c['meshes'][0])),
    lambda c:c['meshes'][0]['vertices'][0].__setitem__(0,1e-6),
    lambda c:c['meshes'][0]['triangles'].reverse(),
    lambda c:c['canonical_edges'][0].update(half_length=159.),
    lambda c:c.update(frequency_hz=3.5e9),
    lambda c:c.update(pattern='iso'),
    lambda c:c.update(tx_pol='H'),
    lambda c:c.update(array_rows=2),
    lambda c:c.update(array_cols=2),
    lambda c:c.update(tx_orientation=[.01,0,0]),
    lambda c:c.update(rx_orientation=[.01,0,0]),
    lambda c:c['material'].update(thickness=1.),
    lambda c:c['material'].update(relative_permittivity=1.),
    lambda c:c['material'].update(conductivity=0.),
    lambda c:c['material'].update(scattering_coefficient=.01),
    lambda c:c['solver'].update(diffuse_reflection=True),
    lambda c:c['solver'].update(refraction=True),
    lambda c:c['solver'].update(edge_diffraction=True),
    lambda c:c['solver'].update(synthetic_array=True),
    lambda c:c['solver'].update(max_depth=2),
    lambda c:c['solver'].update(los=False),
    lambda c:c['solver'].update(diffraction=False),
    lambda c:c['solver'].update(specular_reflection=False),
    lambda c:c['receivers'].__setitem__(0,[1.,1.,0.]),
    lambda c:c['receivers'].__setitem__(0,c['tx'].copy()),
    lambda c:c['receivers'].__setitem__(0,[-4.,0.,0.]),
    lambda c:c['receivers'].__setitem__(0,[-1.,-1.,3.1]),
    lambda c:c['receivers'].__setitem__(0,[float('nan'),0.,0.]),
    lambda c:c.update(receivers=[]),
])
def test_unsupported_scenes_fail_closed(case,change):
    change(case)
    with pytest.raises(UnsupportedScene):validate(case)

def test_actual_orientation_controls_port_axis_not_study_label(case):
    case['study'].update(tx_axis='z',rx_axis='z')
    assert validate(case)[1:]==(0,0)

def test_stale_checkpoint_cannot_supply_a_different_scene(tmp_path):
    (tmp_path/'config.json').write_text('{}')
    with pytest.raises(ValueError,match='Checkpoint inputs or solver source changed'):
        Refiner().solve(4-.5j,[[-1.2,.8,0]],[[-.8,-1.1,1]],tmp_path)

def test_whole_batch_and_thin_obstacle_guard_precedes_any_output(case,tmp_path,monkeypatch):
    blocked=copy.deepcopy(case);blocked['meshes'].append(dict(name='micron_obstacle',vertices=[[0,0,0],[1e-6,0,0],[0,1e-6,0]],triangles=[[0,1,2]],material='wall'))
    def forbidden(*a,**k):pytest.fail('Unsupported geometry reached field solver')
    monkeypatch.setattr(Refiner,'solve',forbidden);target=tmp_path/'not_created'
    with pytest.raises(UnsupportedScene):refine([case,blocked],target)
    assert not target.exists()

def test_fem_diagnostics_do_not_materialize_factor_copies(monkeypatch):
    import dielectric3d_fem as fem
    original=fem.splu
    class NoCopies:
        def __init__(self,lu):self.lu=lu
        @property
        def nnz(self):return self.lu.nnz
        def solve(self,rhs):return self.lu.solve(rhs)
        @property
        def L(self):raise AssertionError('Avoid unnecessary L copy')
        @property
        def U(self):raise AssertionError('Avoid unnecessary U copy')
    monkeypatch.setattr(fem,'splu',lambda *a,**k:NoCopies(original(*a,**k)))
    f,m=fem.VectorWedgeFEM(4).solve(3+.3j,4-.5j,[[-1.2,.8,0]],[[-.8,-1.1,1]],(0,1,2))
    assert np.isfinite(f).all() and m['linear_residual']<1e-10

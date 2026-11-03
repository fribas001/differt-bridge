"""Native DiffeRT checks: analytic RF cases and bridge coordinate/tensor contracts."""
from pathlib import Path
import sys,math
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/differt_bridge'))
import differt_backend as b


def scene(tmp_path,wall=False):
    vertices=([(-20,-20,0),(20,-20,0),(20,20,0),(-20,20,0)] if not wall else
              [(0,-20,-20),(0,20,-20),(0,20,20),(0,-20,20)])
    ply=tmp_path/'mesh.ply'
    ply.write_text('ply\nformat ascii 1.0\nelement vertex 4\nproperty float x\nproperty float y\nproperty float z\nelement face 2\nproperty list uchar int vertex_indices\nend_header\n'+'\n'.join(' '.join(map(str,v)) for v in vertices)+'\n3 0 1 2\n3 0 2 3\n')
    xml=tmp_path/'scene.xml'
    xml.write_text('<scene version="3.0.0"><shape type="ply" id="ground"><string name="filename" value="mesh.ply"/><ref id="itu_concrete"/></shape></scene>')
    s=b.load_scene(xml);s.frequency=3e9
    s.add(b.Transmitter('TX',[-2,-1,2]));s.add(b.Receiver('RX',[2,1,2]))
    s.configure_materials([])
    return s


def test_free_space_delay_loss_and_doppler(tmp_path):
    s=scene(tmp_path);s.receivers['RX'].velocity=[1,0,0]
    p=b.PathSolver()(s,max_depth=0)
    assert p.valid.sum()==1
    distance=np.linalg.norm(np.array([4,2,0]))
    np.testing.assert_allclose(p.tau[p.valid],distance/b.C,rtol=1e-8)
    power=(p.a[0]**2+p.a[1]**2)[p.valid]
    np.testing.assert_allclose(power,(b.C/s.frequency/(4*np.pi*distance))**2,rtol=1e-7)
    np.testing.assert_allclose(p.doppler[p.valid],-4/distance*s.frequency/b.C,rtol=1e-8)


@pytest.mark.parametrize('frequency',[3.5e9,28e9])
def test_passband_phase_and_baseband_cir_are_distinct(tmp_path,frequency):
    s=scene(tmp_path);s.frequency=frequency
    p=b.PathSolver()(s,max_depth=0)
    a=(p.a[0]+1j*p.a[1])[p.valid]
    expected=b.C/frequency/(4*np.pi*np.sqrt(20))
    np.testing.assert_allclose(a,expected,rtol=1e-10,atol=1e-14)
    cir,tau=p.cir()
    np.testing.assert_allclose(cir[...,0][p.valid],a*np.exp(-2j*np.pi*frequency*tau[p.valid]),rtol=1e-10)
    assert s.backend_metadata()['path_coefficient_convention']=='passband_without_propagation_phase'


def test_obstruction_and_no_enabled_paths(tmp_path):
    s=scene(tmp_path,wall=True)
    assert b.PathSolver()(s,max_depth=0).valid.sum()==0
    assert b.PathSolver()(s,los=False,specular_reflection=False,max_depth=2).valid.sum()==0


def test_ground_reflection_geometry_and_material(tmp_path):
    s=scene(tmp_path)
    p=b.PathSolver()(s,max_depth=1,los=False)
    assert p.valid.sum()==1 # coplanar triangle seam must not double-count energy
    np.testing.assert_allclose(p.vertices[0][p.valid],[[0,0,0]],atol=1e-6)
    np.testing.assert_allclose(p.tau[p.valid],6/b.C,rtol=1e-7)
    assert np.all(p.interactions[0][p.valid]==1)
    assert np.all(np.isfinite(p.a[0]))
    old=abs((p.a[0]+1j*p.a[1])[p.valid][0])
    s.configure_materials([dict(source_name='itu_concrete',model='CUSTOM',relative_permittivity=1.,conductivity=0.,thickness=.1)])
    q=b.PathSolver()(s,max_depth=1,los=False)
    assert np.max(np.abs(q.a[0]+1j*q.a[1]))<old*1e-5


def test_array_ports_and_absolute_cir(tmp_path):
    s=scene(tmp_path);s.tx_array=b.PlanarArray(num_cols=2,polarization='VH')
    p=b.PathSolver()(s,max_depth=0)
    assert p.valid.shape[:4]==(1,1,1,4)
    assert p.valid.sum()==4
    a,tau=p.cir()
    assert a.shape==p.valid.shape+(1,)
    assert tau.shape==p.valid.shape
    assert not np.allclose(tau[...,0,0],tau[...,1,0],atol=1e-13)


def test_maps_rotation_rss_sinr_and_receiver_restore(tmp_path):
    s=scene(tmp_path);s.transmitters['TX'].power_dbm=30
    old=s.receivers
    m=b.RadioMapSolver()(s,center=[0,0,4],size=[4,2],cell_size=[2,1],orientation=[0,0,math.pi/2],max_depth=0)
    assert m.cell_centers.shape==(2,2,3)
    np.testing.assert_allclose(m.cell_centers[...,1],0,atol=1e-10)
    assert s.receivers is old
    np.testing.assert_allclose(m.rss,m.path_gain)
    np.testing.assert_allclose(m.sinr,m.rss/(1.380649e-23*s.temperature*s.bandwidth))
    distances=np.linalg.norm(m.cell_centers-np.array(s.transmitters['TX'].position),axis=-1)
    np.testing.assert_allclose(m.path_gain[0],(b.C/s.frequency/(4*np.pi*distances))**2,rtol=1e-6)


def test_budget_and_unsupported_polarization_are_explicit(tmp_path):
    s=scene(tmp_path);s.bridge_simulation['differt_max_candidates']=1
    with pytest.raises(ValueError,match='budget'):b.PathSolver()(s,max_depth=2)
    with pytest.raises(ValueError,match='model 2'):b.PlanarArray(polarization_model='tr38901_1')


def test_projected_mesh_centers(tmp_path):
    s=scene(tmp_path)
    mesh=b.eqx.tree_at(lambda m:m.vertices,s.mesh,s.mesh.vertices+b.jnp.array([0.,0.,5.]))
    m=b.RadioMapSolver()(s,measurement_surface=mesh,max_depth=0)
    np.testing.assert_allclose(m.cell_centers,np.asarray(mesh.vertices)[np.asarray(mesh.triangles)].mean(axis=1))
    assert m.path_gain.shape==(1,2)


def test_vegetation_updates_at_frame_frequency(tmp_path):
    s=scene(tmp_path)
    preset=next(iter(b.plant_materials.MODELS)) if hasattr(b.plant_materials,'MODELS') else next(iter(b.plant_materials.PRESETS.values()))['model']
    spec=dict(source_name='itu_concrete',model='VEGETATION',plant_model=preset,thickness=.01)
    s.frequency=10e9;a=s.configure_materials([spec])[0]
    s.frequency=26e9;c=s.configure_materials([spec])[0]
    expected=b.plant_materials.dielectric(preset,26e9)
    np.testing.assert_allclose([c['relative_permittivity'],c['conductivity']],expected)
    assert a['conductivity']!=c['conductivity']


def test_native_thin_slab_transmission(tmp_path):
    s=scene(tmp_path,wall=True)
    p=b.PathSolver()(s,max_depth=1,los=False,specular_reflection=False,refraction=True)
    assert p.valid.sum()==1
    assert np.all(p.interactions[0][p.valid]==4)
    power=(p.a[0]**2+p.a[1]**2)[p.valid]
    assert np.all(power>0)
    np.testing.assert_allclose(p.tau[p.valid],np.sqrt(20)/b.C,rtol=1e-6)


@pytest.mark.parametrize('method',['hybrid','sbr'])
def test_alternative_search_methods(tmp_path,method):
    s=scene(tmp_path);s.bridge_simulation['differt_solver']=method
    p=b.PathSolver()(s,max_depth=1,samples_per_src=1024)
    assert p.valid.sum()>=1
    assert s.backend_metadata()['path_solver']==method
    assert np.all(np.isfinite(p.a[0][p.valid]))


def test_native_diffraction_and_scattering(tmp_path):
    s=scene(tmp_path,wall=True)
    # Adjacent non-coplanar faces form an eligible wedge; open sheet boundaries do not.
    s.mesh=b.Mesh(vertices=b.jnp.array([[0,0,0],[1,0,0],[1,1,0],[1,0,-1]],dtype=b.jnp.float32),
        triangles=b.jnp.array([[0,1,2],[1,3,2]],dtype=b.jnp.int32),
        face_materials=b.jnp.array([0,0],dtype=b.jnp.int32),material_names=('itu_concrete',))
    s.transmitters['TX'].position=[.5,.5,1.]
    s.receivers['RX'].position=[2.,.5,-.5]
    p=b.PathSolver()(s,max_depth=1,los=False,specular_reflection=False,diffraction=True)
    assert p.valid.sum()>0
    assert np.all(p.interactions[0][p.valid]==8)
    assert np.all(np.isfinite(p.a[0][p.valid]))
    # Scattering is tested on the illuminated side of the ground.
    s=scene(tmp_path)
    s.configure_materials([dict(source_name='itu_concrete',model='CUSTOM',relative_permittivity=4.,conductivity=.01,scattering_coefficient=.5)])
    p=b.PathSolver()(s,max_depth=1,los=False,specular_reflection=False,diffuse_reflection=True)
    assert p.valid.sum()>0
    assert np.all(p.interactions[0][p.valid]==2)
    assert np.max(p.a[0]**2+p.a[1]**2)>0

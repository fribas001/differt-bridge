"""Deterministic diffraction fixtures. All engine inputs derive from this file."""
import copy
import json
import math
from pathlib import Path
import struct


def f32(x):
    return struct.unpack('f', struct.pack('f', x))[0]


def wedge(name='wedge', origin=(0, 0, 0), rotation=0, angle=90, length=20, height=20):
    # Solid sector lies between the +x ray and the ray at `angle`.
    a, r = math.radians(angle), math.radians(rotation)
    vertices = [(0,0,-height),(length,0,-height),(length,0,height),(0,0,height),
                (length*math.cos(a),length*math.sin(a),height),
                (length*math.cos(a),length*math.sin(a),-height)]
    vertices = [[f32(x*math.cos(r)-y*math.sin(r)+origin[0]),
                 f32(x*math.sin(r)+y*math.cos(r)+origin[1]), f32(z+origin[2])] for x,y,z in vertices]
    return dict(name=name, vertices=vertices, triangles=[[0,1,2],[0,2,3],[0,3,4],[0,4,5]], material='wall')


def quad(name, vertices, material='wall'):
    return dict(name=name, vertices=[[f32(x) for x in v] for v in vertices], triangles=[[0,1,2],[0,2,3]], material=material)


def base(name='wedge_v'):
    return dict(name=name, category='single_wedge', meshes=[wedge()], tx=[-4.,4.,0.], receivers=[[4.,-2.,0.]],
                frequency_hz=3.5e9, tx_pol='V', rx_pol='V', pattern='iso',
                material=dict(relative_permittivity=f32(5.24), conductivity=f32(.123086944), thickness=f32(.1), scattering_coefficient=0.),
                solver=dict(max_depth=1, samples_per_src=65536, max_num_paths_per_src=20000,
                    los=False, specular_reflection=False, diffuse_reflection=False, refraction=False,
                    diffraction=True, edge_diffraction=False, diffraction_lit_region=True, synthetic_array=False, seed=42),
                differt_solver='exhaustive', repeats=1, expected='One central-edge diffraction path per RX',
                canonical_edges=[dict(origin=[0.,0.,0.], direction=[0.,0.,1.], half_length=20.)])


def pilot_cases():
    a=base(); cases=[a]
    b=copy.deepcopy(a); b.update(name='wedge_h', tx_pol='H', rx_pol='H'); cases.append(b)
    b=copy.deepcopy(a); b.update(name='wedge_reciprocal', tx=a['receivers'][0], receivers=[a['tx']]); cases.append(b)
    b=copy.deepcopy(a); b.update(name='diffraction_disabled', category='negative_control', expected='No paths with all interactions disabled'); b['solver']['diffraction']=False; cases.append(b)
    b=copy.deepcopy(a); b.update(name='open_sheet_edge_on', category='edge_eligibility',
        meshes=[quad('sheet',[(0,0,-20),(20,0,-20),(20,0,20),(0,0,20)])], expected='Sionna boundary-edge support; DiffeRT bridge excludes open boundaries'); b['solver']['edge_diffraction']=True; cases.append(b)
    b=copy.deepcopy(a); b.update(name='double_wedge',category='multiple_diffraction',tx=[-3.,3.,0.],receivers=[[7.,-5.,0.]],
        meshes=[wedge(),wedge('second',origin=(4,-2,0),rotation=180)],
        canonical_edges=[dict(origin=[0.,0.,0.],direction=[0.,0.,1.],half_length=20.),dict(origin=[4.,-2.,0.],direction=[0.,0.,1.],half_length=20.)],
        expected='A two-edge path is geometrically required; Sionna cannot represent two diffraction events'); b['solver']['max_depth']=2; cases.append(b)
    b=copy.deepcopy(a); b.update(name='reflection_diffraction',category='mixed_interaction',
        meshes=[wedge(),quad('ground',[(-20,-20,-3),(20,-20,-3),(20,20,-3),(-20,20,-3)])],
        expected='Direct diffraction and ground-reflection/diffraction sequences'); b['solver'].update(max_depth=2,specular_reflection=True); cases.append(b)
    return cases


def benchmark_cases():
    cases=pilot_cases()
    def variant(name, category, **changes):
        b=base(name); b['category']=category; b.update(changes); cases.append(b); return b
    for ghz in (.7,2.4,5.8,28,60):
        variant('frequency_'+str(ghz).replace('.','_'),'frequency',frequency_hz=f32(ghz*1e9))
    for name,er,sigma,d in [('dielectric_lossless',4.,0.,.1),('high_loss',5.24,10.,.1),
                          ('metal_1e7',1.,1e7,.1),('metal_1e10',1.,1e10,.1),
                          ('thin_1mm',5.24,.123086944,.001),('thick_1m',5.24,.123086944,1.)]:
        b=variant(name,'material'); b['material'].update(relative_permittivity=f32(er),conductivity=f32(sigma),thickness=f32(d))
    b=variant('metal_h','material',tx_pol='H',rx_pol='H'); b['material'].update(relative_permittivity=1.,conductivity=f32(1e10))
    variant('cross_vh','polarization',tx_pol='V',rx_pol='H',expected='Broadside symmetry gives cross-polar null; phase is undefined at zero field')
    variant('skew_heights','skew_incidence',tx=[-4.,4.,-3.],receivers=[[4.,-2.,z] for z in (-10.,-3.,0.,5.,15.)])
    variant('skew_h','polarization',tx=[-4.,4.,-3.],receivers=[[4.,-2.,5.]],tx_pol='H',rx_pol='H')
    variant('skew_vh','polarization',tx=[-4.,4.,-3.],receivers=[[4.,-2.,5.]],tx_pol='V',rx_pol='H')
    for angle in (45,135):
        variant('wedge_angle_'+str(angle),'wedge_angle',meshes=[wedge(angle=angle)],tx=[-4.,1.,0.],receivers=[[4.,-2.,0.]])
    b=variant('lit_region_sweep','lit_region',receivers=[[f32(5*math.cos(math.radians(a))),f32(5*math.sin(math.radians(a))),0.] for a in (100,135,180,225,270,300,310,320,335,350)],
              angles_deg=[100,135,180,225,270,300,310,320,335,350],expected='All endpoints outside wedge; lit-region controls differ between bridges')
    b=copy.deepcopy(b); b['name']='lit_region_disabled'; b['solver']['diffraction_lit_region']=False; cases.append(b)
    offsets=[-.1,-.01,-.001,-.0001,0,.0001,.001,.01,.1]
    for pol in ('V','H'):
        b=variant('shadow_boundary_'+pol.lower(),'shadow_boundary',tx_pol=pol,rx_pol=pol,
            receivers=[[f32(5*math.cos(math.radians(315+a))),f32(5*math.sin(math.radians(315+a))),0.] for a in offsets],
            boundary_offsets_deg=offsets,expected='Total coherent field should approach the same limit across the incident shadow boundary')
        b['solver']['los']=True
    b=variant('open_sheet_edge_off','edge_eligibility',meshes=[quad('sheet',[(0,0,-20),(20,0,-20),(20,0,20),(0,0,20)])],expected='Open boundaries disabled: no diffraction paths')
    b=variant('finite_edge_outside','edge_endpoints',meshes=[wedge(height=1)],tx=[-4.,4.,5.],receivers=[[4.,-2.,5.]],
              canonical_edges=[dict(origin=[0.,0.,0.],direction=[0.,0.,1.],half_length=1.)],expected='Stationary point outside finite edge: no central-edge diffraction')
    b=variant('edge_endpoint','edge_endpoints',meshes=[wedge(height=1)],tx=[-4.,4.,1.],receivers=[[4.,-2.,1.]],
              canonical_edges=[dict(origin=[0.,0.,0.],direction=[0.,0.,1.],half_length=1.)],expected='Exact edge endpoint is a degeneracy, not a point-diffraction model')
    b=variant('unwelded_faces','mesh_topology'); m=b['meshes'][0]; m['vertices']=m['vertices']+[m['vertices'][0],m['vertices'][3]]; m['triangles']=[[0,1,2],[0,2,3],[6,7,4],[6,4,5]]
    b=variant('coplanar_seam','mesh_topology',meshes=[wedge(angle=180)],tx=[-4.,-4.,0.],receivers=[[4.,-2.,0.]],expected='Coplanar shared edge must not act as a wedge')
    b=variant('reversed_winding','mesh_topology'); b['meshes'][0]['triangles']=[t[::-1] for t in b['meshes'][0]['triangles']]
    b=variant('split_objects','mesh_topology'); m=b['meshes'][0]; b['meshes']=[dict(name='face_a',vertices=m['vertices'],triangles=m['triangles'][:2],material='wall'),dict(name='face_b',vertices=m['vertices'],triangles=m['triangles'][2:],material='wall')]
    # Block only the incoming/outgoing central-edge route with an unrelated sheet.
    for name,vertices in [
        ('block_incoming',[(-2,1,-2),(-2,3,-2),(-2,3,2),(-2,1,2)]),
        ('block_outgoing',[(2,-2,-2),(2,0,-2),(2,0,2),(2,-2,2)]),
        ('clear_nearby',[(-2,2.1,-2),(-2,3,-2),(-2,3,2),(-2,2.1,2)])]:
        b=variant(name,'visibility',meshes=[wedge(),quad('blocker',vertices)],expected='Blocked central-edge route' if name.startswith('block') else 'Nearby sheet does not block the central-edge route')
    for distance in (.1,.01,.001):
        b=variant('block_near_edge_'+str(distance).replace('.','_'),'visibility',
            meshes=[wedge(),quad('blocker',[(-distance,distance-.2,-2),(-distance,distance+.2,-2),(-distance,distance+.2,2),(-distance,distance-.2,2)])],expected='Real interior obstruction close to the diffraction point')
    for scale in (.001,.01,100.):
        b=variant('scale_'+str(scale).replace('.','_'),'scale_limits');
        for m in b['meshes']: m['vertices']=[[f32(x*scale) for x in v] for v in m['vertices']]
        b['tx']=[f32(x*scale) for x in b['tx']]; b['receivers']=[[f32(x*scale) for x in p] for p in b['receivers']]
        b['canonical_edges'][0]['half_length']*=scale
        b['expected']='Scale/segment threshold probe; fixed frequency means this is not EM scale invariance'
    b=variant('translated_10km','coordinate_precision'); shift=[10000.,-10000.,10000.]
    for m in b['meshes']: m['vertices']=[[f32(x+s) for x,s in zip(v,shift)] for v in m['vertices']]
    b['tx']=[f32(x+s) for x,s in zip(b['tx'],shift)]; b['receivers']=[[f32(x+s) for x,s in zip(v,shift)] for v in b['receivers']]; b['canonical_edges'][0]['origin']=shift
    for method in ('hybrid','sbr'):
        variant('search_'+method,'candidate_search',differt_solver=method)
    for rays in (256,4096,262144):
        b=variant('rays_'+str(rays),'candidate_search'); b['solver']['samples_per_src']=rays
    for seed in (7,123):
        b=variant('seed_'+str(seed),'candidate_search'); b['solver']['seed']=seed
    b=variant('repeat_warm','repeatability',repeats=3)
    for depth in (1,3):
        b=copy.deepcopy(next(c for c in cases if c['name']=='double_wedge')); b['name']='double_wedge_depth_'+str(depth); b['solver']['max_depth']=depth; cases.append(b)
    b=copy.deepcopy(next(c for c in cases if c['name']=='reflection_diffraction')); b['name']='mixed_reciprocal'; b['tx'],b['receivers']=b['receivers'][0],[b['tx']]; cases.append(b)
    for interaction in ('refraction','diffuse_reflection'):
        b=variant('mixed_'+interaction,'mixed_interaction'); b['solver'].update(max_depth=2); b['solver'][interaction]=True
        if interaction=='diffuse_reflection': b['material']['scattering_coefficient']=f32(.5)
        b['expected']='Interaction-combination capability probe, not an equality assertion'
    for case in cases:
        case['tx']=[f32(x) for x in case['tx']]
        case['receivers']=[[f32(x) for x in p] for p in case['receivers']]
    return cases


def write_scene(case, folder):
    folder.mkdir(parents=True,exist_ok=True)
    from xml.etree import ElementTree as ET
    root=ET.Element('scene',version='3.0.0')
    mat=ET.SubElement(root,'bsdf',type='radio-material',id='wall')
    for key,value in case['material'].items(): ET.SubElement(mat,'float',name=key,value=str(value))
    for mesh in case['meshes']:
        vertices,triangles=mesh['vertices'],mesh['triangles']
        text='ply\nformat ascii 1.0\nelement vertex '+str(len(vertices))+'\nproperty float x\nproperty float y\nproperty float z\nelement face '+str(len(triangles))+'\nproperty list uchar int vertex_indices\nend_header\n'
        text+=''.join(' '.join(map(str,v))+'\n' for v in vertices)
        text+=''.join('3 '+' '.join(map(str,t))+'\n' for t in triangles)
        (folder/(mesh['name']+'.ply')).write_text(text,encoding='ascii')
        shape=ET.SubElement(root,'shape',type='ply',id=mesh['name'])
        ET.SubElement(shape,'string',name='filename',value=mesh['name']+'.ply')
        ET.SubElement(shape,'boolean',name='face_normals',value='true')
        ET.SubElement(shape,'ref',id=mesh['material'],name='bsdf')
    ET.ElementTree(root).write(folder/'scene.xml',encoding='utf-8',xml_declaration=True)
    return folder/'scene.xml'


if __name__=='__main__':
    import sys
    target=Path(sys.argv[1]); target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(dict(schema='diffraction_cases_v1',cases=benchmark_cases() if '--full' in sys.argv else pilot_cases()),indent=2))

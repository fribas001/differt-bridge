"""DiffeRT 0.12 execution adapter for the bridge's portable result contract.

Only worker processes import this module. No Sionna, Mitsuba or Dr.Jit is used.
Candidate search and EM fields are computed by DiffeRT. The adapter validates
LoS/specular visibility and refines reflection/diffraction geometry in float64,
aligns phase conventions, expands arrays, maps tensor axes and samples coverage.
"""
from __future__ import annotations

import importlib.metadata
import math
import os
from pathlib import Path
from types import SimpleNamespace
import xml.etree.ElementTree as ET

import numpy as np
import equinox as eqx
import jax
import jax.numpy as jnp
import differt
import warp as wp
from differt.geometry import Mesh, Scene
from differt.em import (Material, MaterialsDict, materials, GeometricFieldSolver,
                       InteractionType, LambertianPattern, DirectivePattern,
                       BackscatteringPattern)
from radio_map_orientation import plane_basis
import plant_materials
from precise_visibility import SegmentVisibility, trace_specular
from segment_policy import segment_profile,SHARED_PROFILE,MINIMUM_M

jax.config.update('jax_enable_x64', True)
wp.config.kernel_cache_dir = os.environ.get('WP_CACHE_DIR', str(Path(os.environ.get('TEMP', '.'))/'differt-warp'))
__version__ = '0.6.3'
C = 299792458.0
if importlib.metadata.version('differt') != '0.12.0':
    raise RuntimeError('DiffeRT-Bridge requires differt==0.12.0; install requirements-external.txt')


def variant():
    return jax.default_backend()


def rotation(angles):
    """Local to world Rz(alpha) Ry(beta) Rx(gamma), shared with export."""
    a,b,c = map(float, angles)
    ca,sa,cb,sb,cc,sc = math.cos(a),math.sin(a),math.cos(b),math.sin(b),math.cos(c),math.sin(c)
    return np.array([[ca*cb,ca*sb*sc-sa*cc,ca*sb*cc+sa*sc],
                     [sa*cb,sa*sb*sc+ca*cc,sa*sb*cc-ca*sc],[-sb,cb*sc,cb*cc]])


class PlanarArray:
    def __init__(self, num_rows=1, num_cols=1, vertical_spacing=.5,
                 horizontal_spacing=.5, pattern='iso', polarization='V',
                 polarization_model='tr38901_2'):
        if pattern not in ('iso','dipole','hw_dipole','tr38901'):
            raise ValueError(f'Unsupported antenna pattern: {pattern}')
        if polarization not in ('V','H','VH','cross'):
            raise ValueError(f'Unsupported polarization: {polarization}')
        if polarization_model != 'tr38901_2':
            raise ValueError('DiffeRT-Bridge currently supports polarization model 2; select TR 38.901 model 2')
        self.__dict__.update(num_rows=int(num_rows), num_cols=int(num_cols),
            vertical_spacing=float(vertical_spacing),horizontal_spacing=float(horizontal_spacing),
            pattern=pattern,polarization=polarization,polarization_model=polarization_model)
    @property
    def num_ant(self):
        return self.num_rows*self.num_cols*(2 if self.polarization in ('VH','cross') else 1)
    def offsets(self, wavelength):
        # Column-major YZ array, centered at the device; same role order in exports.
        base=np.array([[0, (col-(self.num_cols-1)/2)*self.horizontal_spacing,
                       ((self.num_rows-1)/2-row)*self.vertical_spacing]
                      for col in range(self.num_cols) for row in range(self.num_rows)])*wavelength
        angles={'V':[0.], 'H':[math.pi/2], 'VH':[0.,math.pi/2], 'cross':[-math.pi/4,math.pi/4]}[self.polarization]
        return np.tile(base,(len(angles),1)), np.repeat(angles,len(base))


class Device:
    def __init__(self,name,position,orientation=(0,0,0)):
        self.name=name; self.position=position; self.orientation=orientation
        self.velocity=[0.,0.,0.]; self.power_dbm=44.
    def look_at(self,target):
        d=np.asarray(target)-np.asarray(self.position)
        self.orientation=[math.atan2(d[1],d[0]),-math.atan2(d[2],np.linalg.norm(d[:2])),0.]

class Transmitter(Device): pass
class Receiver(Device): pass


class BridgePattern(eqx.Module):
    """Normalized element field in the antenna's local spherical basis (model 2)."""
    center: jax.Array
    rotation_matrix: jax.Array
    slant: jax.Array
    pattern: str = eqx.field(static=True)
    def polarization_vectors(self,r):
        direction=r-self.center
        direction=direction/jnp.maximum(jnp.linalg.norm(direction,axis=-1,keepdims=True),1e-20)
        local=jnp.einsum('...i,...ij->...j',direction,self.rotation_matrix)
        theta=jnp.arccos(jnp.clip(local[...,2],-1.,1.))
        phi=jnp.arctan2(local[...,1],local[...,0])
        st=jnp.sin(theta)
        if self.pattern=='iso':
            gain=jnp.ones_like(theta)
        elif self.pattern=='dipole':
            gain=1.5*st**2
        elif self.pattern=='hw_dipole':
            gain=1.643*(jnp.cos(math.pi/2*jnp.cos(theta))/jnp.maximum(st,1e-12))**2
        else:
            vertical=jnp.minimum(12*((theta*180/math.pi-90)/65)**2,30.)
            horizontal=jnp.minimum(12*((phi*180/math.pi)/65)**2,30.)
            gain=10**((8-jnp.minimum(vertical+horizontal,30.))/10)
        et=jnp.stack([jnp.cos(theta)*jnp.cos(phi),jnp.cos(theta)*jnp.sin(phi),-st],axis=-1)
        ep=jnp.stack([-jnp.sin(phi),jnp.cos(phi),jnp.zeros_like(phi)],axis=-1)
        v=jnp.sqrt(gain)[...,None]*(jnp.cos(self.slant)[...,None]*et+jnp.sin(self.slant)[...,None]*ep)
        world=jnp.einsum('...ij,...j->...i',self.rotation_matrix,v)
        return world,jnp.zeros_like(world)


def load_mesh(path,flip_normals=False):
    mesh=Mesh.load_ply(path)
    if flip_normals:
        mesh=eqx.tree_at(lambda m:m.triangles,mesh,mesh.triangles[:,::-1])
    return mesh


class BridgeScene:
    def __init__(self,path):
        self.path=str(path); self.frequency=28e9; self.bandwidth=1e6; self.temperature=293.
        self.transmitters={}; self.receivers={}; self.tx_array=PlanarArray(); self.rx_array=PlanarArray()
        self.radio_materials={}; self.objects={}; self.bridge_simulation={}
        self.material_summary=[]; self.last_diagnostics={}
        vertices=[]; triangles=[]; ids=[]; names=[]; bounds=[]; offset=0; face_offset=0
        root=ET.parse(path).getroot()
        for shape in root.findall('shape'):
            if shape.get('type')!='ply' or shape.find('transform') is not None:
                raise ValueError('Use the integrated Blender exporter: world-space PLY shapes are required')
            filename=shape.find("string[@name='filename']")
            if filename is None: raise ValueError('PLY shape has no filename')
            mesh=load_mesh(str(Path(path).parent/filename.get('value')))
            v=np.asarray(mesh.vertices); f=np.asarray(mesh.triangles)
            ref=shape.find('ref'); name=ref.get('id') if ref is not None else 'default-bsdf'
            if name not in names: names.append(name)
            vertices.append(v); triangles.append(f+offset); ids.extend([names.index(name)]*len(f))
            bounds.append([face_offset,face_offset+len(f)])
            self.objects[shape.get('id',str(len(bounds)))]=SimpleNamespace(material_name=name)
            offset+=len(v); face_offset+=len(f)
        if not triangles: raise ValueError('No triangular geometry was exported')
        # DiffeRT's Warp intersection kernels require float32 geometry.
        self.mesh=Mesh(vertices=jnp.asarray(np.concatenate(vertices),dtype=jnp.float32),
            triangles=jnp.asarray(np.concatenate(triangles),dtype=jnp.int32),
            face_materials=jnp.asarray(ids,dtype=jnp.int32),material_names=tuple(names),
            object_bounds=jnp.asarray(bounds,dtype=jnp.int32))
        self.native_materials={}
    def add(self,device):
        (self.transmitters if isinstance(device,Transmitter) else self.receivers)[device.name]=device
    def remove(self,name):
        self.transmitters.pop(name,None);self.receivers.pop(name,None)
    def configure_materials(self,specs):
        by_name={}
        for s in specs:
            for key in ('source_name','runtime_name','blender_name'):
                if s.get(key): by_name[s[key].removeprefix('mat-')]=s
        summary=[]; native={}; presets=MaterialsDict(materials)
        for name in self.mesh.material_names:
            short=name.removeprefix('mat-'); spec=by_name.get(short)
            if spec is None:
                if short in presets: spec={'model':'ITU','itu_type':short}
                elif short=='default-bsdf': spec={'model':'ITU','itu_type':'concrete'}
                else: raise ValueError(f'No radio material configured for {name!r}')
            model=str(spec.get('model','ITU')).upper()
            if model=='ITU':
                key=spec.get('itu_type','concrete')
                key=key if key in presets else 'itu_'+key
                if key not in presets: raise ValueError(f'Unknown DiffeRT ITU material: {key}')
                er,sigma=map(float,presets[key].properties(self.frequency))
            elif model=='VEGETATION':
                er,sigma=plant_materials.dielectric(spec.get('plant_model'),self.frequency)
            else:
                er=float(spec.get('relative_permittivity',1));sigma=float(spec.get('conductivity',0))
            if not np.isfinite([er,sigma]).all():
                raise ValueError(f'Material {name}: frequency outside the DiffeRT ITU validity range')
            pattern=str(spec.get('scattering_pattern','lambertian'))
            scattering=(DirectivePattern(alpha_r=int(spec.get('directive_alpha_r',1))) if pattern=='directive' else
                BackscatteringPattern(alpha_r=int(spec.get('backscatter_alpha_r',1)),alpha_i=int(spec.get('backscatter_alpha_i',1)),lambda_=float(spec.get('backscatter_lambda',1))) if pattern=='backscattering' else LambertianPattern())
            values=dict(relative_permittivity=er,conductivity=sigma,thickness=float(spec.get('thickness',.1)),
                scattering_coefficient=float(spec.get('scattering_coefficient',0)),xpd_coefficient=float(spec.get('xpd_coefficient',0)))
            native[name]=Material(name=name,properties=lambda f,e=er,s=sigma:(jnp.asarray(e),jnp.asarray(s)),
                thickness=values['thickness'],scattering_coefficient=values['scattering_coefficient'],
                xpd_coefficient=values['xpd_coefficient'],scattering_pattern=scattering)
            self.radio_materials[name]=SimpleNamespace(name=name,**values)
            summary.append(dict(blender_name=spec.get('blender_name',short),differt_name=name,model=model,**values))
        for obj in self.objects.values(): obj.radio_material=self.radio_materials[obj.material_name]
        self.material_summary=summary;self.native_materials=native
        return summary
    def backend_metadata(self):
        return dict(engine='DiffeRT',version=differt.__version__,jax_version=jax.__version__,
            devices=[str(d) for d in jax.devices()],array_model='explicit_element_positions',
            polarization_model='tr38901_2',map_model='point_receivers_incoherent_path_power',
            map_tx_array='equal-power incoherent elements; no precoding',
            doppler_model='endpoint_velocity_frozen_scatterers',
            interaction_object_ids='DiffeRT triangle/edge indices; not Sionna object IDs',
            seed_semantics='deterministic candidate generation; seed recorded but unused',
            path_coefficient_convention='passband_without_propagation_phase',
            cir_coefficient_convention='baseband_with_negative_carrier_delay_phase',
            bridge_version=__version__,
            **self.last_diagnostics)


def load_scene(path,merge_shapes=True):
    return BridgeScene(path)

# Kept as import names for the original bridge's runtime wiring, not used to run physics.
RadioMaterial=Material
ITURadioMaterial=Material


def expand_devices(devices,array,frequency,role):
    positions=[];rotations=[];slants=[];velocities=[]
    offsets,slant=array.offsets(C/frequency)
    for device in devices:
        rot=rotation(device.orientation)
        positions.extend(np.asarray(device.position)+offsets@rot.T)
        rotations.extend([rot]*len(offsets));slants.extend(slant)
        velocities.extend([device.velocity]*len(offsets))
    positions=np.asarray(positions,dtype=float)
    shape=(-1,1,1) if role=='tx' else (1,-1,1)
    pattern=BridgePattern(center=jnp.asarray(positions.reshape(*shape,3)),
        rotation_matrix=jnp.asarray(np.asarray(rotations).reshape(*shape,3,3)),
        slant=jnp.asarray(np.asarray(slants).reshape(shape)),pattern=array.pattern)
    return positions,np.asarray(velocities),pattern


class BridgePaths:
    def __init__(self,vertices,interactions,objects,valid,tau,coeff,doppler,sources,targets,baseband_coeff):
        self.__dict__.update(vertices=vertices,interactions=interactions,objects=objects,valid=valid,
            tau=tau,a=(coeff.real,coeff.imag),doppler=doppler,sources=sources,targets=targets,
            _baseband_coeff=baseband_coeff)
    def cir(self,normalize_delays=False,num_time_steps=1,out_type='numpy'):
        if normalize_delays or num_time_steps!=1 or out_type!='numpy':
            raise ValueError('Bridge CIR exports use absolute delays and a single frozen time sample')
        return self._baseband_coeff[...,None],self.tau


class PathSolver:
    def __init__(self,deterministic=True): self.deterministic=deterministic
    def __call__(self,scene,max_depth=3,max_num_paths_per_src=10000,samples_per_src=100000,
                 synthetic_array=True,los=True,specular_reflection=True,diffuse_reflection=False,
                 refraction=False,diffraction=False,edge_diffraction=False,diffraction_lit_region=True,seed=42):
        txs=list(scene.transmitters.values());rxs=list(scene.receivers.values())
        if not txs or not rxs: raise ValueError('At least one TX and one RX is required')
        if scene.frequency<=0: raise ValueError('Frequency must be positive')
        if segment_profile()==SHARED_PROFILE and (diffuse_reflection or refraction or diffraction):
            raise ValueError('Shared segment-length profile supports LoS/specular paths only')
        if not scene.native_materials: scene.configure_materials([])
        tp,tv,tpat=expand_devices(txs,scene.tx_array,scene.frequency,'tx')
        rp,rv,rpat=expand_devices(rxs,scene.rx_array,scene.frequency,'rx')
        if np.any(np.linalg.norm(tp[:,None]-rp[None,:],axis=-1)<1e-6):
            raise ValueError('Coincident TX/RX antenna elements are not a valid propagation link')
        native=Scene(transmitters=jnp.asarray(tp,dtype=jnp.float32),receivers=jnp.asarray(rp,dtype=jnp.float32),mesh=scene.mesh)
        allowed=frozenset(t for flag,t in [(specular_reflection,InteractionType.REFLECTION),
            (diffuse_reflection,InteractionType.SCATTERING),(refraction,InteractionType.TRANSMISSION),
            (diffraction,InteractionType.DIFFRACTION)] if flag)
        orders=([0] if los else [])+(list(range(1,int(max_depth)+1)) if allowed else [])
        sim=scene.bridge_simulation
        method=sim.get('differt_solver','exhaustive')
        if method not in ('exhaustive','hybrid','sbr'): raise ValueError(f'Unknown solver {method}')
        budget=int(sim.get('differt_max_candidates',1000000))
        # Mixed interactions may still enumerate a graph even with SBR. Refuse enormous searches early.
        sites=len(scene.mesh.triangles)*(int(specular_reflection)+int(diffuse_reflection)+int(refraction)+3*int(diffraction))
        estimate=sum(max(1,sites)**n for n in orders)
        if estimate>budget and (method!='sbr' or allowed != frozenset({InteractionType.REFLECTION})):
            raise ValueError(f'Candidate upper bound {estimate:,} exceeds budget {budget:,}. Lower depth, simplify geometry, increase budget, or use SBR for specular paths.')
        chunk=int(sim.get('differt_chunk_size',1024))
        kw={'chunk_size':chunk}
        if method in ('hybrid','sbr'): kw['num_rays']=int(samples_per_src)
        if method=='sbr': kw['max_num_candidates']=int(max_num_paths_per_src)
        field_solver=GeometricFieldSolver(tx_polarization=tpat,rx_polarization=rpat,radio_materials=scene.native_materials)
        # The aligned float32 profile exposes its original passband field.
        # Preserve it for paths.a instead of rotating into/out of the carrier
        # just to export a phase. CIR keeps the existing baseband calculation.
        # Stock DiffeRT and both native profiles retain their existing path.
        direct_passband=None
        try:
            from differt.em._bridge_precision import field_precision, passband_fields32
            from differt.em._bridge_arithmetic import arithmetic_profile
        except ImportError:
            pass
        else:
            if field_precision()=='float32' and arithmetic_profile()=='sionna_order':
                direct_passband=passband_fields32
        visibility=SegmentVisibility(scene.mesh)
        records=[[{} for _ in rp] for _ in tp]
        candidates=0
        edge_coordinates=np.asarray(scene.mesh.triangle_edges,dtype=float).reshape(-1,2,3) if diffraction else None
        for order in orders:
            traced=trace_specular(native,order,method,kw,visibility,allowed)
            chunks=[traced] if hasattr(traced,'vertices') else traced
            for paths in chunks:
                candidates+=int(paths.mask.shape[-1])
                if candidates>budget: raise ValueError('Candidate budget exceeded during path generation')
                mask=np.asarray(paths.mask,dtype=bool)
                if not np.any(mask): continue
                # Native received fields include exp(-j*2*pi*f*delay).
                # paths.a excludes it; cir() includes it. Preserve the existing
                # baseband result and, when available, the original passband.
                paths=eqx.tree_at(lambda p:p.vertices,paths,paths.vertices.astype(jnp.float64))
                fields=np.asarray(field_solver.compute_fields(paths,visibility.precise_mesh,scene.frequency))
                original_passband=(np.asarray(direct_passband(field_solver,paths,visibility.precise_mesh,scene.frequency))
                                   if direct_passband is not None else None)
                vv=np.asarray(paths.vertices,dtype=np.float64); oo=np.asarray(paths.objects); ii=np.asarray(paths.interaction_types)
                for ti,ri,pi in np.argwhere(mask):
                    vertices=vv[ti,ri,pi]; types=ii[ti,ri,pi]; objects=oo[ti,ri,pi,1:-1]
                    value=fields[ti,ri,pi]
                    if not np.isfinite(value): raise FloatingPointError('DiffeRT returned a nonfinite field for a valid path')
                    key=(tuple(types.tolist()),tuple(np.round(vertices,7).ravel()))
                    if diffraction and np.any(types==InteractionType.DIFFRACTION):
                        # Nearby but physically distinct edges must not be merged
                        # merely because their refined vertices round alike.
                        edge_ids=tuple(tuple(sorted(map(tuple,edge_coordinates[int(obj)])))
                            for obj,kind in zip(objects,types) if kind==InteractionType.DIFFRACTION)
                        key=(*key,edge_ids)
                    if key in records[ti][ri]: continue
                    segments=np.diff(vertices,axis=0); lengths=np.linalg.norm(segments,axis=-1)
                    if np.any(lengths<=1e-9): continue
                    velocity=np.dot(segments[0]/lengths[0],tv[ti])-np.dot(segments[-1]/lengths[-1],rv[ri])
                    doppler=velocity*scene.frequency/C if sim.get('mobility_doppler',True) else 0.
                    delay=lengths.sum()/C
                    passband=(original_passband[ti,ri,pi] if original_passband is not None
                              else value*np.exp(2j*np.pi*scene.frequency*delay))
                    if not np.isfinite(passband): raise FloatingPointError('DiffeRT returned a nonfinite passband field for a valid path')
                    records[ti][ri][key]=(vertices,types,objects,passband,delay,doppler,value)
        count=max((len(r) for row in records for r in row),default=0)
        nr,nt,ra,ta=len(rxs),len(txs),scene.rx_array.num_ant,scene.tx_array.num_ant
        shape=(nr,ra,nt,ta,count);depth=int(max_depth)
        vertices=np.zeros((depth,*shape,3));interactions=np.zeros((depth,*shape),dtype=np.int32)
        objects=np.full((depth,*shape),-1,dtype=np.int32);valid=np.zeros(shape,dtype=bool)
        tau=np.full(shape,-1.);coeff=np.zeros(shape,dtype=complex);doppler=np.zeros(shape)
        baseband=np.zeros(shape,dtype=complex)
        flags={0:1,1:8,2:2,3:4}
        for ti,row in enumerate(records):
            for ri,rr in enumerate(row):
                for pi,(vv,ii,oo,a,delay,fd,bb) in enumerate(rr.values()):
                    index=(ri//ra,ri%ra,ti//ta,ti%ta,pi);n=len(ii)
                    valid[index]=True;tau[index]=delay;coeff[index]=a;doppler[index]=fd
                    baseband[index]=bb
                    vertices[(slice(0,n),*index)]=vv[1:-1]
                    interactions[(slice(0,n),*index)]=[flags[int(i)] for i in ii]
                    objects[(slice(0,n),*index)]=oo
        scene.last_diagnostics=dict(path_solver=method,candidate_count=candidates,
            passband_coefficient_source=('direct_complex64_field' if direct_passband is not None else 'carrier_removed_baseband'),
            phase_export_calculation='math_atan2_float64',phase_blender_storage='binary32_radians',
            valid_element_paths=int(valid.sum()),synthetic_array_requested=bool(synthetic_array),
            diffraction_semantics='DiffeRT native edge eligibility and UTD; Sionna edge/lit switches do not map',
            diffraction_geometry=os.environ.get('DIFFERT_DIFFRACTION_GEOMETRY','validated'),
            diffraction_validation=getattr(visibility,'diffraction_stats',{}),
            transmission_semantics='DiffeRT thin slabs; not volumetric refraction',
            specular_visibility='float64_unshifted_endpoint_planes',
            segment_length_profile=segment_profile(),
            minimum_segment_length_m=MINIMUM_M if segment_profile()==SHARED_PROFILE else float(np.sqrt(10*np.finfo(np.float32).eps)),
            minimum_segment_comparison='squared_length_greater_than_or_equal_minimum_squared',
            other_interaction_visibility='native_differt',
            visibility_segments_checked=visibility.segments_checked,
            candidate_limit_per_source=int(max_num_paths_per_src) if method=='sbr' else None)
        return BridgePaths(vertices,interactions,objects,valid,tau,coeff,doppler,tp,rp,baseband)


class MapResult:
    def __init__(self,centers,gain,power,noise):
        self.cell_centers=centers;self.path_gain=gain
        self.rss=gain*np.asarray(power).reshape((-1,)+(1,)*(gain.ndim-1))
        self.sinr=self.rss/np.maximum(np.sum(self.rss,axis=0,keepdims=True)-self.rss+noise,1e-300)
    def tx_association(self,metric='path_gain'):
        values=getattr(self,metric)
        return np.where(np.max(values,axis=0)>0,np.argmax(values,axis=0),-1)


class RadioMapSolver:
    def __call__(self,scene,center=None,orientation=(0,0,0),size=None,cell_size=None,
                 measurement_surface=None,samples_per_tx=100000,**kwargs):
        if scene.bandwidth<=0 or scene.temperature<=0: raise ValueError('Positive bandwidth and temperature are required')
        if measurement_surface is not None:
            centers=np.asarray(measurement_surface.vertices)[np.asarray(measurement_surface.triangles)].mean(axis=1)
        else:
            nx,ny=[int(math.ceil(float(a)/float(b))) for a,b in zip(size,cell_size)]
            if nx<1 or ny<1: raise ValueError('Map dimensions must be positive')
            x=(np.arange(nx)-(nx-1)/2)*cell_size[0];y=(np.arange(ny)-(ny-1)/2)*cell_size[1]
            xx,yy=np.meshgrid(x,y)
            local=np.stack([xx,yy,np.zeros_like(xx)],axis=-1)
            centers=local@np.asarray(plane_basis(orientation))+np.asarray(center)
        flat=centers.reshape(-1,3)
        gain=np.zeros((len(scene.transmitters),len(flat)))
        saved_rx,saved_array=scene.receivers,scene.rx_array
        try:
            scene.rx_array=PlanarArray()
            for start in range(0,len(flat),32):
                points=flat[start:start+32]
                scene.receivers={str(i):Receiver(str(i),p) for i,p in enumerate(points)}
                paths=PathSolver()(scene,samples_per_src=samples_per_tx,**kwargs)
                p=np.abs(paths.a[0]+1j*paths.a[1])**2
                # [rx,rx port,tx,tx port,path] -> equal-power incoherent TX ports.
                g=p.sum(axis=-1).mean(axis=(1,3)).T
                gain[:,start:start+len(points)]=g
        finally:
            scene.receivers,scene.rx_array=saved_rx,saved_array
        gain=gain.reshape((len(scene.transmitters),)+centers.shape[:-1])
        power=[10**((t.power_dbm-30)/10) for t in scene.transmitters.values()]
        return MapResult(centers,gain,power,1.380649e-23*scene.temperature*scene.bandwidth)

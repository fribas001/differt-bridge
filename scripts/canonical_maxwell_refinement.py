"""Optional full-wave 2D wedge field beside native ray exports.

This is a coupled transmission BIE solve, not a modified UTD coefficient or a
general 3D ray-tracer patch. It consumes explicit line-source benchmark geometry,
never measured/reference fields. Unsupported scenes fail before any solve.
"""
import hashlib,json,time
from pathlib import Path
import numpy as np
from wedge_bem_reference import WedgeBEM
from ray_wedge2d import fixture,C,EPS0
from refinement_cases import DOMAIN

class UnsupportedScene(ValueError):pass

def validate(case):
    def require(condition,message):
        if not condition:raise UnsupportedScene(message)
    require(case.get('maxwell_domain')==DOMAIN,'Explicit 2D line-source solid-quadrant domain required; 3D point-source exports cannot be refined by this solver')
    require(case.get('frequency_hz')==C,'This normalized benchmark requires wavelength = 1 m')
    pol=case.get('study',{}).get('polarization')
    require(pol in ('Ez','Hz'),'Only broadside Ez/Hz are supported')
    expected_pol='V' if pol=='Ez' else 'H'
    require(case.get('tx_pol')==case.get('rx_pol')==expected_pol,'Cross polarization is unsupported')
    require(case.get('pattern')=='iso','Only isotropic canonical ports are supported')
    template=fixture([-2.,1.],[-3.,-1.],4-2j,pol)
    meshes=case.get('meshes',[])
    require(len(meshes)==1,'Additional obstacles/materials are unsupported; no geometry is silently dropped')
    m=meshes[0];t=template['meshes'][0]
    require(m.get('triangles')==t['triangles'] and m.get('material')==t['material'],'Canonical triangle topology/material required')
    v=np.asarray(m.get('vertices',[]),dtype=float);tv=np.asarray(t['vertices'])
    require(v.shape==tv.shape and np.isfinite(v).all() and np.allclose(v,tv,rtol=0,atol=1e-12),'Modified, finite or rotated faces are outside this canonical domain')
    require(case.get('canonical_edges')==template['canonical_edges'],'Canonical edge description required')
    require(case.get('physics',{}).get('rotation')==np.eye(3).tolist(),'Rotated/skew domain is unsupported')
    require(case.get('physics',{}).get('opening_deg')==90,'Only the right-angle solid wedge is supported')
    material=case['material'];eps=complex(material['relative_permittivity'],-material['conductivity']/(2*np.pi*C*EPS0))
    require(np.isfinite(eps) and 1<eps.real<=10 and -10<=eps.imag<=-.1,'Only the declared lossy validation envelope 1 < Re(eps) <= 10, 0.1 <= loss <= 10 is supported')
    require(material.get('thickness')==10. and material.get('scattering_coefficient')==0,'Finite slabs and diffuse materials are unsupported; thickness=10 is the ray benchmark halfspace proxy')
    require(len(case.get('receivers',[]))>0,'At least one receiver is required')
    ports=np.asarray([case['tx'],*case['receivers']],dtype=float)
    require(ports.ndim==2 and ports.shape[1]==3 and np.isfinite(ports).all(),'Invalid ports')
    require(np.max(abs(ports[:,2]))<1e-12,'Skew or non-coplanar 3D ports are unsupported')
    require(np.all(np.linalg.norm(ports[:,:2],axis=1)>=.75) and np.max(abs(ports))<=5,'Ports must lie 0.75 wavelengths from the corner and inside the validated 5-wavelength box')
    require(np.all((ports[:,0]<0)|(ports[:,1]<0)),'Ports must be strictly outside the solid quadrant')
    require(np.all(np.linalg.norm(ports[1:]-ports[0],axis=1)>1e-5),'Coincident ports are unsupported')
    solver=case['solver']
    require(all(solver.get(k) is True for k in ('los','specular_reflection','diffraction','diffraction_lit_region')),'The reference domain requires the complete external field')
    require(not any(solver.get(k,False) for k in ('diffuse_reflection','refraction','edge_diffraction','synthetic_array')),'Unsupported interaction/array setting')
    require(solver.get('max_depth')==1,'Mixed/multiple-edge interactions are unsupported')
    return eps,pol

class CanonicalRefiner:
    def __init__(self,panels=24,tail=5.):
        if panels not in (16,24,36,48):raise ValueError('Use a declared validation resolution')
        self.panels=panels;self.tail=tail;self._solver=None
    def solve(self,sources,receivers,epsilon,polarization):
        """Internal validated-domain numerical solve; no field/reference argument."""
        if self._solver is None:self._solver=WedgeBEM(self.panels,6.,self.tail)
        start=time.perf_counter()
        f,meta=self._solver.solve(sources,receivers,epsilon,polarization)
        r,reverse=self._solver.solve(receivers,sources,epsilon,polarization)
        # Constant collocation is not exactly reciprocal. Project its small
        # discretization bias onto the known Lorentz symmetry, without conjugation.
        # Both raw directions remain in the receipt; this is not a fitted correction.
        u=.5*(f+r.T)
        detail=dict(**meta,mode='fullwave_2d',reciprocity_projection='ordinary transpose average of independently solved source/probe directions',raw_reciprocity_rms=float(np.linalg.norm(f-r.T)/np.linalg.norm(u)),reverse_linear_residual=reverse['linear_residual'],elapsed_seconds=time.perf_counter()-start)
        return u,f,r.T,detail

def refine_cases(cases,panels=24):
    # Validate the entire batch before computing or creating output.
    validated=[validate(c) for c in cases];groups={}
    for c,(eps,pol) in zip(cases,validated):
        key=(eps,pol,json.dumps(c['receivers']))
        groups.setdefault(key,[]).append(c)
    solver=CanonicalRefiner(panels);results=[]
    pair=lambda a:np.stack([a.real,a.imag],axis=-1).tolist()
    for (eps,pol,_),rows in groups.items():
        sources=np.asarray([c['tx'][:2] for c in rows]);receivers=np.asarray(rows[0]['receivers'])[:,:2]
        print('REFINE',rows[0]['study']['material'],pol,panels,flush=True)
        u,f,r,meta=solver.solve(sources,receivers,eps,pol)
        results.append(dict(**meta,name=rows[0]['study']['material']+'_'+pol,case_names=[c['name'] for c in rows],sources=sources.tolist(),receivers=receivers.tolist(),field=pair(u),raw_forward=pair(f),raw_reverse=pair(r)))
    return dict(mode='fullwave_2d',native_ray_exports_modified=False,panels=panels,scope='Explicit solid right-angle wedge, 2D line sources only; a separate full-wave field, not an upstream ray model',source_sha256={n:hashlib.sha256(Path(__file__).with_name(n).read_bytes()).hexdigest() for n in ('canonical_maxwell_refinement.py','wedge_bem_reference.py')},results=results)

if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('manifest',type=Path);ap.add_argument('output',type=Path);ap.add_argument('--panels',type=int,default=24);args=ap.parse_args()
    cases=json.loads(args.manifest.read_text())['cases'];data=refine_cases(cases,args.panels)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(data,indent=2,allow_nan=False))

"""Optional coupled 3D dielectric wedge field, separate from both ray exports.

This solves a declared infinite solid quadrant. No FEM/reference data, fitted
parameters or completed-channel averaging are used. Every scene is validated
before any solve or output: additional obstacles are never silently removed.
"""
import argparse,hashlib,json,time
from pathlib import Path
import numpy as np
from numpy.polynomial.legendre import leggauss
from scipy.constants import epsilon_0
from dielectric3d_bem import VectorWedgeBEM

C=299792458.;K=2*np.pi
DOMAIN=dict(geometry='infinite_solid_dielectric_quadrant',source='electric_point_dipole',dimensions=3,edge_axis='z',wavelength_m=1.)
ORIENT={'x':[0.,np.pi/2,0.],'y':[np.pi/2,np.pi/2,0.],'z':[0.,0.,0.]}
class UnsupportedScene(ValueError):pass

def validate(case):
    from diffraction_cases import wedge
    def require(ok,message):
        if not ok:raise UnsupportedScene('Unsupported dielectric 3D refinement: '+message)
    require(case.get('maxwell_domain')==DOMAIN,'explicit infinite solid-wedge point-source domain required')
    require(case.get('frequency_hz')==C,'wavelength must be 1 m')
    require(case.get('meshes')==[wedge(length=160,height=160)],'canonical faces only; all extra or changed obstacles are rejected')
    require(case.get('canonical_edges')==[dict(origin=[0.,0.,0.],direction=[0.,0.,1.],half_length=160.)],'canonical edge required')
    require(case.get('pattern')=='dipole' and case.get('tx_pol')==case.get('rx_pol')=='V','single short electric dipoles required')
    require(case.get('array_cols',1)==case.get('array_rows',1)==1,'arrays unsupported')
    def axis(key):
        orientation=case.get(key,[0.,0.,0.]);found=[name for name,v in ORIENT.items() if np.array_equal(orientation,v)]
        require(len(found)==1,'only declared x/y/z dipole orientations supported');return 'xyz'.index(found[0])
    txaxis,rxaxis=axis('tx_orientation'),axis('rx_orientation')
    m=case.get('material',{});eps=complex(m.get('relative_permittivity',np.nan),-m.get('conductivity',np.nan)/(2*np.pi*C*epsilon_0))
    require(np.isfinite(eps) and 2.<=eps.real<=8. and .25<=-eps.imag<=1.5,'validated material envelope: 2≤Re ε≤8, 0.25≤loss≤1.5')
    require(m.get('thickness')==10. and m.get('scattering_coefficient')==0.,'10-wavelength slab proxy, no diffuse material; solid volume is the explicit refined model')
    receivers=case.get('receivers',[]);require(len(receivers)>0,'at least one receiver required')
    p=np.asarray([case.get('tx'),*receivers],float);require(p.ndim==2 and p.shape[1]==3 and np.isfinite(p).all(),'finite 3D ports required')
    rho=np.linalg.norm(p[:,:2],axis=1);phi=(np.arctan2(p[:,1],p[:,0])-np.pi/2)%(2*np.pi)
    require(np.all((rho>=1.-1e-7)&(rho<=2.5+1e-7)) and np.all((phi>=np.deg2rad(4.99))&(phi<=np.deg2rad(265.01))),'ports outside wedge, radii 1–2.5 λ and angles 5–265 degrees')
    require(np.max(abs(p[:,2]))<=3.000001 and np.max(abs(p[1:,2]-p[0,2]))<=3.000001,'absolute height and height difference at most 3 λ')
    require(np.all(np.linalg.norm(p[1:]-p[0],axis=1)>.25),'separated source and receiver required')
    solver=case.get('solver',{});require(solver.get('max_depth')==1,'single wedge only')
    require(all(solver.get(k) is True for k in ('los','specular_reflection','diffraction','diffraction_lit_region')),'complete exterior field required')
    require(not any(solver.get(k,False) for k in ('diffuse_reflection','refraction','edge_diffraction','synthetic_array')),'unsupported ray/array setting')
    return eps,txaxis,rxaxis

def spectral_quadrature(order=8,contour=.5,qmax=24.):
    if order not in (6,8,12) or not .3<=contour<=.8 or qmax not in (24.,28.,32.):raise ValueError('Undeclared quadrature setting')
    t,w=leggauss(order);nodes=[];weights=[]
    for left,right in zip([0.,2.,4.,5.5,7.,9.,12.,16.],[2.,4.,5.5,7.,9.,12.,16.,qmax]):
        u=left+(t+1)*(right-left)/2;nodes.extend(u+1j*contour*np.tanh(u/contour));weights.extend(w*(right-left)/2*(1+1j/np.cosh(u/contour)**2))
    return np.array(nodes),np.array(weights)

def electric_free(source,receiver):
    d=np.asarray(receiver)-source;distance=np.linalg.norm(d)
    if distance<=0:raise ValueError('Coincident dipole singularity')
    n=d/distance;g=np.exp(-1j*K*distance)/(4*np.pi*distance);q=1j/(K*distance)+1/(K*distance)**2
    return g*((1-q)*np.eye(3)+(-1+3*q)*np.outer(n,n))

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def pair(a):return np.stack([a.real,a.imag],axis=-1).tolist()

class Refiner:
    def __init__(self,panels=32,order=8,contour=.5,qmax=24.):
        if panels not in (16,24,32,48):raise ValueError('Unsupported resolution')
        spectral_quadrature(order,contour,qmax)
        self.panels=panels;self.order=order;self.contour=contour;self.qmax=qmax
    def solve(self,epsilon,sources,receivers,checkpoint):
        params=dict(epsilon=pair(np.array(epsilon)),sources=sources,receivers=receivers,panels=self.panels,order=self.order,contour=self.contour,qmax=self.qmax,
                    source_hashes={n:digest(Path(__file__).with_name(n)) for n in ('dielectric3d_refinement.py','dielectric3d_bem.py')})
        checkpoint.mkdir(parents=True,exist_ok=True);config=checkpoint/'config.json'
        if config.exists() and json.loads(config.read_text())!=params:raise ValueError('Checkpoint inputs or solver source changed')
        if not config.exists():config.write_text(json.dumps(params,indent=2),encoding='utf-8')
        model=VectorWedgeBEM(self.panels);nodes,weights=spectral_quadrature(self.order,self.contour,self.qmax)
        total=np.zeros((len(receivers),3,3*len(sources)),complex);metadata=[];start=time.perf_counter();calculated=0
        for i,(q,w) in enumerate(zip(nodes,weights)):
            file=checkpoint/f'mode_{i:03d}.npz';meta=file.with_suffix('.json')
            if file.exists() and meta.exists():
                detail=json.loads(meta.read_text());assert digest(file)==detail['field_sha256'];field=np.load(file)['field']
            else:
                field,detail=model.solve(q,epsilon,sources,receivers,(0,1,2))
                if not np.isfinite(field).all() or detail['linear_residual']>=1e-9:raise ArithmeticError('Unconverged Maxwell boundary solve: '+str(detail))
                np.savez_compressed(file,field=field);detail['field_sha256']=digest(file);meta.write_text(json.dumps(detail,indent=2),encoding='utf-8');calculated+=1
            metadata.append(detail)
            for si,source in enumerate(sources):
                dz=np.asarray(receivers)[:,2]-source[2]
                for rx in range(3):
                    for tx in range(3):total[:,rx,si*3+tx]+=w*field[:,rx,si*3+tx]*(1j*np.sin(q*dz) if (rx==2)!=(tx==2) else np.cos(q*dz))/np.pi
            print('DIELECTRIC3D',self.panels,epsilon,'MODE',i+1,'/',len(nodes),flush=True)
        for si,source in enumerate(sources):
            for ri,receiver in enumerate(receivers):
                # Cartesian grouping may create unrequested coincident pairs.
                # User-requested coincident ports have already been rejected.
                if np.linalg.norm(np.asarray(receiver)-source)>0:total[ri,:,si*3:si*3+3]+=electric_free(source,receiver)
        total*=1.5
        detail=dict(**params,nodes=len(nodes),newly_calculated_modes=calculated,maximum_linear_residual=max(m['linear_residual'] for m in metadata),elapsed_seconds=time.perf_counter()-start,normalization='1.5 lambda times electric dyadic; only requested noncoincident channels exposed')
        (checkpoint/'receipt.json').write_text(json.dumps(detail,indent=2),encoding='utf-8');return total,detail

def refine(cases,checkpoint,panels=32,order=8,contour=.5,qmax=24.):
    validated=[validate(c) for c in cases] # Whole-batch guard before output/computation.
    groups={}
    for c,(eps,tx,rx) in zip(cases,validated):groups.setdefault(eps,[]).append((c,tx,rx))
    solver=Refiner(panels,order,contour,qmax);results=[];details=[]
    for gi,(eps,rows) in enumerate(groups.items()):
        sources=list(dict.fromkeys(tuple(c['tx']) for c,_,_ in rows));receivers=list(dict.fromkeys(tuple(r) for c,_,_ in rows for r in c['receivers']))
        sources=[list(s) for s in sources];receivers=[list(r) for r in receivers]
        field,info=solver.solve(eps,sources,receivers,checkpoint/f'group_{gi:02d}');details.append(info)
        for c,tx,rx in rows:
            si=sources.index(c['tx']);values=np.array([field[receivers.index(r),rx,si*3+tx] for r in c['receivers']])
            results.append(dict(name=c['name'],field=pair(values)))
    return dict(status='completed',mode='optional_3d_dielectric_fullwave',domain=DOMAIN,reference_used=False,native_exports_modified=False,shared_solver=True,
                scope='Coupled full-wave solid infinite dielectric quadrant, declared 3D point dipoles. Separate companion field, not a native UTD patch or arbitrary-scene correction.',
                panels=panels,order=order,source_hashes={n:digest(Path(__file__).with_name(n)) for n in ('dielectric3d_refinement.py','dielectric3d_bem.py')},groups=details,results=results)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('manifest',type=Path);ap.add_argument('output',type=Path);ap.add_argument('--panels',type=int,default=32);ap.add_argument('--order',type=int,default=8);a=ap.parse_args()
    cases=json.loads(a.manifest.read_text(encoding='utf-8'))['cases'];result=refine(cases,a.output.parent/(a.output.stem+'_modes'),a.panels,a.order)
    a.output.write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')

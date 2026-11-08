"""Fourier synthesis of a genuine 3D point-dipole dielectric Maxwell field."""
import argparse,hashlib,json,time
from pathlib import Path
import numpy as np
from numpy.polynomial.legendre import leggauss
from maxwell3d_pec_reference import free_dyadic
from dielectric3d_bem import VectorWedgeBEM
from dielectric3d_fem import VectorWedgeFEM

def quadrature(order=6,height=.5,qmax=24.):
    knots=[0.,2.,4.,5.5,7.,9.,12.,16.,qmax];t,w=leggauss(order);nodes=[];weights=[]
    for a,b in zip(knots[:-1],knots[1:]):
        u=a+(t+1)*(b-a)/2;q=u+1j*height*np.tanh(u/height)
        dq=1+1j/np.cosh(u/height)**2
        nodes.extend(q);weights.extend(w*(b-a)/2*dq)
    return np.array(nodes),np.array(weights)

def campaign():
    from native3d_cases import point
    sources=[point(60.,1.5,0),point(150.,1.5,0)]
    angles=sorted(set([*np.arange(5.,270.,10.),119.99,120.,120.01,209.99,210.,210.01,239.99,240.,240.01]))
    receivers=[point(a,2.,z) for z in (0.,1.,3.) for a in angles]
    return dict(sources=sources,receivers=receivers,axes=[0,1,2],angles=angles,heights=[0.,1.,3.])

def run(output,method='bem',resolution=16,epsilon=5.24-.632143019j,order=6,contour=.5,qmax=24.,core=3.,tail=3.,inner=2.5,pml=1.5,boundary='dielectric',ports=None):
    output.mkdir(parents=True,exist_ok=True);ports=campaign() if ports is None else ports;sources=ports['sources'];receivers=ports['receivers'];axes=ports['axes']
    params=dict(method=method,resolution=resolution,epsilon=[epsilon.real,epsilon.imag],order=order,contour=contour,qmax=qmax,core=core,tail=tail,inner=inner,pml=pml,boundary=boundary,ports=ports)
    scripts=Path(__file__).parent;params['source_hashes']={name:hashlib.sha256((scripts/name).read_bytes()).hexdigest() for name in ['dielectric3d_synthesis.py','dielectric3d_'+method+'.py']}
    config=output/'config.json'
    if config.exists():assert json.loads(config.read_text())==params,'Checkpoint configuration changed'
    else:config.write_text(json.dumps(params,indent=2),encoding='utf-8')
    model=VectorWedgeBEM(resolution,core,tail) if method=='bem' else VectorWedgeFEM(resolution,inner,pml)
    nodes,weights=quadrature(order,contour,qmax);total=np.zeros((len(receivers),3,len(sources)*len(axes)),complex);metadata=[];start=time.perf_counter()
    for i,(q,w) in enumerate(zip(nodes,weights)):
        file=output/f'mode_{i:03d}.npz';meta=output/f'mode_{i:03d}.json'
        if file.exists() and meta.exists():field=np.load(file)['field'];detail=json.loads(meta.read_text())
        else:
            field,detail=model.solve(q,epsilon,sources,receivers,axes,**({'boundary':boundary} if method=='bem' else {}))
            assert np.isfinite(field).all() and detail['linear_residual']<1e-9,detail
            np.savez_compressed(file,field=field);detail['field_sha256']=hashlib.sha256(file.read_bytes()).hexdigest();meta.write_text(json.dumps(detail,indent=2),encoding='utf-8')
        assert hashlib.sha256(file.read_bytes()).hexdigest()==detail['field_sha256'];metadata.append(detail)
        for si,s in enumerate(sources):
            dz=np.array(receivers)[:,2]-s[2]
            for ai,axis in enumerate(axes):
                col=si*len(axes)+ai
                for rx_axis in range(3):
                    odd=(axis==2)!=(rx_axis==2)
                    phase=1j*np.sin(q*dz) if odd else np.cos(q*dz)
                    total[:,rx_axis,col]+=w*phase*field[:,rx_axis,col]/np.pi
        print(method,resolution,'MODE',i+1,'/',len(nodes),'seconds',round(detail['seconds'],2),flush=True)
    for si,s in enumerate(sources):
        for j,r in enumerate(receivers):
            g=free_dyadic(s,r)
            for ai,axis in enumerate(axes):total[j,:,si*len(axes)+ai]+=g[:,axis]
    total*=1.5 # normalized short-dipole transmitter and receiver gains, lambda=1.
    result=dict(status='completed',**params,nodes=len(nodes),linear_residual=max(m['linear_residual'] for m in metadata),elapsed_seconds=time.perf_counter()-start,field=np.stack([total.real,total.imag],axis=-1).tolist(),normalization='1.5 lambda times full electric Green dyadic; all longitudinal wavenumbers, propagating and evanescent; free term analytic',shape=list(total.shape))
    (output/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8');return result

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('output',type=Path);ap.add_argument('--method',choices=['bem','fem'],default='bem');ap.add_argument('--resolution',type=int,default=16);ap.add_argument('--epsilon',type=float,default=5.24);ap.add_argument('--loss',type=float,default=.632143019);ap.add_argument('--order',type=int,default=6);ap.add_argument('--contour',type=float,default=.5);ap.add_argument('--qmax',type=float,default=24.);ap.add_argument('--core',type=float,default=3.);ap.add_argument('--tail',type=float,default=3.);ap.add_argument('--inner',type=float,default=2.5);ap.add_argument('--pml',type=float,default=1.5);ap.add_argument('--boundary',default='dielectric');a=ap.parse_args()
    run(a.output,a.method,a.resolution,complex(a.epsilon,-a.loss),a.order,a.contour,a.qmax,a.core,a.tail,a.inner,a.pml,a.boundary)

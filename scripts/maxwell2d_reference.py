"""Independent 2D Maxwell reference: conservative FDFD with coordinate-stretched PML.

No ray tracer, UTD formula, fitted coefficient or engine-produced field is used.
Exp(+i omega t); passive epsilon has negative imaginary part. Units: vacuum wavelength.
Ez: div(grad u)+k^2 epsilon u=-delta. Hz: div(epsilon^-1 grad u)+k^2 u=-delta.
The discrete flux operator is complex symmetric. Sources and probes use the same
bilinear weights, preserving the discrete reciprocity theorem without averaging.
"""
import argparse,json,time
from pathlib import Path
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import splu
from scipy.special import hankel2,jv

def free_green(source,receiver,k=2*np.pi):
    return -.25j*hankel2(0,k*np.linalg.norm(np.asarray(receiver)-source))

def pec_green(source,receiver,polarization='Ez',terms=120,k=2*np.pi):
    """Independent separation-of-variables Green function, exterior angle 3pi/2."""
    def polar(p):return np.linalg.norm(p),(np.arctan2(p[1],p[0])-np.pi/2)%(2*np.pi)
    rs,ps=polar(source);rr,pr=polar(receiver);alpha=1.5*np.pi
    assert 0<ps<alpha and 0<pr<alpha and abs(rs-rr)>1e-5
    m=np.arange(1,terms+1);nu=m*np.pi/alpha
    radial=jv(nu,k*min(rs,rr))*hankel2(nu,k*max(rs,rr))
    if polarization=='Ez':angular=np.sin(nu*ps)*np.sin(nu*pr)
    else:angular=np.cos(nu*ps)*np.cos(nu*pr)
    value=-1j*np.pi/alpha*np.sum(angular*radial)
    if polarization=='Hz':value+=-1j*np.pi/(2*alpha)*jv(0,k*min(rs,rr))*hankel2(0,k*max(rs,rr))
    assert np.isfinite(value)
    return value

class Maxwell2D:
    def __init__(self,ppw=24,inner=5.,pml=1.5,epsilon=4-2j,polarization='Ez',geometry='wedge',strength=4.):
        started=time.perf_counter();self.h=h=1./ppw;self.k=2*np.pi
        size=round(2*(inner+pml)*ppw);size+=size%2;self.size=size
        self.x=(np.arange(size)-(size-1)/2)*h;self.extent=size*h/2
        xx,yy=np.meshgrid(self.x,self.x,indexing='ij')
        if geometry in ('wedge','pec'):material=(xx>0)&(yy>0)
        elif geometry=='halfspace':material=xx>0
        elif geometry=='slabs':material=((xx>0)&(yy>0)&((xx<.5)|(yy<.5)))
        elif geometry=='free':material=np.zeros_like(xx,dtype=bool)
        else:raise ValueError(geometry)
        eps=np.where(material,epsilon,1.).astype(complex)
        a=np.ones_like(eps) if polarization=='Ez' else 1/eps
        b=eps if polarization=='Ez' else np.ones_like(eps)
        active=~material if geometry=='pec' else np.ones_like(material)
        ids=np.full((size,size),-1,int);ids[active]=np.arange(active.sum());self.ids=ids
        def stretch(x):return 1-1j*strength*np.maximum((abs(x)-inner)/pml,0)**3
        s=stretch(self.x);sf=stretch((self.x[:-1]+self.x[1:])/2)
        diag=(self.k*h)**2*b*s[:,None]*s[None,:]
        rows=[];cols=[];values=[]
        for axis in (0,1):
            low=[slice(None),slice(None)];high=low.copy();low[axis]=slice(None,-1);high[axis]=slice(1,None)
            low=tuple(low);high=tuple(high)
            w=2*a[low]*a[high]/(a[low]+a[high])
            w*=s[None,:]/sf[:,None] if axis==0 else s[:,None]/sf[None,:]
            il,ih=ids[low],ids[high];both=(il>=0)&(ih>=0)
            wl=np.where(both,w,0.);wh=wl.copy()
            if geometry=='pec' and polarization=='Ez':
                # Dirichlet boundary lies halfway between cell centres.
                wl=np.where((il>=0)&(ih<0),2*w,wl);wh=np.where((ih>=0)&(il<0),2*w,wh)
            diag[low]-=wl;diag[high]-=wh
            rows.extend([il[both],ih[both]]);cols.extend([ih[both],il[both]]);values.extend([w[both],w[both]])
        # Homogeneous Dirichlet termination beyond the absorbing layer, at face distance h/2.
        for axis in (0,1):
            for end in (0,-1):
                sel=[slice(None),slice(None)];sel[axis]=end;sel=tuple(sel)
                ratio=s/stretch(self.extent)
                diag[sel]-=2*a[sel]*ratio
        rows.append(ids[active]);cols.append(ids[active]);values.append(diag[active])
        A=coo_matrix((np.concatenate(values),(np.concatenate(rows),np.concatenate(cols))),shape=(active.sum(),active.sum())).tocsc()
        self.matrix=A
        symmetry=A-A.T;self.symmetry_error=float(np.max(abs(symmetry.data),initial=0.))
        self.lu=splu(A,permc_spec='MMD_AT_PLUS_A')
        self.metadata=dict(ppw=ppw,inner=inner,pml=pml,strength=strength,epsilon=[epsilon.real,epsilon.imag],polarization=polarization,geometry=geometry,unknowns=int(active.sum()),matrix_symmetry_error=self.symmetry_error,factor_seconds=time.perf_counter()-started,lu_nonzeros=int(self.lu.L.nnz+self.lu.U.nnz))

    def weights(self,p):
        q=(np.asarray(p)-self.x[0])/self.h;i=np.floor(q).astype(int);f=q-i
        ids=[];weights=[]
        for dx in (0,1):
            for dy in (0,1):
                n=self.ids[i[0]+dx,i[1]+dy]
                if n<0:raise ValueError('Source/probe interpolation overlaps PEC')
                ids.append(n);weights.append((f[0] if dx else 1-f[0])*(f[1] if dy else 1-f[1]))
        return np.array(ids),np.array(weights)

    def solve(self,sources,receivers):
        rhs=np.zeros((self.matrix.shape[0],len(sources)),complex)
        for j,p in enumerate(sources):
            ids,w=self.weights(p);rhs[ids,j]-=w
        u=self.lu.solve(rhs);res=self.matrix@u-rhs
        values=[]
        for p in receivers:
            ids,w=self.weights(p);values.append(w@u[ids])
        return np.asarray(values).T,float(np.linalg.norm(res)/np.linalg.norm(rhs))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('output',type=Path);ap.add_argument('--ppw',type=int,default=20);ap.add_argument('--geometry',default='free');ap.add_argument('--polarization',default='Ez');ap.add_argument('--inner',type=float,default=5);ap.add_argument('--pml',type=float,default=1.5);args=ap.parse_args()
    source=[-2.598076211,1.5];angles=np.deg2rad(np.array([40,80,119,121,160,200,239,241,260])+90)
    receivers=np.stack([4*np.cos(angles),4*np.sin(angles)],axis=1)
    solver=Maxwell2D(args.ppw,inner=args.inner,pml=args.pml,geometry=args.geometry,polarization=args.polarization)
    values,residual=solver.solve([source],receivers);values=values[0]
    refs=[free_green(source,p) if args.geometry=='free' else pec_green(source,p,args.polarization) if args.geometry=='pec' else None for p in receivers]
    result=dict(**solver.metadata,linear_residual=residual,source=source,receivers=receivers.tolist(),field=[[z.real,z.imag] for z in values],reference=[[z.real,z.imag] if z is not None else None for z in refs],relative_error=[abs(v-r)/abs(r) if r is not None else None for v,r in zip(values,refs)])
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('field','reference','receivers')},indent=2),flush=True)

if __name__=='__main__':main()

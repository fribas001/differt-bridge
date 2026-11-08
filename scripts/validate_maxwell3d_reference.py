"""Independent checks for the 3D PEC point-dipole Maxwell reference."""
import json,time
from pathlib import Path
import numpy as np
from scipy.integrate import quad_vec
from scipy.special import ive,kve
from maxwell3d_pec_reference import wedge_green,electric_z_column,free_dyadic,polar
from maxwell2d_reference import pec_green

def spectral(source,receiver,k=2*np.pi-.3j,terms=100,qmax=40.,tol=2e-10):
    """Independent Fourier synthesis of separated angular Bessel modes.

    Integrates every longitudinal wavenumber, including evanescent modes;
    (1-q^2/k^2) is the Maxwell zz projector. Small uniform absorption keeps
    the numerical contour clear of the light-line branch point. Same k is
    used by the Sommerfeld comparator. This is a true 3D point Green field.
    """
    rs,ps=polar(source);rr,pr=polar(receiver);dz=receiver[2]-source[2]
    alpha=1.5*np.pi;nu=np.arange(1,terms+1)*np.pi/alpha
    angular=np.sin(nu*ps)*np.sin(nu*pr)
    def f(q):
        kap=np.sqrt(complex(k*k-q*q))
        if kap.imag>0:kap=-kap
        v=1j*kap;a=v*min(rs,rr);b=v*max(rs,rr)
        radial=ive(nu,a)*kve(nu,b)*np.exp(abs(a.real)-b)
        g2=2/alpha*np.sum(angular*radial)
        return np.cos(q*dz)*(1-q*q/(k*k))*g2/np.pi
    value,error=quad_vec(f,0.,qmax,epsabs=tol,epsrel=tol,points=[float(k.real)])
    return value,error

def run():
    start=time.perf_counter();s=np.array([-2.598076,1.5,0.]);out=dict(controls=[])
    def add(name,value,limit,**extra):
        out['controls'].append(dict(name=name,error=float(value),limit=limit,passed=bool(value<limit),**extra));print(name,value,flush=True)
    errs=[]
    for pol,bc in [('Ez','dirichlet'),('Hz','neumann')]:
        for a in np.deg2rad([110,170,210,260,310,350]):
            r=[4*np.cos(a),4*np.sin(a),0.]
            a1=wedge_green(s,r,component='line',boundary=bc)
            a2=pec_green(s[:2],r[:2],pol)
            errs.append(abs(a1-a2)/max(abs(a2),1e-10))
    add('2D eigenfunction limit / both scalar boundaries',max(errs),2e-8,samples=len(errs))
    for dz in (0.,2.,8.):
        r=np.array([-1.,-np.sqrt(15.),dz]);k=2*np.pi-.3j
        a,e=spectral(s,r,k,terms=100);b,_=spectral(s,r,k,terms=140,qmax=55.,tol=2e-11)
        c=wedge_green(s,r,k=k)
        add(f'3D Fourier-Bessel Maxwell zz / dz={dz}',abs(c-b)/abs(b),2e-7,reference=[c.real,c.imag],spectral=[b.real,b.imag],spectral_refinement=float(abs(a-b)/abs(b)),quadrature_estimate=float(e))
    # alpha=pi is a PEC plane: exact dyadic method of images.
    for dz in (0.,2.,8.):
        r=np.array([-1.,-3.,dz]);image=s.copy();image[0]*=-1
        v=electric_z_column(s,r,alpha=np.pi)
        ref=(free_dyadic(s,r)-free_dyadic(image,r))[:,2]
        add(f'3D vector PEC plane image / dz={dz}',np.linalg.norm(v-ref)/np.linalg.norm(ref),2e-7)
    points=[np.array([-1.,-3.,2.]),np.array([2.,-3.,8.]),np.array([-3.,2.,1.])]
    for i,r in enumerate(points):
        a=electric_z_column(s,r,h=4e-4);b=electric_z_column(s,r,h=2e-4)
        c=electric_z_column(s,r,h=1e-4,contour=1.1,tolerance=2e-12,limit=55.)
        add(f'vector derivative / contour / tail convergence {i}',max(np.linalg.norm(a-b),np.linalg.norm(b-c))/np.linalg.norm(c),2e-7)
        h=1e-3;div=0j;lap=np.zeros(3,complex)
        for axis in range(3):
            d=np.eye(3)[axis]*h
            low=electric_z_column(s,r-d);high=electric_z_column(s,r+d)
            div+=(high[axis]-low[axis])/(2*h);lap+=(high-2*b+low)/(h*h)
        add(f'3D divergence-free Maxwell field {i}',abs(div)/(2*np.pi*np.linalg.norm(b)),2e-5)
        add(f'3D Helmholtz / curl-curl residual {i}',np.linalg.norm(lap+(2*np.pi)**2*b)/((2*np.pi)**2*np.linalg.norm(b)),2e-5)
        add(f'point-dipole zz reciprocity {i}',abs(wedge_green(s,r)-wedge_green(r,s))/abs(wedge_green(s,r)),2e-10)
    # Tangential E is zero at both faces; approach them from the exterior.
    for r,tangent in [(np.array([-1e-5,2.,3.]),[1,2]),(np.array([2.,-1e-5,3.]),[0,2])]:
        v=electric_z_column(s,r,h=2e-6)
        add('PEC tangential boundary approach',np.linalg.norm(v[tangent])/np.linalg.norm(v),2e-4)
    for center in (120.,240.):
        # Use a non-boundary source for 240; this still tests smoothness.
        def rx(a):a=np.deg2rad(a+90);return [4*np.cos(a),4*np.sin(a),8.]
        vals=[wedge_green(s,rx(center+d)) for d in (-1e-6,0.,1e-6)]
        add(f'3D total-field boundary continuity {center}',max(abs(vals[0]-vals[1]),abs(vals[2]-vals[1]))/abs(vals[1]),2e-5)
    out.update(status='passed' if all(x['passed'] for x in out['controls']) else 'failed',elapsed_seconds=time.perf_counter()-start)
    return out

if __name__=='__main__':
    import sys
    p=Path(sys.argv[1]);p.parent.mkdir(parents=True,exist_ok=True);r=run();p.write_text(json.dumps(r,indent=2),encoding='utf-8')
    if r['status']!='passed':raise SystemExit(1)

"""Independent 2D transmission boundary-integral reference for a right-angle wedge.

Piecewise-constant collocation on its two semi-infinite faces. A smooth complex
coordinate continuation damps the outgoing tail; no ray/UTD data enter the solve.
Exterior: (.5 I - K0) u + S0 q = u_inc.
Interior: (.5 I + Ki) u - alpha Si q = 0, alpha=1 (Ez), epsilon (Hz).
Normals point out of the material. Time dependence is exp(+i omega t).
"""
import argparse,json,time
from functools import lru_cache
import numpy as np
from scipy.linalg import lu_factor,lu_solve
from scipy.special import hankel2
from numpy.polynomial.legendre import leggauss

def green(k,r):return -.25j*hankel2(0,k*r)

class WedgeBEM:
    def __init__(self,panels_per_wavelength=16,core=6.,tail=5.,stretch=2.,quadrature=16):
        self.k=2*np.pi;h=1/panels_per_wavelength
        # Extra geometric refinement at the corner, shared by the two faces.
        near=np.geomspace(h/128,h,8)
        physical=np.unique(np.r_[0.,near,np.arange(h,core+tail+h/2,h)])
        contour=physical-1j*stretch*np.maximum(physical-core,0.)**3/(3*tail**2)
        a,b=contour[:-1],contour[1:];mid=(a+b)/2;length=b-a
        self.points=np.r_[np.stack([mid,np.zeros_like(mid)],axis=1),np.stack([np.zeros_like(mid),mid],axis=1)]
        self.length=np.tile(length,2);self.normals=np.repeat([[0.,-1.],[-1.,0.]],len(mid),axis=0)
        self.tangents=np.repeat([[1.,0.],[0.,1.]],len(mid),axis=0)
        t,w=leggauss(quadrature);self.t=t/2;self.w=w/2
        self.samples=self.points[:,None,:]+self.length[:,None,None]*self.t[None,:,None]*self.tangents[:,None,:]
        self.S0,self.K0=self.operators(self.points,self.k,diagonal=True)
        self.metadata=dict(method='constant-panel transmission BIE with complex contour tail',panels_per_wavelength=panels_per_wavelength,core=core,tail=tail,stretch=stretch,quadrature=quadrature,panels=len(self.points))

    def operators(self,targets,k,diagonal=False):
        targets=np.asarray(targets);S=[];K=[]
        for block in np.array_split(targets,max(1,(len(targets)+31)//32)):
            d=self.samples[None,:,:,:]-block[:,None,None,:]
            r=np.sqrt(np.sum(d*d,axis=-1));weights=self.length[:,None]*self.w[None,:]
            S.append(np.sum(green(k,r)*weights,axis=-1))
            derivative=.25j*k*hankel2(1,k*r)*np.sum(d*self.normals[None,:,None,:],axis=-1)/r
            K.append(np.sum(derivative*weights,axis=-1))
        S=np.concatenate(S);K=np.concatenate(K)
        if diagonal:
            # Integrate the logarithmic singularity analytically; Gaussian
            # quadrature is applied only to the smooth remainder.
            r=self.length[:,None]*abs(self.t)[None,:]
            smooth=green(k,r)+np.log(abs(self.t))[None,:]/(2*np.pi)
            selfterm=self.length*(np.sum(smooth*self.w,axis=-1)+(1+np.log(2))/(2*np.pi))
            np.fill_diagonal(S,selfterm);np.fill_diagonal(K,0.)
        return S,K

    def solve(self,sources,receivers,epsilon=5.24-.632j,polarization='Ez',boundary='dielectric'):
        start=time.perf_counter();n=len(self.points);I=np.eye(n)
        delta=self.points[:,None,:]-np.asarray(sources)[None,:,:]
        incoming=green(self.k,np.sqrt(np.sum(delta*delta,axis=-1)))
        if boundary=='pec':
            if polarization=='Ez':A=self.S0;rhs=incoming;kind='q'
            else:A=.5*I-self.K0;rhs=incoming;kind='u'
        elif boundary=='impedance':
            beta=np.sqrt(epsilon) if polarization=='Ez' else 1/np.sqrt(epsilon)
            A=.5*I-self.K0+1j*self.k*beta*self.S0;rhs=incoming;kind='impedance'
        elif boundary=='dielectric':
            Si,Ki=self.operators(self.points,self.k*np.sqrt(epsilon),diagonal=True)
            alpha=1 if polarization=='Ez' else epsilon
            A=np.block([[.5*I-self.K0,self.S0],[.5*I+Ki,-alpha*Si]])
            rhs=np.r_[incoming,np.zeros_like(incoming)];kind='both'
        else:raise ValueError(boundary)
        solution=lu_solve(lu_factor(A),rhs)
        residual=np.linalg.norm(A@solution-rhs)/np.linalg.norm(rhs)
        if kind=='both':u,q=solution[:n],solution[n:]
        elif kind=='q':u=np.zeros_like(solution);q=solution
        elif kind=='u':u=solution;q=np.zeros_like(solution)
        else:u=solution;q=1j*self.k*beta*u
        S,K=self.operators(receivers,self.k)
        d=np.asarray(receivers)[:,None,:]-np.asarray(sources)[None,:,:]
        direct=green(self.k,np.linalg.norm(d,axis=-1))
        field=direct+K@u-S@q
        return field.T,dict(**self.metadata,epsilon=[epsilon.real,epsilon.imag],polarization=polarization,boundary=boundary,linear_residual=float(residual),solve_seconds=time.perf_counter()-start)

if __name__=='__main__':
    from run_maxwell_reference import SOURCES,RECEIVERS,MATERIALS
    from maxwell2d_reference import pec_green,free_green
    ap=argparse.ArgumentParser();ap.add_argument('output');ap.add_argument('--panels',type=int,default=16);ap.add_argument('--core',type=float,default=6.);ap.add_argument('--tail',type=float,default=5.);args=ap.parse_args()
    model=WedgeBEM(args.panels,args.core,args.tail);rows=[]
    for name,epsilon,boundary in [('air',1+0j,'dielectric'),('pec',1+0j,'pec'),('concrete',MATERIALS['concrete'],'dielectric')]:
        for pol in ('Ez','Hz'):
            u,meta=model.solve(SOURCES,RECEIVERS,epsilon,pol,boundary)
            if name=='air':exact=np.array([[free_green(s,r) for r in RECEIVERS] for s in SOURCES])
            elif name=='pec':exact=np.array([[pec_green(s,r,pol) for r in RECEIVERS] for s in SOURCES])
            else:exact=None
            row=dict(name=name,**meta,sources=SOURCES.tolist(),receivers=RECEIVERS.tolist(),field=np.stack([u.real,u.imag],axis=-1).tolist(),analytic_rms_error=float(np.linalg.norm(u-exact)/np.linalg.norm(exact)) if exact is not None else None)
            print(name,pol,row['analytic_rms_error'],row['linear_residual'],round(row['solve_seconds'],2),flush=True);rows.append(row)
    from pathlib import Path
    Path(args.output).write_text(json.dumps(rows,indent=2))

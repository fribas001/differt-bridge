"""Independent planar dielectric Fourier Green dyadic from Maxwell interfaces."""
import numpy as np
from scipy.integrate import quad_vec
K=2*np.pi
def root(v):
    a=np.sqrt(complex(v));return -a if a.imag>0 else a
def reflected(q,epsilon,source,receiver):
    sx,sy=source[:2];rx,ry=receiver[:2];assert sx<0 and rx<0
    distance=-sx-rx;dy=ry-sy
    def f(p):
        value=np.zeros((3,3),complex)
        for sign in (-1,1):
            py=sign*p;kx=root(K*K-py*py-q*q);kt=root(K*K*epsilon-py*py-q*q)
            tangent=np.sqrt(complex(py*py+q*q));s=np.array([0.,q,-py])/tangent
            ki=np.array([kx,-py,-q])/K;kr=np.array([-kx,-py,-q])/K
            pin=np.cross(s,ki);pref=np.cross(s,kr)
            rs=(kx-kt)/(kx+kt);rp=(epsilon*kx-kt)/(epsilon*kx+kt)
            dyad=rs*np.outer(s,s)+rp*np.outer(pref,pin)
            value+=(-1j/(2*kx))*np.exp(-1j*kx*distance+1j*py*dy)*dyad/(2*np.pi)
        return value
    v,e=quad_vec(f,0.,30.,epsabs=1e-11,epsrel=1e-10,points=[3.,6.,9.,15.])
    return v,e

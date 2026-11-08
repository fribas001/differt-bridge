"""Independent Sommerfeld angular-spectrum reflection for a 2D dielectric plane."""
import numpy as np
from scipy.integrate import quad
from scipy.special import hankel2

def reflected(source,receiver,epsilon,polarization='Ez',axis=0,k=2*np.pi,boundary='dielectric'):
    source=np.asarray(source);receiver=np.asarray(receiver)
    if source[axis]>=0 or receiver[axis]>=0:raise ValueError('Both ports must be outside the material halfspace')
    height=-source[axis]-receiver[axis];offset=receiver[1-axis]-source[1-axis]
    def R(c):
        if boundary=='pec':return -1 if polarization=='Ez' else 1
        if boundary!='dielectric':raise ValueError(boundary)
        q=np.sqrt(epsilon-1+c*c+0j)
        # Radiation branch for exp(+i wt): evanescent fields must decay.
        # At exactly real epsilon the principal square root alone selects
        # the wrong side of the negative real branch cut.
        if q.imag>0:q=-q
        return (c-q)/(c+q) if polarization=='Ez' else (epsilon*c-q)/(epsilon*c+q)
    def propagating(t):
        c,s=np.cos(t),np.sin(t)
        return R(c)*np.exp(-1j*k*height*c)*np.cos(k*offset*s)
    end=np.arcsinh(40/(k*height))
    def evanescent(t):
        s,c=np.sinh(t),np.cosh(t)
        return R(-1j*s)*np.exp(-k*height*s)*np.cos(k*offset*c)
    integrate=lambda f,a,b:quad(f,a,b,complex_func=True,epsabs=1e-11,epsrel=1e-10,limit=300)[0]
    return (-1j*integrate(propagating,0,np.pi/2)+integrate(evanescent,0,end))/(2*np.pi)

def go_reflected(source,receiver,epsilon,polarization='Ez',axis=0,k=2*np.pi):
    image=np.asarray(source).copy();image[axis]*=-1
    distance=np.linalg.norm(np.asarray(receiver)-image);c=abs(receiver[axis]-image[axis])/distance
    q=np.sqrt(epsilon-1+c*c+0j);r=(c-q)/(c+q) if polarization=='Ez' else (epsilon*c-q)/(epsilon*c+q)
    return r*(-.25j*hankel2(0,k*distance))

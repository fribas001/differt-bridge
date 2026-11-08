"""Convert local 3D UTD dyads to a 2D line-source asymptotic prediction.

This is the ray-model comparator, NOT the independent Maxwell reference.
Each ray's cylindrical Green function is used for GO. The diffracted line-source
field is G0(s') D exp(-iks)/sqrt(s), with L=s s'/(s+s').
"""
import numpy as np
from scipy.special import hankel2
from dielectric_cases import make
from dielectric_model import coefficient,go_coefficient

C=299792458.;EPS0=8.8541878188e-12
def fixture(source,receiver,epsilon,pol,name='reference_wedge'):
    case=make(name,60,100,'V' if pol=='Ez' else 'H','concrete')
    case['tx']=[*map(float,source),0.];case['receivers']=[[*map(float,receiver),0.]]
    case['frequency_hz']=C
    case['material'].update(relative_permittivity=float(epsilon.real),conductivity=float(-epsilon.imag*2*np.pi*C*EPS0),thickness=10.)
    return case

def green(distance):return -.25j*hankel2(0,2*np.pi*distance)

def field(source,receiver,epsilon,pol,profile):
    case=fixture(source,receiver,epsilon,pol)
    si=np.linalg.norm(source);s=np.linalg.norm(receiver);sign=1 if pol=='Ez' else -1
    a,_=coefficient(case,profile)
    scale=1/(4*np.pi*np.sqrt(si*s*(si+s)));D=sign*a/scale
    ud=green(si)*D*np.exp(-2j*np.pi*s)/np.sqrt(s)
    go=0j
    for boundary in ('incident','reflection0','reflectionn'):
        r=go_coefficient(case,boundary)
        if r is not None:
            coeff,length=r
            go+=sign*coeff*(4*np.pi*length)*green(length)
    return go+ud,go,ud

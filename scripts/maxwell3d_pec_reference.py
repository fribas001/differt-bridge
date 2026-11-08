"""Independent point-source PEC wedge Green function (exp(+i omega t)).

Sommerfeld/Carslaw contour for the periodic scalar Green function, followed
by Dirichlet images and the electric Hertz-vector operator. No UTD, ray
tracer, engine field, fitted coefficient, or 2D-to-3D spreading conversion.
See Rawlins (1989), doi:10.1017/S0305004100001523, sections 3--5.

The z column of the electric dyadic is exact for an electric dipole parallel
to the straight infinite edge: G_Ez=(I+grad grad/k^2) zhat G_D.
This does NOT implement arbitrary transverse sources or dielectric wedges.
"""
import numpy as np
from scipy.integrate import quad_vec
from scipy.special import hankel2


def polar(p):
    p=np.asarray(p,float)
    return np.linalg.norm(p[:2]), (np.arctan2(p[1],p[0])-np.pi/2)%(2*np.pi)


def radial(R,z,k,component):
    if component=='line':return -.25j*hankel2(0,k*R)
    g=np.exp(-1j*k*R)/(4*np.pi*R)
    if component=='scalar':return g
    if component=='dz':return g*(-1j*k-1/R)*z/R
    if component=='zz':
        a=z*z/(R*R)
        return g*(1-a+(3*a-1)*(1j/(k*R)+1/(k*R)**2))
    raise ValueError(component)


def wedge_green(source,receiver,k=2*np.pi,alpha=1.5*np.pi,component='zz',
                tolerance=2e-11,contour=.65,limit=45.,boundary='dirichlet',parts=False):
    """Exact scalar or edge-aligned electric Green function, canonical wedge.

    Exterior angle alpha begins at +y and turns counterclockwise. The
    contour t=u-i*c*(1-exp(-u/c)) is a deformation of the real Sommerfeld
    integral; it lies strictly right of all angular poles and damps outgoing
    waves. At a GO boundary the pole has its half-residue value.
    """
    s=np.asarray(source,float);r=np.asarray(receiver,float)
    rs,ps=polar(s);rr,pr=polar(r);dz=r[2]-s[2]
    if not (0<ps<alpha and 0<=pr<=alpha and rs>0 and rr>0):raise ValueError('Outside canonical exterior')
    if np.linalg.norm(r-s)<1e-10:raise ValueError('Coincident point sources are singular')
    if component=='line' and dz!=0:raise ValueError('Line-source control requires equal z')
    if not 0<contour<1.4:raise ValueError('Invalid contour')
    if boundary not in ('dirichlet','neumann'):raise ValueError(boundary)
    signs=(1,-1 if boundary=='dirichlet' else 1)
    go=0j;angles=[]
    for delta,sign in zip((pr-ps,pr+ps),signs):
        for m in range(-4,5):
            angle=delta+2*m*alpha;gap=np.pi-abs(angle)
            weight=1. if gap>1e-12 else .5 if abs(gap)<=1e-12 else 0.
            if weight:
                R=np.sqrt(rs*rs+rr*rr+dz*dz-2*rs*rr*np.cos(angle))
                go+=sign*weight*radial(R,dz,k,component)
        for a in ((np.pi+delta)*np.pi/alpha,(np.pi-delta)*np.pi/alpha):
            a=(a+np.pi)%(2*np.pi)-np.pi
            # Stable removable zero at an exact shadow/reflection boundary.
            if abs(a)>1e-12:angles.append((a,sign))
    R0=np.sqrt((rs+rr)**2+dz*dz);g0=radial(R0,dz,k,component)
    # Integrate the angular pole exactly, so very close boundary samples do
    # not depend on resolving a shrinking quadrature peak. The identity is
    # integral_0^inf sin(a)/(cosh(t/n)-cos(a)) dt = n*(pi*sign(a)-a).
    pole=-g0*sum(sign*(np.pi*np.sign(a)-a) for a,sign in angles)/(2*np.pi)
    def integrand(u):
        t=u-1j*contour*(1-np.exp(-u/contour));dt=1-1j*np.exp(-u/contour)
        R=np.sqrt(rs*rs+rr*rr+dz*dz+2*rs*rr*np.cosh(t))
        w=sum(sign*np.sin(a)/(2*np.sinh(np.pi*t/(2*alpha))**2+2*np.sin(a/2)**2) for a,sign in angles)
        g=radial(R,dz,k,component) if np.imag(k*R)>-600 else 0j
        return -(g-g0)*w*dt/(2*alpha)
    knots=[0.,.1,1.,3.,8.,limit]
    diffracted=pole;error=0.
    for a,b in zip(knots[:-1],knots[1:]):
        v,e=quad_vec(integrand,a,b,epsabs=tolerance,epsrel=tolerance)
        diffracted+=v;error+=e
    if parts:return dict(total=go+diffracted,go=go,diffracted=diffracted,quadrature_error=error)
    return go+diffracted


def electric_z_column(source,receiver,k=2*np.pi,h=2e-4,**kwargs):
    """Full electric vector from an edge-parallel point electric dipole.

    Transverse entries use fourth-order differentiation of analytic dG/dz;
    h convergence is mandatory when those entries are used.
    """
    r=np.asarray(receiver,float);v=np.zeros(3,complex)
    for axis in (0,1):
        d=np.eye(3)[axis]*h
        values=[wedge_green(source,r+j*d,k,component='dz',**kwargs) for j in (-2,-1,1,2)]
        v[axis]=(values[0]-8*values[1]+8*values[2]-values[3])/(12*h*k*k)
    v[2]=wedge_green(source,r,k,component='zz',**kwargs)
    return v


def free_dyadic(source,receiver,k=2*np.pi):
    d=np.asarray(receiver,float)-source;R=np.linalg.norm(d);n=d/R
    g=np.exp(-1j*k*R)/(4*np.pi*R);q=1j/(k*R)+1/(k*R)**2
    return g*((1-q)*np.eye(3)+(-1+3*q)*np.outer(n,n))


def free_far_dyadic(source,receiver,k=2*np.pi):
    d=np.asarray(receiver,float)-source;R=np.linalg.norm(d);n=d/R
    return np.exp(-1j*k*R)/(4*np.pi*R)*(np.eye(3)-np.outer(n,n))

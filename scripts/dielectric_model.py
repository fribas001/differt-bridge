"""Float64 formula audit, NOT an independent dielectric-wedge accuracy reference.

The engine transcriptions isolate angular weights, full reflection-basis transport,
and material-angle choices. Only PEC coefficients have an independent reference.
"""
import copy
import numpy as np
from diffraction_reference import C,transition,stationary_edge
from diffraction_physics_cases import unit,spherical

def fresnel(cosine,eta,d,k):
    cosine=abs(cosine);q=np.sqrt(eta-1+cosine*cosine+0j)
    rs=(cosine-q)/(cosine+q);rp=(eta*cosine-q)/(eta*cosine+q)
    if d is None or d<0:return rs,rp
    phase=np.exp(-2j*k*d*q)
    return tuple(r*(1-phase)/(1-r*r*phase) for r in (rs,rp))

def coefficient(case,profile,rx=0,*,fresnel_policy='incident'):
    if profile in ('differt-reciprocal','sionna-reciprocal'):
        reverse=copy.deepcopy(case)
        reverse['tx'],reverse['receivers']=case['receivers'][rx],[case['tx']]
        reverse['tx_pol'],reverse['rx_pol']=case['rx_pol'],case['tx_pol']
        f,detail=coefficient(case,'sionna-kp_depth',rx,fresnel_policy=fresnel_policy)
        r,_=coefficient(reverse,'sionna-kp_depth',fresnel_policy=fresnel_policy)
        return .5*(f+r),dict(detail,reciprocal_dyad=True)
    tx=np.asarray(case['tx']);dest=np.asarray(case['receivers'][rx]);rot=np.asarray(case.get('physics',{}).get('rotation',np.eye(3)))
    edge=case['canonical_edges'][0];q=stationary_edge(tx,dest,edge)
    ki=unit(q-tx);ko=unit(dest-q);e=rot@np.array([0.,0.,-1.]);n0=rot@np.array([0.,-1.,0.]);nn=rot@np.array([-1.,0.,0.])
    # All fixtures use the same 90 degree solid sector. The edge face labels are
    # treated as a diagnostic variable, never as a change in physical geometry.
    if case['name'].endswith('__face_swap'):n0,nn,e=nn,n0,-e
    if ki@n0>0:n0,nn,e=nn,n0,-e
    t0=np.cross(n0,e);ki_proj=unit(ki-(ki@e)*e);ko_proj=unit(ko-(ko@e)*e)
    pi=np.arctan2((-ki_proj)@n0,(-ki_proj)@t0)%(2*np.pi)
    pd=np.arctan2(ko_proj@n0,ko_proj@t0)%(2*np.pi)
    n=1.5;sb=np.linalg.norm(np.cross(ki,e));k=2*np.pi*case['frequency_hz']/C
    sp=np.linalg.norm(q-tx);s=np.linalg.norm(dest-q);L=s*sp/(s+sp)*sb*sb
    factor=-np.exp(-.25j*np.pi)/(2*n*np.sqrt(2*np.pi*k)*sb)
    def term(beta,sign):
        order=np.rint((beta+sign*np.pi)/(2*n*np.pi));arg=2*np.cos(n*np.pi*order-beta/2)**2
        psi=(np.pi+sign*beta)/(2*n)
        if abs(np.sin(psi))<1e-12:raise ValueError('Exact boundary requires a specified one-sided limit')
        return factor*transition(k*L*arg)/np.tan(psi)
    d1,d2=term(pd-pi,1),term(pd-pi,-1);d3,d4=term(pd+pi,1),term(pd+pi,-1)
    m=case['material'];eta=m['relative_permittivity']-1j*m['conductivity']/(2*np.pi*case['frequency_hz']*8.8541878188e-12)
    co,cn=abs(ki@n0),abs(ki@nn)
    if profile in ('differt-native','differt-polarization'):co,cn=abs(np.sin(pi)),abs(np.sin(n*np.pi-pd))
    elif profile=='differt-symmetric_cosine':co,cn=.5*(abs(ki@n0)+abs(ko@n0)),.5*(abs(ki@nn)+abs(ko@nn))
    if fresnel_policy!='incident':
        if profile!='sionna-kp_depth':raise ValueError('Policies apply only to the full Jones candidate')
        def symmetric(a,b):
            if fresnel_policy=='mean_cosine':return .5*(a+b)
            if fresnel_policy=='angle_bisector':return np.cos(.5*(np.arccos(np.clip(a,0,1))+np.arccos(np.clip(b,0,1))))
            if fresnel_policy=='geometric_cosine':return np.sqrt(a*b)
            raise ValueError(fresnel_policy)
        co,cn=symmetric(abs(ki@n0),abs(ko@n0)),symmetric(abs(ki@nn),abs(ko@nn))
    rso,rpo=fresnel(co,eta,m['thickness'],k);rsn,rpn=fresnel(cn,eta,m['thickness'],k)
    p_i=unit(np.cross(ki,e));p_o=-unit(np.cross(ko,e));B_i=np.stack([p_i,np.cross(p_i,ki)],axis=1);B_o=np.stack([p_o,np.cross(p_o,ko)],axis=1)
    if profile=='differt-native':D=np.diag([-(d1+d2)+rsn*d3+rso*d4,-(d1+d2)+rpn*d3+rpo*d4])
    elif profile.startswith('differt-'):D=np.diag([-(d1+d2)-rpn*d3-rpo*d4,-(d1+d2)-rsn*d3-rso*d4])
    else:
        def R(normal,rs,rp):
            reflected=ki-2*(ki@normal)*normal;se=np.cross(ki,normal)
            if np.linalg.norm(se)<1e-12:
                ref=np.array([1.,0.,0.]) if abs(ki[0])<.9 else np.array([0.,1.,0.])
                se=ref-(ref@ki)*ki
            se=unit(se)
            pi_=np.cross(se,ki);po_=np.cross(se,reflected)
            shadow_phi=-unit(np.cross(reflected,e));B_shadow=np.stack([shadow_phi,np.cross(shadow_phi,reflected)],axis=1)
            return B_shadow.T@(rs*np.outer(se,se)+rp*np.outer(po_,pi_))@B_i
        R0,Rn=R(n0,rso,rpo),R(nn,rsn,rpn)
        if profile=='sionna-native':
            if n*np.pi>np.pi+pi:Rn=-np.eye(2)
            D=R0*(d1-d4)+Rn*(d2-d3)
        elif profile=='sionna-kp_depth':D=-np.eye(2)*(d1+d2)+R0*d4+Rn*d3
        else:raise ValueError(profile)
    dyad=B_o@D@B_i.T
    g=C/case['frequency_hz']/(4*np.pi*np.sqrt(sp*s*(sp+s)))
    value=g*spherical(-ko,case['rx_pol'])@dyad@spherical(ki,case['tx_pol'])
    return complex(value),dict(phi_i_deg=float(np.rad2deg(pi)),phi_d_deg=float(np.rad2deg(pd)),face_cosines=[float(co),float(cn)],sin_beta=float(sb),off_diagonal_norm=float(np.linalg.norm(D-np.diag(np.diag(D)))),distance_m=float(sp+s))

def go_coefficient(case,boundary,rx=0):
    """Independent point-source LoS/specular field for the chosen canonical face.

    Boundary-only fixtures have two finite faces and no unrelated obstacles.
    Returns None on the geometrically absent side of the chosen GO boundary.
    """
    rot=np.asarray(case['physics']['rotation']);tx=np.asarray(case['tx']);dest=np.asarray(case['receivers'][rx])
    m=case['material'];frequency=case['frequency_hz'];k=2*np.pi*frequency/C
    if boundary=='incident':
        a,b=rot.T@tx,rot.T@dest
        for axis,other in ((0,1),(1,0)):
            den=b[axis]-a[axis]
            if abs(den)>1e-15:
                t=-a[axis]/den
                if 0<t<1 and (a+t*(b-a))[other]>0:return None
        direction=unit(dest-tx);length=np.linalg.norm(dest-tx)
        value=C/frequency/(4*np.pi*length)*(spherical(-direction,case['rx_pol'])@spherical(direction,case['tx_pol']))
    else:
        axis=0 if boundary=='reflection0' else 1;other=1-axis
        normal=rot@np.eye(3)[axis];image=tx-2*(tx@normal)*normal
        den=(dest-image)@normal
        if abs(den)<1e-15:return None
        t=-(image@normal)/den;q=image+t*(dest-image)
        if not 0<t<1 or (rot.T@q)[other]<=0:return None
        ki=unit(q-tx);ko=unit(dest-q);length=np.linalg.norm(q-tx)+np.linalg.norm(dest-q)
        se=unit(np.cross(ki,normal));pi=np.cross(se,ki);po=np.cross(se,ko)
        eta=m['relative_permittivity']-1j*m['conductivity']/(2*np.pi*frequency*8.8541878188e-12)
        rs,rp=fresnel(ki@normal,eta,m['thickness'],k)
        dyad=rs*np.outer(se,se)+rp*np.outer(po,pi)
        value=C/frequency/(4*np.pi*length)*spherical(-ko,case['rx_pol'])@dyad@spherical(ki,case['tx_pol'])
    return complex(value),float(length)

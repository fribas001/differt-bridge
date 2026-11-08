"""Optional 3D PEC Hertz-UTD correction; no Maxwell-reference imports or fits.

Returns a separate canonical point-dipole field; native engine exports survive.
The scalar UTD potential is differentiated as a whole, including its GO terms,
so finite-range electric fields preserve the transition cancellation.
"""
import json
from pathlib import Path
import numpy as np
from scipy.special import erfcx

def polar(p):
    p=np.asarray(p,float)
    return np.linalg.norm(p[:2]),(np.arctan2(p[1],p[0])-np.pi/2)%(2*np.pi)

def potential(source,receiver,k=2*np.pi):
    s=np.asarray(source);r=np.asarray(receiver);rs,ps=polar(s);rr,pr=polar(r)
    dz=r[2]-s[2];R=np.sqrt((rs+rr)**2+dz*dz);n=1.5;L=rs*rr/R
    total=0j
    for delta,weight in ((pr-ps,1),(pr+ps,-1)):
        for m in range(-2,3):
            a=delta+2*np.pi*n*m;gap=np.pi-abs(a)
            go=1 if gap>1e-12 else .5 if abs(gap)<=1e-12 else 0
            if go:
                rho=np.sqrt(rs*rs+rr*rr+dz*dz-2*rs*rr*np.cos(a))
                total+=weight*go*np.exp(-1j*k*rho)/(4*np.pi*rho)
        for sign in (1,-1):
            N=np.rint((delta+sign*np.pi)/(2*np.pi*n));d=delta-(2*np.pi*n*N-sign*np.pi)
            if abs(d)<1e-12:continue
            a=2*np.sin(d/2)**2
            c=np.sqrt(2)*abs(np.sin(d/2))/np.tan(sign*d/(2*n))
            Fcot=np.sqrt(np.pi*k*L)*np.exp(.25j*np.pi)*erfcx(np.exp(.25j*np.pi)*np.sqrt(k*L*a))*c
            total+=weight*(-np.exp(-.25j*np.pi)/(2*n*np.sqrt(2*np.pi*k)))*Fcot*np.exp(-1j*k*R)/(4*np.pi*np.sqrt(rs*rr*R))
    return total

def vector(source,receiver,h=5e-4):
    r=np.asarray(receiver);zdir=np.array([0.,0.,h]);f=lambda p:potential(source,p);g=f(r)
    result=np.zeros(3,complex)
    result[2]=g+(-f(r+2*zdir)+16*f(r+zdir)-30*g+16*f(r-zdir)-f(r-2*zdir))/(12*h*h*(2*np.pi)**2)
    weights={-2:1,-1:-8,1:8,2:-1}
    for axis in (0,1):
        d=np.eye(3)[axis]*h
        result[axis]=sum(a*b*f(r+i*d+j*zdir) for i,a in weights.items() for j,b in weights.items())/(144*h*h*(2*np.pi)**2)
    return result


def validate(c):
    """Fail closed before evaluating any part of a batch, including obstacles."""
    from diffraction_cases import wedge
    def require(ok,why):
        if not ok:raise ValueError('Unsupported PEC 3D refinement: '+why)
    require(c.get('study',{}).get('kind')=='native3d','explicit native3d point-source benchmark declaration')
    require(c.get('frequency_hz')==299792458.,'wavelength must be 1 m')
    require(c.get('pattern')=='dipole' and c.get('tx_pol')==c.get('rx_pol')=='V' and c.get('array_cols',1)==1,'single short electric dipole ports')
    require(np.array_equal(c.get('tx_orientation',[0,0,0]),[0,0,0]),'source must be parallel to z edge')
    axis=c['study'].get('receiver_axis');orient={'z':[0,0,0],'x':[0,np.pi/2,0],'y':[np.pi/2,np.pi/2,0]}
    require(axis in orient and np.array_equal(c.get('rx_orientation',[0,0,0]),orient[axis]),'receiver orientation')
    require(c['meshes'] in ([wedge(length=160,height=160)],[wedge(length=80,height=80)]),'canonical wedge only; extra or changed obstacles are rejected')
    m=c['material'];require(m['relative_permittivity']==1. and m['conductivity']>=1e12*.999 and m['thickness']==10. and m['scattering_coefficient']==0.,'declared PEC-limit material only; no dielectric substitution')
    solver=c['solver'];require(solver['max_depth']==1 and solver['los'] and solver['specular_reflection'] and solver['diffraction'] and solver['diffraction_lit_region'] and not solver['diffuse_reflection'] and not solver['refraction'] and not solver['edge_diffraction'] and not solver['synthetic_array'],'single-edge GO plus diffraction configuration')
    s=np.asarray(c['tx']);require(s.shape==(3,) and np.isfinite(s).all(),'finite source')
    for r in [s,*c['receivers']]:
        r=np.asarray(r);require(r.shape==(3,) and np.isfinite(r).all(),'finite ports')
        rho,phi=polar(r);require(.5<=rho<=20 and .01<phi<1.5*np.pi-.01 and abs(r[2])<=40,'validated canonical exterior domain')
    for r in c['receivers']:require(np.linalg.norm(np.asarray(r)-s)>.25,'separated point ports')


def refine(cases,h=2.5e-4):
    for c in cases:validate(c)
    fields=[]
    for c in cases:
        axis={'x':0,'y':1,'z':2}[c['study']['receiver_axis']]
        values=np.array([1.5*vector(c['tx'],r,h=h)[axis] for r in c['receivers']])
        fields.append(dict(name=c['name'],field=np.stack([values.real,values.imag],axis=-1).tolist()))
    import hashlib
    return dict(status='completed',mode='optional_3d_pec_hertz_utd',scope='Infinite PEC right-angle wedge, edge-parallel short electric point dipole, z/x/y receiver. Higher-order asymptotic field, not an exact Maxwell solver or dielectric correction.',reference_used=False,native_exports_modified=False,step=h,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),results=fields)


if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('manifest',type=Path);ap.add_argument('output',type=Path);a=ap.parse_args()
    result=refine(json.loads(a.manifest.read_text(encoding='utf-8'))['cases'])
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')


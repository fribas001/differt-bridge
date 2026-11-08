"""Reciprocal full-Jones UTD approximation, using native transition/Fresnel kernels.

The transpose is a Cartesian dyadic transpose (not a Hermitian adjoint).
This restores Lorentz reciprocity of a local reciprocal wedge approximation;
it does not turn a thin-surface ray model into a volumetric Maxwell solution.
"""
import jax.numpy as jnp
from differt.em._utd import _cot_times_F
from differt.em._solvers import _get_reflection_coefficients
from differt.em._utils import _spherical_basis

def unit(x):return x/jnp.maximum(jnp.linalg.norm(x,axis=-1,keepdims=True),1e-20)
def dot(a,b):return jnp.sum(a*b,axis=-1)
def outer(a,b):return a[..., :,None]*b[...,None,:]
def swapaxes(x):return jnp.swapaxes(x,-1,-2)

def boundary_cot(beta,n,k,L,mode):
    value=_cot_times_F(beta,n,k,L,mode)
    sign=1. if mode=='+' else -1.
    nearest=jnp.round((beta+sign*jnp.pi)/(2*n*jnp.pi))
    delta=beta-(2*n*jnp.pi*nearest-sign*jnp.pi)
    # At float32-indistinguishable coincidence use the shadow-side joint-field
    # convention. The coincident GO companion is removed by the bridge wrapper.
    limit=-n*(1.+1j)*jnp.sqrt(jnp.pi*k*L)
    return jnp.where(jnp.abs(delta)<8e-7,limit,value)

def forward(ki,ko,e,n0,nn,n,k,L,nr0,nrn,d0,dn):
    # Orient the two physical faces together with their materials and edge tangent.
    swap=dot(ki,n0)>0
    n0,nn=jnp.where(swap[...,None],nn,n0),jnp.where(swap[...,None],n0,nn)
    e=jnp.where(swap[...,None],-e,e)
    nr0,nrn=jnp.where(swap,nrn,nr0),jnp.where(swap,nr0,nrn)
    d0,dn=jnp.where(swap,dn,d0),jnp.where(swap,d0,dn)
    t0=unit(jnp.cross(n0,e));pi=unit(ki-dot(ki,e)[...,None]*e);po=unit(ko-dot(ko,e)[...,None]*e)
    ai=jnp.mod(jnp.arctan2(dot(-pi,n0),dot(-pi,t0)),2*jnp.pi)
    ao=jnp.mod(jnp.arctan2(dot(po,n0),dot(po,t0)),2*jnp.pi)
    sb=jnp.maximum(jnp.linalg.norm(jnp.cross(ki,e),axis=-1),1e-12)
    factor=-jnp.exp(-.25j*jnp.pi)/(2*n*jnp.sqrt(2*jnp.pi*k)*sb)
    d1=factor*boundary_cot(ao-ai,n,k,L,'+');d2=factor*boundary_cot(ao-ai,n,k,L,'-')
    d3=factor*boundary_cot(ao+ai,n,k,L,'+');d4=factor*boundary_cot(ao+ai,n,k,L,'-')
    p_i=unit(jnp.cross(ki,e));p_o=-unit(jnp.cross(ko,e))
    Bi=jnp.stack([p_i,jnp.cross(p_i,ki)],axis=-1)
    Bo=jnp.stack([p_o,jnp.cross(p_o,ko)],axis=-1)
    def reflection(normal,nr,thickness):
        kr=ki-2*dot(ki,normal)[...,None]*normal
        te=jnp.cross(ki,normal)
        # Deterministic transverse fallback for the degenerate normal-incidence basis.
        reference=jnp.where((jnp.abs(ki[...,0])<.9)[...,None],jnp.array([1.,0.,0.]),jnp.array([0.,1.,0.]))
        fallback=reference-dot(reference,ki)[...,None]*ki
        te=unit(jnp.where((dot(te,te)<1e-20)[...,None],fallback,te))
        p_in=jnp.cross(te,ki);p_ref=jnp.cross(te,kr)
        rs,rp=_get_reflection_coefficients(nr,jnp.abs(dot(ki,normal)),thickness,2*jnp.pi/k)
        cart=rs[...,None,None]*outer(te,te)+rp[...,None,None]*outer(p_ref,p_in)
        ps=-unit(jnp.cross(kr,e));Bs=jnp.stack([ps,jnp.cross(ps,kr)],axis=-1)
        return swapaxes(Bs)@cart@Bi
    R0=reflection(n0,nr0,d0);Rn=reflection(nn,nrn,dn)
    D=-(d1+d2)[...,None,None]*jnp.eye(2)+d4[...,None,None]*R0+d3[...,None,None]*Rn
    return Bo@D@swapaxes(Bi)

def reciprocal_jones(ki,ko,e,n0,nn,n,k,L,nr0,nrn,d0,dn):
    f=forward(ki,ko,e,n0,nn,n,k,L,nr0,nrn,d0,dn)
    r=forward(-ko,-ki,e,n0,nn,n,k,L,nr0,nrn,d0,dn)
    T=.5*(f+swapaxes(r))
    it,ip=_spherical_basis(ki);ot,op=_spherical_basis(ko)
    Bi=jnp.stack([it,ip],axis=-1);Bo=jnp.stack([ot,op],axis=-1)
    return swapaxes(Bo)@T@Bi

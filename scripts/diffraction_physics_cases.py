"""Independent, signed PEC reference and reproducible field-diagnostic fixtures."""
import copy
import json
from pathlib import Path
import numpy as np
from diffraction_cases import base, wedge, f32, benchmark_cases
from diffraction_reference import pec_utd, stationary_edge, C


def unit(v):
    v=np.asarray(v,float)
    return v/np.linalg.norm(v)


def spherical(k,pol):
    k=unit(k); phi=np.arctan2(k[1],k[0]); theta=np.arccos(np.clip(k[2],-1,1))
    return (np.array([np.cos(theta)*np.cos(phi),np.cos(theta)*np.sin(phi),-np.sin(theta)])
            if pol=='V' else np.array([-np.sin(phi),np.cos(phi),0.]))


def pec_channel(case,rx=0):
    """KP dyad contracted with the actual TX/RX spherical antenna ports.

    No engine field, angle, delay, basis, or coefficient is used. Valid for one
    straight PEC edge and a point source, away from exact shadow boundaries.
    """
    meta=case['physics']; rot=np.asarray(meta['rotation']); edge=case['canonical_edges'][0]
    tx=np.asarray(case['tx']); dest=np.asarray(case['receivers'][rx])
    q=stationary_edge(tx,dest,edge); ki=unit(q-tx); ko=unit(dest-q); e=unit(edge['direction'])
    a=rot.T@(tx-q); b=rot.T@(dest-q); opening=np.deg2rad(meta['opening_deg'])
    phi_i=(np.arctan2(a[1],a[0])-opening)%(2*np.pi)
    phi_d=(np.arctan2(b[1],b[0])-opening)%(2*np.pi)
    n=2-opening/np.pi; sp=np.linalg.norm(q-tx); s=np.linalg.norm(dest-q)
    sin_beta=np.linalg.norm(np.cross(ki,e)); L=sp*s/(sp+s)*sin_beta**2
    ds,dh=pec_utd(2*np.pi*case['frequency_hz']/C,n,phi_i,phi_d,L,sin_beta)
    pin=unit(np.cross(ki,e)); pout=-unit(np.cross(ko,e))
    bin_=np.cross(ki,pin); bout=np.cross(ko,pout)
    dyad=-dh*np.outer(pout,pin)-ds*np.outer(bout,bin_)
    g=C/case['frequency_hz']/(4*np.pi*np.sqrt(sp*s*(sp+s)))
    return complex(g*spherical(-ko,case['rx_pol'])@dyad@spherical(ki,case['tx_pol']))


def fixture(name,phi_i,phi_d,pol='V',material='pec',rotation=None,z=(-0.,0.)):
    c=base(name); rot=np.eye(3) if rotation is None else np.asarray(rotation)
    def pos(angle,r,h):
        a=np.deg2rad(90+angle)
        return [f32(x) for x in rot@np.array([r*np.cos(a),r*np.sin(a),h])]
    c['tx']=pos(phi_i,3,z[0]);c['receivers']=[pos(phi_d,4,z[1])]
    c['tx_pol']=pol[0];c['rx_pol']=pol[-1]
    c['category']='field_physics';c['meshes']=[wedge(length=40,height=40)]
    c['meshes'][0]['vertices']=[[f32(v) for v in rot@p] for p in c['meshes'][0]['vertices']]
    c['canonical_edges'][0].update(direction=(rot@np.array([0.,0.,1.])).tolist(),half_length=40)
    c['physics']=dict(material=material,rotation=rot.tolist(),opening_deg=90,phi_i_deg=phi_i,phi_d_deg=phi_d)
    c['expected']='One central-edge path; signed complex coefficient compared with KP only for PEC-limit material.'
    if material=='pec':c['material'].update(relative_permittivity=1.,conductivity=f32(1e12))
    if material=='lossless':c['material'].update(relative_permittivity=4.,conductivity=0.)
    return c


def cases():
    result=[]
    def paired(c):
        result.append(c)
        b=copy.deepcopy(c);b['name']+='__reverse';b['tx'],b['receivers']=b['receivers'][0],[b['tx']]
        b['tx_pol'],b['rx_pol']=b['rx_pol'],b['tx_pol'];b['physics']['reverse_of']=c['name'];result.append(b)
    for material in ('pec','concrete','lossless'):
        for i,(pi,pd) in enumerate(((60,100),(30,240),(150,80),(120,166),(150,260))):
            for pol in ('V','H'):
                paired(fixture(f'{material}_angle{i}_{pol}',pi,pd,pol,material))
    a=np.deg2rad(57);b=np.deg2rad(23)
    ry=np.array([[np.cos(a),0,np.sin(a)],[0,1,0],[-np.sin(a),0,np.cos(a)]])
    rz=np.array([[np.cos(b),-np.sin(b),0],[np.sin(b),np.cos(b),0],[0,0,1]])
    for label,rot,z in [('skew',np.eye(3),(-3,5)),('tilted',rz@ry,(0,0)),('tilted_skew',rz@ry,(-3,5))]:
        for pol in ('VV','HH','VH','HV'):
            paired(fixture(f'pec_{label}_{pol}',45,210,pol,rotation=rot,z=z))
    for material in ('pec','concrete'):
        for label,pi,bound in [('incident',30,210),('reflection0',60,120),('reflectionn',120,240)]:
            for pol in ('V','H'):
                c=fixture(f'boundary_{material}_{label}_{pol}',pi,bound,pol,material)
                offsets=[-e for e in (1,.1,.01,.001)]+[e for e in (.001,.01,.1,1)]
                c['receivers']=[fixture('x',pi,bound+e,pol,material)['receivers'][0] for e in offsets]
                c['solver'].update(los=True,specular_reflection=True)
                c['physics'].update(boundary=label,offsets_deg=offsets);result.append(c)
    original={c['name']:c for c in benchmark_cases()}
    for pol in ('V','H'):
        for depth in (2,3,5):
            c=copy.deepcopy(original['reflection_diffraction']);c['name']=f'mixed_{pol}_depth{depth}'
            c['tx_pol']=c['rx_pol']=pol;c['solver']['max_depth']=depth
            c['physics']=dict(depth_control=True);result.append(c)
    for name in ('wedge_v','wedge_h','wedge_reciprocal','block_incoming','block_outgoing','clear_nearby'):
        c=copy.deepcopy(original[name]);c['physics']=dict(baseline_control=True);result.append(c)
    return result


if __name__=='__main__':
    import sys
    target=Path(sys.argv[1]);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(dict(schema='diffraction_physics_cases_v1',cases=cases()),indent=2),encoding='utf-8')
    print(len(cases()),'fixtures',flush=True)

"""Independent NumPy/SciPy checks; imports neither ray tracer.

PEC UTD: Kouyoumjian & Pathak, Proc. IEEE 62(11), 1974.
This is an asymptotic conducting-wedge reference, not a full-wave solution.
F is evaluated through SciPy's complex scaled erfc, not engine Fresnel routines.
"""
import math
import numpy as np
from scipy.special import erfcx

C=299792458.


def transition(x):
    x=np.asarray(x,dtype=float)
    return np.sqrt(np.pi*x)*np.exp(.25j*np.pi)*erfcx(np.exp(.25j*np.pi)*np.sqrt(x))


def pec_utd(k,n,phi_i,phi_d,L,sin_beta=1.):
    """Classical soft/hard scalar coefficients, away from exact boundaries."""
    def pair(beta):
        values=[]
        for sign in (1,-1):
            N=np.rint((beta+sign*np.pi)/(2*np.pi*n))
            a=2*np.cos(np.pi*n*N-beta/2)**2
            psi=(np.pi+sign*beta)/(2*n)
            if abs(np.sin(psi))<1e-10: raise ValueError('Exact boundary: use one-sided limits')
            values.append(transition(k*L*a)/np.tan(psi))
        return sum(values)
    factor=-np.exp(-.25j*np.pi)/(2*n*np.sqrt(2*np.pi*k)*sin_beta)
    direct=pair(phi_d-phi_i); reflected=pair(phi_d+phi_i)
    return factor*(direct-reflected),factor*(direct+reflected)


def broadside_pec(case):
    """Vertical 90-degree solid wedge in +x,+y, isotropic V/V or H/H."""
    tx=np.asarray(case['tx']); rx=np.asarray(case['receivers'][0])
    if tx[2]!=rx[2]: raise ValueError('Broadside reference only')
    sp=np.linalg.norm(tx[:2]); s=np.linalg.norm(rx[:2])
    phi_i=(math.atan2(tx[1],tx[0])-np.pi/2)%(2*np.pi)
    phi_d=(math.atan2(rx[1],rx[0])-np.pi/2)%(2*np.pi)
    soft,hard=pec_utd(2*np.pi*case['frequency_hz']/C,1.5,phi_i,phi_d,sp*s/(sp+s))
    # E_z has the soft boundary condition; H_z has the hard condition.
    # The RX spherical H basis reverses the sign of the scalar H result.
    field=soft if case['tx_pol']=='V' else -hard
    return field*C/case['frequency_hz']/(4*np.pi*np.sqrt(sp*s*(sp+s)))


def stationary_edge(tx,rx,edge):
    o=np.asarray(edge['origin']); e=np.asarray(edge['direction']); e=e/np.linalg.norm(e)
    a=np.asarray(tx)-o; b=np.asarray(rx)-o
    za=np.dot(a,e); zb=np.dot(b,e)
    ra=np.linalg.norm(a-za*e); rb=np.linalg.norm(b-zb*e)
    return o+((rb*za+ra*zb)/(ra+rb))*e


def geometry_audit(path,case):
    points=np.asarray(path['points'],float); diffs=[]; hits=[]; reflections=[]
    for i,flag in enumerate(path['interactions'],1):
        if flag==1:
            options=[]
            for mesh in case['meshes']:
                for triangle in mesh['triangles']:
                    a,b,c=np.asarray(mesh['vertices'],float)[triangle]
                    normal=np.cross(b-a,c-a); normal/=np.linalg.norm(normal)
                    distance=abs(float((points[i]-a)@normal))
                    if distance<1e-4:
                        incoming=points[i]-points[i-1];incoming/=np.linalg.norm(incoming)
                        outgoing=points[i+1]-points[i];outgoing/=np.linalg.norm(outgoing)
                        options.append(float(np.linalg.norm(outgoing-(incoming-2*(incoming@normal)*normal))))
            reflections.append(dict(point_index=i,reflection_law_residual=min(options) if options else None))
        if flag!=8: continue
        options=[]
        for edge in case.get('canonical_edges',[]):
            origin=np.asarray(edge['origin']); e=np.asarray(edge['direction']); e=e/np.linalg.norm(e)
            v=points[i]-origin; z=float(v@e); d=float(np.linalg.norm(v-z*e))
            options.append((d,z,edge,e))
        if options:
            d,z,edge,e=min(options,key=lambda v:v[0]); u=points[i]-points[i-1]; v=points[i+1]-points[i]
            cone=abs(float((u/np.linalg.norm(u)-v/np.linalg.norm(v))@e))
            rec=dict(point_index=i,edge_distance_m=d,edge_coordinate_m=z,within_edge=abs(z)<=edge['half_length']+1e-6,keller_residual=cone)
            if len(path['interactions'])==1 and d<1e-3:
                rec['stationary_point_error_m']=float(np.linalg.norm(points[i]-stationary_edge(points[0],points[-1],edge)))
            diffs.append(rec)
    # Open segment/triangle intersection, float64. Endpoint contacts are
    # excluded by physical distance, not by deleting reflecting/edge obstacles.
    for si,(start,end) in enumerate(zip(points[:-1],points[1:])):
        direction=end-start; length=np.linalg.norm(direction)
        if length==0: continue
        for mesh in case['meshes']:
            vs=np.asarray(mesh['vertices'],float)
            for ti,tri in enumerate(mesh['triangles']):
                a,b,c=vs[tri]; e1=b-a; e2=c-a; p=np.cross(direction,e2); det=float(e1@p)
                if abs(det)<1e-12*np.linalg.norm(e1)*np.linalg.norm(e2)*length: continue
                tvec=start-a; u=float(tvec@p)/det
                q=np.cross(tvec,e1); v=float(direction@q)/det; t=float(e2@q)/det
                if u>=-1e-10 and v>=-1e-10 and u+v<=1+1e-10 and 1e-6<t*length<length-1e-6:
                    hits.append(dict(segment=si,mesh=mesh['name'],triangle=ti,distance_from_start_m=t*length))
    return dict(diffractions=diffs,reflections=reflections,interior_triangle_hits=hits,
                scope='Non-coplanar open-segment intersection; coplanar grazing contacts and vertex diffraction are not certified')


def duplicates(paths,tolerance=1e-5):
    found=[]
    for i,p in enumerate(paths):
        for j,q in enumerate(paths[:i]):
            if p['rx']==q['rx'] and p['interactions']==q['interactions'] and len(p['points'])==len(q['points']):
                error=float(np.max(np.linalg.norm(np.asarray(p['points'])-np.asarray(q['points']),axis=-1)))
                if error<=tolerance: found.append(dict(first=j,second=i,maximum_vertex_difference_m=error))
    return found

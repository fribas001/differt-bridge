"""Reciprocal point-ray to line-source normalization, not a Maxwell correction.

The symmetric closure uses G(s+s') sqrt((s+s')/(s s')). It shares the
leading high-frequency limit of G(s') exp(-iks)/sqrt(s), is symmetric in
the two legs, and uses the same Green function as a coincident GO ray.
No material, angle, or reference-fit parameter enters this conversion.
The original closure remains available to measure normalization uncertainty.
"""
import numpy as np
from ray_wedge2d import green

def kernel(source_distance,receiver_distance,mode='symmetric'):
    si,s=np.asarray(source_distance),np.asarray(receiver_distance)
    if np.any(si<=0) or np.any(s<=0):raise ValueError('Positive exterior leg lengths required')
    if mode=='symmetric':return green(si+s)*np.sqrt((si+s)/(si*s))
    if mode=='legacy':return green(si)*np.exp(-2j*np.pi*s)/np.sqrt(s)
    raise ValueError(mode)

def channel(case,row,receiver,mode='symmetric'):
    """Convert actual exported paths, retaining every valid GO/diffraction ray."""
    pol=case['study']['polarization'];sign=1 if pol=='Ez' else -1
    go=0j;diffracted=0j;count=0
    for path in (p for p in row['paths'] if p['rx']==receiver):
        a=complex(*path['a']);length=path['geometric_length_m']
        if path['interactions']==[8]:
            q=np.asarray(path['points'][1])
            if np.linalg.norm(q)>1e-5:raise ValueError('Only the central broadside edge is supported')
            si=np.linalg.norm(np.asarray(case['tx'])-q);s=np.linalg.norm(np.asarray(case['receivers'][receiver])-q)
            diffracted+=sign*a*(4*np.pi*np.sqrt(si*s*(si+s)))*kernel(si,s,mode);count+=1
        elif path['interactions'] in ([],[1]):go+=sign*a*(4*np.pi*length)*green(length)
        else:raise ValueError('Unsupported interaction chain')
    if count!=1:raise ValueError(f'Expected one central diffraction route, found {count}')
    return go+diffracted,go,diffracted

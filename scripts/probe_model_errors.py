"""Exploratory parameter-free reciprocal Fresnel policies, not accuracy references."""
import json,sys
from pathlib import Path
import numpy as np
from dielectric_model import coefficient,go_coefficient
from ray_wedge2d import fixture,green

POLICIES=('incident','mean_cosine','angle_bisector','geometric_cosine')

def prediction(source,receiver,epsilon,pol,policy):
    c=fixture(source,receiver,epsilon,pol)
    a,_=coefficient(c,'sionna-reciprocal',fresnel_policy=policy)
    s=np.linalg.norm(source);d=np.linalg.norm(receiver);sign=1 if pol=='Ez' else -1
    ud=sign*a*(4*np.pi*np.sqrt(s*d*(s+d)))*green(s)*np.exp(-2j*np.pi*d)/np.sqrt(d)
    go=0j
    for face in ('incident','reflection0','reflectionn'):
        g=go_coefficient(c,face)
        if g is not None:go+=sign*g[0]*(4*np.pi*g[1])*green(g[1])
    return go+ud,go,ud

def analyze(reference,raw):
    result=[]
    for row in json.loads(reference.read_text())['results']:
        if row['name'].startswith(('free','pec')):continue
        r=json.loads((raw/(row['name']+'_80.json')).read_text());epsilon=complex(*r['epsilon']);pol=r['polarization']
        ref=np.asarray(row['extrapolated_field']);ref=ref[...,0]+1j*ref[...,1]
        for policy in POLICIES:
            predicted=np.empty_like(ref);go=np.empty_like(ref)
            for i,s in enumerate(r['sources']):
                for j,d in enumerate(r['receivers']):predicted[i,j],go[i,j],_=prediction(s,d,epsilon,pol,policy)
            err=np.linalg.norm(predicted-ref)/np.linalg.norm(ref)
            residual=np.linalg.norm(predicted-ref)/np.linalg.norm(ref-go)
            result.append(dict(name=row['name'],policy=policy,total_rms=float(err),residual_rms=float(residual)))
    return result

if __name__=='__main__':
    result=analyze(Path(sys.argv[1]),Path(sys.argv[2]));Path(sys.argv[3]).write_text(json.dumps(result,indent=2))
    for r in result:print(r['name'],r['policy'],r['total_rms'],r['residual_rms'])

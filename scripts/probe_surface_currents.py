"""Uncoupled physical-optics current diagnostic, not a runtime patch or UAPO transcription."""
import json,sys
from pathlib import Path
import numpy as np
from scipy.special import hankel2
from wedge_bem_reference import WedgeBEM,green
from refinement_cases import SOURCES,RECEIVERS,MATERIALS
from run_maxwell_reference import pair

model=WedgeBEM(24,6,5)
def field(sources,receivers,eps,pol):
    d=model.points[:,None,:]-np.asarray(sources)[None,:,:];r=np.sqrt(np.sum(d*d,axis=-1));c=-np.sum(d*model.normals[:,None,:],axis=-1)/r
    incoming=green(model.k,r);derivative=.25j*model.k*hankel2(1,model.k*r)*np.sum(d*model.normals[:,None,:],axis=-1)/r
    q=np.sqrt(eps-1+c*c);R=(c-q)/(c+q) if pol=='Ez' else (eps*c-q)/(eps*c+q)
    illuminated=np.asarray(sources)@model.normals.T>0
    u=np.where(illuminated.T,(1+R)*incoming,0);dn=np.where(illuminated.T,(1-R)*derivative,0)
    S,K=model.operators(receivers,model.k);direct=green(model.k,np.linalg.norm(np.asarray(receivers)[:,None,:]-sources,axis=-1))
    return (direct+K@u-S@dn).T
rows=[]
for name,eps in MATERIALS.items():
    for pol in ('Ez','Hz'):
        a=field(SOURCES,RECEIVERS,eps,pol);b=field(RECEIVERS,SOURCES,eps,pol).T
        rows.append(dict(name=name+'_'+pol,field=pair(.5*(a+b)),raw_reciprocity_rms=float(np.linalg.norm(a-b)/np.linalg.norm(a))))
Path(sys.argv[1]).write_text(json.dumps(dict(scope='Reciprocal projection of uncoupled local Fresnel physical-optics face currents; excludes coupled material-face solve',results=rows),indent=2))

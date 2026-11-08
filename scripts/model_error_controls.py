"""Extra numerical controls for the independent BIE, with no fitted ray data."""
import hashlib,json,time
from pathlib import Path
import numpy as np
from wedge_bem_reference import WedgeBEM
from run_maxwell_reference import SOURCES,RECEIVERS,MATERIALS
from run_model_error_reference import SWEEP_SOURCES,SWEEP_RECEIVERS,SWEEP_MATERIALS,pair

def main(output):
    output.mkdir(parents=True,exist_ok=True)
    jobs=[]
    for name in ('concrete','absorbing'):
        for pol in ('Ez','Hz'):
            jobs.append((f'reverse_{name}_{pol}',48,5.,RECEIVERS,SOURCES,MATERIALS[name],pol))
    for name in ('holdout_low','holdout_high'):
        jobs.append((f'tail_{name}_Hz',36,8.,SWEEP_SOURCES,SWEEP_RECEIVERS,SWEEP_MATERIALS[name],'Hz'))
    jobs.append(('rounded_concrete_Hz',36,5.,SWEEP_SOURCES.astype(np.float32).astype(float),SWEEP_RECEIVERS.astype(np.float32).astype(float),MATERIALS['concrete'],'Hz'))
    models={}
    for name,p,tail,sources,receivers,epsilon,pol in jobs:
        target=output/(name+'.json')
        if target.exists():continue
        print('START',name,flush=True)
        if (p,tail) not in models:models[p,tail]=WedgeBEM(p,6.,tail)
        u,meta=models[p,tail].solve(sources,receivers,epsilon,pol)
        target.write_text(json.dumps(dict(**meta,name=name,field=pair(u),sources=sources.tolist(),receivers=receivers.tolist(),source_sha256=hashlib.sha256(Path(__file__).with_name('wedge_bem_reference.py').read_bytes()).hexdigest()),indent=2),encoding='utf-8')
        print('DONE',name,flush=True)

if __name__=='__main__':
    import sys
    main(Path(sys.argv[1]))

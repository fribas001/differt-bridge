"""Independent BIE controls, new materials/angles, and electrical-distance sweeps."""
import argparse,hashlib,json,time
from pathlib import Path
import numpy as np
from wedge_bem_reference import WedgeBEM
from run_maxwell_reference import SOURCES,RECEIVERS,MATERIALS
from maxwell2d_reference import free_green,pec_green

ANGLES=np.arange(5.,266.,5.)
SOURCE_ANGLES=np.array([17.,73.,128.,207.,252.])
def polar(angle,radius):
    t=np.deg2rad(angle+90);return np.stack([radius*np.cos(t),radius*np.sin(t)],axis=-1)
SWEEP_SOURCES=polar(SOURCE_ANGLES,np.array([2.8,3.2,3.1,2.7,3.4]))
SWEEP_RECEIVERS=polar(ANGLES,4.)
SWEEP_MATERIALS={'concrete':MATERIALS['concrete'],'absorbing':MATERIALS['absorbing'],'holdout_low':2.5-.35j,'holdout_high':8.-3j}
pair=lambda a:np.stack([a.real,a.imag],axis=-1).tolist()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('output',type=Path);ap.add_argument('--campaign',choices=['controls','sweep','distance'],required=True);ap.add_argument('--panels',default='16,24,36');args=ap.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    if args.campaign=='controls':
        groups=[('control',SOURCES,RECEIVERS,6.,5.,{'air':1+0j,'pec':1+0j,**MATERIALS}),('tail',SOURCES,RECEIVERS,6.,8.,{'concrete':MATERIALS['concrete']})]
    elif args.campaign=='sweep':groups=[('sweep',SWEEP_SOURCES,SWEEP_RECEIVERS,6.,5.,SWEEP_MATERIALS)]
    else:groups=[('scale'+str(s),SOURCES*s,RECEIVERS*s,4*s+2.,5.,{k:MATERIALS[k] for k in ('concrete','absorbing')}) for s in (1,2,4)]
    for panels in map(int,args.panels.split(',')):
        for group,sources,receivers,core,tail,mats in groups:
            model=None
            for name,epsilon in mats.items():
                for pol in ('Ez','Hz'):
                    label=f'{group}_{name}_{pol}_{panels}';target=args.output/(label+'.json')
                    if target.exists():continue
                    if model is None:model=WedgeBEM(panels,core,tail)
                    print('START',label,flush=True);start=time.perf_counter()
                    boundary='pec' if name=='pec' else 'dielectric'
                    u,meta=model.solve(sources,receivers,epsilon,pol,boundary)
                    exact=None
                    if name in ('air','pec'):
                        exact=np.array([[free_green(s,r) if name=='air' else pec_green(s,r,pol) for r in receivers] for s in sources])
                    result=dict(**meta,group=group,material=name,sources=np.asarray(sources).tolist(),receivers=np.asarray(receivers).tolist(),field=pair(u),source_sha256=hashlib.sha256(Path(__file__).with_name('wedge_bem_reference.py').read_bytes()).hexdigest(),elapsed_seconds=time.perf_counter()-start)
                    if exact is not None:result['analytic_rms_error']=float(np.linalg.norm(u-exact)/np.linalg.norm(exact));result['analytic']=pair(exact)
                    target.write_text(json.dumps(result,indent=2),encoding='utf-8')
                    print('DONE',label,round(result['elapsed_seconds'],2),result.get('analytic_rms_error'),flush=True)
            del model

if __name__=='__main__':main()

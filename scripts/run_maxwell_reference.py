"""Convergence and analytic controls for an independent solid dielectric wedge."""
import argparse,hashlib,json,time
from pathlib import Path
import numpy as np
import scipy
from maxwell2d_reference import Maxwell2D,free_green,pec_green

SOURCES=np.array([[-2.5,1.5],[-1.5,2.5],[-2.5,-1.5],[1.5,-2.5],[-.5,2.5],[2.5,-.5]])
RECEIVERS=np.array([[-4.,0],[-4.,-1],[-3.5,-2],[-2,-3.5],[0,-4.],[1,-4.],[2,-3.5],[3.5,-2],[4,-.5],[-.5,4],[-2,3.5],[-3.5,2]])
MATERIALS={'concrete':5.24-1j*.123086944/(2*np.pi*3.5e9*8.8541878188e-12),'lossy':4-2j,'absorbing':5.24-6j}
pair=lambda a:np.stack([a.real,a.imag],axis=-1).tolist()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('output',type=Path);ap.add_argument('--grids',default='40,60,80');ap.add_argument('--only',default='');ap.add_argument('--pml',type=float,default=1.5);args=ap.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    configs=[('free','Ez','free',1+0j),('pec','Ez','pec',1+0j),('pec','Hz','pec',1+0j)]
    configs += [(name,pol,'wedge',epsilon) for name,epsilon in MATERIALS.items() for pol in ('Ez','Hz')]
    selected=set(args.only.split(',')) if args.only else None
    for ppw in map(int,args.grids.split(',')):
        for name,pol,geometry,epsilon in configs:
            label=f'{name}_{pol}_{ppw}';path=args.output/(label+'.json')
            if selected and name+'_'+pol not in selected:continue
            if path.exists():print('EXISTING',label,flush=True);continue
            print('START',label,flush=True);start=time.perf_counter()
            model=Maxwell2D(ppw=ppw,inner=5.,pml=args.pml,epsilon=epsilon,geometry=geometry,polarization=pol)
            fields,residual=model.solve(SOURCES,np.vstack([RECEIVERS,SOURCES]))
            outer=fields[:,:len(RECEIVERS)];port_matrix=fields[:,len(RECEIVERS):]
            reciprocity=np.max(abs(port_matrix-port_matrix.T))/np.max(abs(port_matrix))
            exact=None
            if name in ('free','pec'):
                exact=np.array([[free_green(s,r) if name=='free' else pec_green(s,r,pol) for r in RECEIVERS] for s in SOURCES])
            result=dict(**model.metadata,source_sha256=hashlib.sha256(Path(__file__).with_name('maxwell2d_reference.py').read_bytes()).hexdigest(),numpy=np.__version__,scipy=scipy.__version__,sources=SOURCES.tolist(),receivers=RECEIVERS.tolist(),field=pair(outer),ports=pair(port_matrix),linear_residual=residual,reciprocity_residual=float(reciprocity),analytic=pair(exact) if exact is not None else None,elapsed_seconds=time.perf_counter()-start)
            if exact is not None:result['analytic_rms_relative']=float(np.linalg.norm(outer-exact)/np.linalg.norm(exact))
            path.write_text(json.dumps(result,indent=2),encoding='utf-8')
            print('DONE',label,'seconds',round(result['elapsed_seconds'],2),'residual',residual,'analytic',result.get('analytic_rms_relative'),flush=True)
            del model

if __name__=='__main__':main()

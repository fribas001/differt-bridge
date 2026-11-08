"""Fresh independent FDFD validation, never used to construct the BIE output."""
import argparse,hashlib,json,time
from pathlib import Path
import numpy as np
from maxwell2d_reference import Maxwell2D
from refinement_cases import SOURCES,RECEIVERS,MATERIALS
from run_maxwell_reference import pair

def main():
    ap=argparse.ArgumentParser();ap.add_argument('output',type=Path);ap.add_argument('--grids',default='40,60,80');ap.add_argument('--pml',type=float,default=1.5);ap.add_argument('--only',default='');args=ap.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    for ppw in map(int,args.grids.split(',')):
        for name,eps in MATERIALS.items():
            for pol in ('Ez','Hz'):
                label=f'{name}_{pol}'
                if args.only and label not in args.only.split(','):continue
                target=args.output/f'{label}_{ppw}.json'
                if target.exists():continue
                print('START',label,ppw,flush=True);start=time.perf_counter()
                solver=Maxwell2D(ppw=ppw,inner=5.,pml=args.pml,epsilon=eps,polarization=pol)
                u,residual=solver.solve(SOURCES,np.vstack([RECEIVERS,SOURCES]));ports=u[:,len(RECEIVERS):]
                result=dict(**solver.metadata,source_sha256=hashlib.sha256(Path(__file__).with_name('maxwell2d_reference.py').read_bytes()).hexdigest(),sources=SOURCES.tolist(),receivers=RECEIVERS.tolist(),field=pair(u[:,:len(RECEIVERS)]),linear_residual=residual,reciprocity_residual=float(np.max(abs(ports-ports.T))/np.max(abs(ports))),elapsed_seconds=time.perf_counter()-start)
                target.write_text(json.dumps(result,indent=2));print('DONE',label,ppw,round(result['elapsed_seconds'],2),flush=True)
                del solver

if __name__=='__main__':main()

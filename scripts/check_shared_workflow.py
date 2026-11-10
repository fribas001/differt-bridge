"""Repeat a small native RT 2.2 + DiffeRT calculation without touching evidence."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from shared_sionna import DEFAULT_PYTHON, command, worker_environment


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace',type=Path,required=True)
    p.add_argument('--output',type=Path)
    p.add_argument('--blender',default='C:/Program Files/Blender Foundation/Blender 5.2/blender.exe')
    p.add_argument('--run-comparison',action='store_true')
    a=p.parse_args();root=a.workspace.resolve()
    out=a.output.resolve() if a.output else root/'work'/('rt22-check-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f'))
    out.mkdir(parents=True,exist_ok=False)
    temp=out/'temp';temp.mkdir()
    env=worker_environment(dict(os.environ,TEMP=str(temp),TMP=str(temp),DIFFERT_ARITHMETIC_PROFILE='native'))
    records=[]
    def run(label,args):
        with (out/(label+'.log')).open('w',encoding='utf-8') as log:
            result=subprocess.run(list(map(str,args)),cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT)
        records.append(dict(label=label,command=list(map(str,args)),returncode=result.returncode))
        if result.returncode:raise RuntimeError(label+' failed; see '+str(out/(label+'.log')))
    scripts=Path(__file__).resolve().parent
    receipt=dict(profile='shared-sionna-rt-2.2-native',output=str(out),processes=records,status='failed')
    try:
        run('runtime',[DEFAULT_PYTHON,'-I','-B','-m','codex_sionna_runtime','--check'])
        differt=root/'work/runtime/Scripts/python.exe'
        run('paired',[differt,'-B',scripts/'run_diffraction.py','--differt-python',differt,'--sionna-python',DEFAULT_PYTHON,
                      '--output',out/'paired','--only','wedge_v,wedge_h,wedge_reciprocal,diffraction_disabled,reflection_diffraction'])
        if a.run_comparison:
            source=Path(os.environ['APPDATA'])/'Blender Foundation/Blender/5.2/extensions/user_default/sionnart_bridge'
            for case in ('free_space','ground_reflection','blocked_los','receiver_motion'):
                run('blender-'+case,[a.blender,'--background','--factory-startup','--python-exit-code','1',
                                    '--python',scripts/'blender_comparison_check.py','--',case,out/case,source,DEFAULT_PYTHON,differt])
            run('blender-batch',[a.blender,'--background','--factory-startup','--python-exit-code','1',
                                '--python',scripts/'blender_shared_batch_check.py','--',out/'batch',source,DEFAULT_PYTHON])
        receipt['status']='passed'
    finally:
        (out/'verification.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
        print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()

"""Run an explicit research profile after codex_sionna_runtime has initialized."""
import argparse,json,os,runpy,sys
from pathlib import Path

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--profile',choices=('phase','reciprocal'),required=True)
    p.add_argument('--receipt',type=Path)
    p.add_argument('arguments',nargs=argparse.REMAINDER)
    a=p.parse_args();args=a.arguments
    if args[:1]==['--']:args=args[1:]
    if not args:p.error('A script or -m module is required after --')
    from codex_sionna_runtime import configure_verified_runtime
    configure_verified_runtime()
    from rt22_profiles import install
    detail=install(a.profile)
    if a.receipt:
        a.receipt.parent.mkdir(parents=True,exist_ok=True);a.receipt.write_text(json.dumps(detail,indent=2))
    print('RT22_RESEARCH_PROFILE',a.profile,detail['manifest_sha256'],flush=True)
    if args[0]=='-m':
        sys.argv=args[1:];sys.path.insert(0,str(Path.cwd()));runpy.run_module(args[1],run_name='__main__',alter_sys=True)
    else:
        path=Path(args[0]).resolve(strict=True);sys.path.insert(0,str(path.parent))
        sys.argv=[str(path),*args[1:]];runpy.run_path(str(path),run_name='__main__')

if __name__=='__main__':main()

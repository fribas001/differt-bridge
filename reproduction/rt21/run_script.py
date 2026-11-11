"""Preserve script/module arguments under the restored isolated interpreter."""
from pathlib import Path
import runpy,sys
args=sys.argv[1:]
if args[0]=='-m':
    sys.argv=args[1:];sys.path.insert(0,str(Path.cwd()));runpy.run_module(args[1],run_name='__main__',alter_sys=True)
else:
    path=Path(args[0]).resolve(strict=True);sys.path.insert(0,str(path.parent))
    sys.argv=[str(path),*args[1:]];runpy.run_path(str(path),run_name='__main__')

"""Lazy, opt-in runtime profile. Native startup imports no scientific packages."""
import os,sys

def activate():
    profile=os.environ.get('RADIO_DIELECTRIC_PROFILE','native')
    if profile=='native':return
    if profile!='reciprocal':
        # site.py otherwise logs .pth errors and silently continues in native mode.
        sys.stderr.write('Unknown RADIO_DIELECTRIC_PROFILE: '+profile+'\n');os._exit(78)
    import importlib.abc,importlib.machinery
    targets={'sionna.rt':'sionna','differt_backend':'differt'}
    class Loader(importlib.abc.Loader):
        def __init__(self,original,engine):self.original=original;self.engine=engine
        def create_module(self,spec):return self.original.create_module(spec)
        def exec_module(self,module):
            self.original.exec_module(module)
            from reciprocal_corrections import install
            detail=install(self.engine)
            sys.stderr.write('RADIO_DIELECTRIC_PROFILE=reciprocal activated for '+self.engine+'\n')
            # Write an auditable receipt only to an explicitly requested location.
            receipt=os.environ.get('RADIO_DIELECTRIC_RECEIPT')
            if receipt:
                import json
                from pathlib import Path
                destination=Path(receipt)
                if destination.is_dir():destination=destination/(self.engine+'_profile.json')
                destination.write_text(json.dumps(detail,indent=2),encoding='utf-8')
    class Finder(importlib.abc.MetaPathFinder):
        def find_spec(self,fullname,path=None,target=None):
            if fullname not in targets:return None
            spec=importlib.machinery.PathFinder.find_spec(fullname,path)
            if spec is None:return None
            spec.loader=Loader(spec.loader,targets[fullname]);return spec
    sys.meta_path.insert(0,Finder())

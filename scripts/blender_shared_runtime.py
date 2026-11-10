"""Select the verified shared RT interpreter in this Blender session only.

Launch through Launch_Workflow.ps1 / Launch_Diffraction.ps1. No preferences,
saved scenes, installed extensions or engine packages are written by this file.
"""
import importlib
from pathlib import Path
import sys
import bpy
from bpy.app.handlers import persistent

sys.path.insert(0,str(Path(__file__).resolve().parent))
from shared_sionna import DEFAULT_PYTHON, attach_bridge, is_shared, research_profile

profile=research_profile()
if not DEFAULT_PYTHON.is_file() or not is_shared(DEFAULT_PYTHON):
    raise RuntimeError('Verified shared RT environment missing: '+str(DEFAULT_PYTHON))
bridge=importlib.import_module('bl_ext.user_default.sionnart_bridge')
attach_bridge(bridge)

@persistent
def select_shared_runtime(_unused=None):
    for scene in bpy.data.scenes:
        settings=getattr(scene,'sionna_bridge',None)
        if settings is None:continue
        settings.runtime_mode='EXTERNAL'
        settings.sionna_python=str(DEFAULT_PYTHON)
        settings.sionna_site_packages=''
        settings.drjit_libllvm_path=''
        settings.runtime_probe_json=''
    print('Shared Sionna RT 2.2 '+profile+' CPU profile selected; historical results are unchanged.',flush=True)

bpy.app.handlers.load_post.append(select_shared_runtime)
select_shared_runtime()

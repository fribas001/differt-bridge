"""Explicit, source-guarded RT 2.2 research profiles; mutations are process-only."""
import hashlib
import importlib
import inspect
import json
import linecache
import os
from pathlib import Path
import sys
import textwrap

ROOT=Path(__file__).resolve().parent
_ACTIVE=None

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def verify():
    from importlib.metadata import version
    import mitsuba as mi
    import sionna.rt as rt
    expected={'sionna-rt':'2.2.0','mitsuba':'3.9.1','drjit':'1.5.0','numpy':'2.5.4','scipy':'1.18.1'}
    actual={name:version(name) for name in expected}
    if actual!=expected or mi.variant()!='llvm_ad_mono_polarized':
        raise RuntimeError('Research profile requires the audited RT 2.2 Windows CPU stack')
    manifest=json.loads((ROOT/'manifest.json').read_text())
    for name,digest in manifest['native_files'].items():
        if sha(Path(rt.__file__).parent/name)!=digest:raise RuntimeError('Unsupported native source: '+name)
    for name,digest in manifest['payload'].items():
        if sha(ROOT/name)!=digest:raise RuntimeError('Research payload changed: '+name)
    return actual,manifest

def helpers():
    parent=importlib.import_module('sionna.rt.path_solvers')
    for name in ('_bridge_segment_policy','_bridge_geometry'):
        module=importlib.import_module('.'+name,__name__)
        fullname='sionna.rt.path_solvers.'+name
        if fullname in sys.modules and sys.modules[fullname] is not module:
            raise RuntimeError('Competing geometry helper already loaded: '+fullname)
        sys.modules[fullname]=module;setattr(parent,name,module)

def compile_method(cls,name,replacements,extra=None):
    original=getattr(cls,name);source=textwrap.dedent(inspect.getsource(original))
    for before,after in replacements:
        if source.count(before)!=1:raise RuntimeError('Unexpected source anchor: '+cls.__name__+'.'+name)
        source=source.replace(before,after,1)
    filename='<rt22-research-'+cls.__name__+'.'+name+'>'
    linecache.cache[filename]=(len(source),None,source.splitlines(True),filename)
    namespace=dict(vars(importlib.import_module(cls.__module__)),**(extra or {}))
    exec(compile(source,filename,'exec'),namespace)
    return namespace[name]

def historical_field_methods():
    import sionna.rt.path_solvers.field_calculator as fc
    namespace=vars(fc).copy();payload=ROOT/'historical_fields.py'
    exec(compile(payload.read_text(),str(payload),'exec'),namespace)
    return [(fc.FieldCalculator,name,namespace[name]) for name in ('__call__','_compute_cir','_update_field')]

def phase():
    from sionna.rt.path_solvers.path_solver import PathSolver
    from sionna.rt.path_solvers.image_method import ImageMethod
    from sionna.rt.path_solvers.sb_candidate_generator import SBCandidateGenerator
    from sionna.rt.path_solvers.sb_deterministic import SBDeterministicCandidateGenerator
    from ._bridge_segment_policy import preliminary_minimum
    # Preserve 2.2 code (including its source-box support) and change only the
    # three preliminary segment gates. Final full-mesh checks remain mandatory.
    edits=[]
    for cls,name in ((ImageMethod,'_backtrack'),(SBCandidateGenerator,'_los'),(SBDeterministicCandidateGenerator,'_los')):
        method=compile_method(cls,name,[('length > MIN_SEGMENT_LENGTH','length > preliminary_minimum(MIN_SEGMENT_LENGTH)')],{'preliminary_minimum':preliminary_minimum})
        edits.append((cls,name,method))
    guard='''        # Check that the scene is all set for simulations'''
    insert='''        from ._bridge_geometry import geometry_profile
        from ._bridge_segment_policy import segment_profile
        if geometry_profile() != 'unshifted_float64' or segment_profile() != 'shared_1mm':
            raise ValueError('Phase profile requires unshifted geometry and shared_1mm segments')
        if diffuse_reflection or refraction or diffraction:
            raise ValueError('Phase alignment supports LoS/specular paths only')

'''
    # inspect.getsource is dedented: method body has four-space indentation.
    guard=textwrap.dedent(guard).rstrip()
    before='    '+guard
    insert=textwrap.dedent(insert)
    insert=textwrap.indent(insert,'    ')
    repair='''    from ._bridge_geometry import repair_paths
    paths_buffer = repair_paths(scene.mi_scene, paths_buffer, src_positions, tgt_positions)

'''
    method=compile_method(PathSolver,'__call__',[(before,insert+before),
          ('    # Compute channel coefficients and delays',repair+'    # Compute channel coefficients and delays')])
    edits.append((PathSolver,'__call__',method))
    edits.extend(historical_field_methods())
    # All guarded source transformations compile before attaching any method.
    for cls,name,method in edits:setattr(cls,name,method)
    return {'geometry':'unshifted_float64','segments':'shared_1mm','field_arithmetic':'RT 2.1 operation order on RT 2.2 data structures',
            'scope':'CPU LoS/specular paths; native 2.2 discovery, complete-mesh visibility, unchanged threshold'}

def reciprocal():
    import reciprocal_corrections as old
    # These lower-level field functions keep their original source guards.
    # This is a separate 2.2 installer, not a relaxed 2.1 version check.
    methods=historical_field_methods()
    result=old.install_sionna_fields()
    for cls,name,method in methods:setattr(cls,name,method)
    result['field_arithmetic']='RT 2.1 operation order on RT 2.2 data structures'
    result['geometry']=old.install_sionna_geometry()
    from sionna.rt.path_solvers.image_method import ImageMethod
    previous=ImageMethod.__call__
    def checked(self,*args,**kwargs):
        if kwargs.get('src_boxes') is not None:
            raise ValueError('Reciprocal research does not support source exclusion boxes')
        return previous(self,*args,**kwargs)
    ImageMethod.__call__=checked
    from reciprocal_boundary import install_boundary_merge
    result['boundary_convention']=install_boundary_merge('sionna')
    result.update(profile='reciprocal',engine='sionna',runtime='2.2.0',installer='project-local rt22_profiles')
    # Existing diagnostic worker calls install() again; return this exact receipt
    # rather than reapplying wrappers or bypassing guards on another version.
    old._INSTALLED['sionna']=result
    return result

def install(profile):
    global _ACTIVE
    if profile not in ('phase','reciprocal'):raise ValueError('Unknown research profile: '+profile)
    if _ACTIVE:
        if _ACTIVE['profile']!=profile:raise RuntimeError('Start a fresh process to change research profiles')
        return _ACTIVE
    versions,manifest=verify();helpers()
    os.environ.update(RADIO_RT22_PROFILE=profile,
        RADIO_SEGMENT_PROFILE='shared_1mm' if profile=='phase' else 'native',
        SIONNA_GEOMETRY_PROFILE='unshifted_float64' if profile=='phase' else 'native',
        RADIO_DIELECTRIC_PROFILE='reciprocal' if profile=='reciprocal' else 'native')
    detail=phase() if profile=='phase' else reciprocal()
    _ACTIVE=dict(profile=profile,versions=versions,details=detail,manifest_sha256=sha(ROOT/'manifest.json'),
                 installation='Process-local; shared packages and native-library bootstrap unchanged')
    return _ACTIVE

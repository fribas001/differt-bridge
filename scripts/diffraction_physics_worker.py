"""Run field-formula interventions in an isolated process; never install them.

Sionna assembly candidate is the algebra discussed in upstream issues 84/85.
It must be assessed with a signed independent reference and GO transitions.
"""
import hashlib
import inspect
import json
import os
from pathlib import Path
import sys
import textwrap


def install_assembly():
    import sionna.rt.radio_materials.radio_material as rm
    original=rm.RadioMaterial._diffraction_matrix
    source=textwrap.dedent(inspect.getsource(original))
    start=source.index('    # For wide exterior angles,')
    end=source.index('    # Embed into to_world transformation',start)
    replacement='''    # Diagnostic KP-compatible assembly; production code is untouched.
    d12 = d1 + d2
    real = (-mi.Matrix2f(d12.real, 0., 0., d12.real)
            + r_0_real*d4.real - r_0_imag*d4.imag
            + r_n_real*d3.real - r_n_imag*d3.imag)
    imag = (-mi.Matrix2f(d12.imag, 0., 0., d12.imag)
            + r_0_imag*d4.real + r_0_real*d4.imag
            + r_n_imag*d3.real + r_n_real*d3.imag)

'''
    code=source[:start]+replacement+source[end:]
    namespace=vars(rm).copy();exec(compile(code,'<diagnostic-kp-assembly>','exec'),namespace)
    rm.RadioMaterial._diffraction_matrix=namespace['_diffraction_matrix']
    return dict(original_source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                diagnostic_source_sha256=hashlib.sha256(code.encode()).hexdigest(),
                scope='In-process field assembly only; no ray search, visibility, installed file or runtime change')


def main():
    profile=sys.argv.pop(1)
    if profile not in ('native','kp_assembly','kp_depth'):raise ValueError(profile)
    engine=sys.argv[1];out=Path(sys.argv[3]);out.mkdir(parents=True,exist_ok=True)
    temporary=(out/'temp').resolve();temporary.mkdir(exist_ok=True)
    os.environ.update(TEMP=str(temporary),TMP=str(temporary))
    import tempfile
    tempfile.tempdir=str(temporary)
    detail={}
    if profile in ('kp_assembly','kp_depth'):
        if engine!='sionna':raise ValueError('Sionna-only intervention')
        import mitsuba as mi
        mi.set_variant('llvm_ad_mono_polarized')
        detail=install_assembly()
        if profile=='kp_depth':detail['distance_intervention']=install_depth()
    (out/'intervention.json').write_text(json.dumps(dict(profile=profile,engine=engine,**detail),indent=2),encoding='utf-8')
    from diffraction_worker import main as run
    run()


def install_depth():
    import linecache
    import sionna.rt.path_solvers.field_calculator as fc
    original=fc.FieldCalculator._diffraction_compute_s_s_prime
    source=textwrap.dedent(inspect.getsource(original))
    marker='        none = active & (interaction_type == InteractionType.NONE)'
    assert source.count(marker)==1
    code=source.replace(marker,marker+'\n        active &= ~none  # Ignore padded vertices before accumulating distance.')
    filename='<diagnostic-active-segment-distance>'
    linecache.cache[filename]=(len(code),None,code.splitlines(True),filename)
    namespace=vars(fc).copy();exec(compile(code,filename,'exec'),namespace)
    fc.FieldCalculator._diffraction_compute_s_s_prime=namespace['_diffraction_compute_s_s_prime']
    return dict(original_source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                diagnostic_source_sha256=hashlib.sha256(code.encode()).hexdigest(),
                scope='In-process distance accumulation only; ignore NONE padding, preserve all active segments')


if __name__=='__main__':main()

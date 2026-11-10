import importlib.util
from pathlib import Path
from types import SimpleNamespace
import pytest

SCRIPTS=Path(__file__).resolve().parents[1]/'scripts'
spec=importlib.util.spec_from_file_location('shared_sionna', SCRIPTS/'shared_sionna.py')
runtime=importlib.util.module_from_spec(spec);spec.loader.exec_module(runtime)

@pytest.fixture
def shared(tmp_path):
    root=tmp_path/'shared runtime'
    helper=root/'Lib/site-packages/codex_sionna_runtime/__init__.py'
    helper.parent.mkdir(parents=True);helper.write_text('')
    return root/'Scripts/python.exe'

def test_script_arguments_and_environment(shared):
    args=['-B','some path/worker.py','--config','path with spaces.json']
    assert runtime.command(shared,args)==[str(shared),'-I','-B','-m','codex_sionna_runtime',*args[1:]]
    assert args[0]=='-B'
    env={'PATH':'keep','TEMP':'keep too','PYTHONPATH':'old packages','DRJIT_LIBLLVM_PATH':'old adapter'}
    result=runtime.worker_environment(env)
    assert 'PYTHONPATH' not in result and 'DRJIT_LIBLLVM_PATH' not in result
    assert result['PATH']=='keep' and result['TEMP']=='keep too'
    assert 'PYTHONPATH' in env

def test_fail_closed_on_scientific_profiles():
    with pytest.raises(ValueError,match='historical'):runtime.require_native(environment={'RADIO_SEGMENT_PROFILE':'shared_1mm'})
    with pytest.raises(ValueError,match='2.1'):runtime.require_native('reciprocal',{})

def test_legacy_and_module_commands(shared):
    assert runtime.command('legacy/python.exe',['-B','worker.py'])==['legacy/python.exe','-B','worker.py']
    assert runtime.command(shared,['-m','example','x'])[-3:]==['-m','example','x']
    assert runtime.command(shared,['-u','-B','worker.py'])[:6]==[str(shared),'-I','-B','-u','-m','codex_sionna_runtime']
    assert runtime.command(shared,['-I','-B','-m','codex_sionna_runtime','worker.py']).count('codex_sionna_runtime')==1

def test_inline_probe_and_scoped_subprocess(shared):
    calls=[]
    delegate=SimpleNamespace(run=lambda *a,**k:calls.append((a,k)),Popen=lambda *a,**k:calls.append((a,k)))
    wrapped=runtime.BridgeSubprocess(delegate)
    wrapped.run([str(shared),'-c','print(1)'],cwd='unchanged',env={'DRJIT_LIBLLVM_PATH':'old'})
    args,kw=calls[-1]
    assert args[0][-2].endswith('shared_sionna_inline.py') and args[0][-1]=='print(1)'
    assert kw['cwd']=='unchanged' and 'DRJIT_LIBLLVM_PATH' not in kw['env']
    wrapped.Popen(['differt/python.exe','worker.py'],env={'X':'Y'})
    assert calls[-1]==((['differt/python.exe','worker.py'],),{'env':{'X':'Y'}})

@pytest.mark.parametrize('profile',['phase','reciprocal'])
def test_explicit_research_dispatch(shared,profile):
    env={'RADIO_RT22_PROFILE':profile,'RADIO_DIELECTRIC_PROFILE':'reciprocal' if profile=='reciprocal' else 'native',
         'SIONNA_GEOMETRY_PROFILE':'unshifted_float64' if profile=='phase' else 'native',
         'RADIO_SEGMENT_PROFILE':'shared_1mm' if profile=='phase' else 'native',
         'DRJIT_LIBLLVM_PATH':'old adapter','PYTHONPATH':'old runtime'}
    clean=runtime.worker_environment(env)
    assert runtime.research_profile(clean)==profile and 'DRJIT_LIBLLVM_PATH' not in clean and 'PYTHONPATH' not in clean
    cmd=runtime.command(shared,['-B','script with spaces.py','--argument','value'],profile=profile)
    assert cmd[5].endswith('rt22_research_worker.py')
    assert cmd[6:]==['--profile',profile,'--','script with spaces.py','--argument','value']
    env['RADIO_SEGMENT_PROFILE']='invalid'
    with pytest.raises(ValueError):runtime.worker_environment(env)

def test_unrequested_correction_never_silently_activates():
    with pytest.raises(ValueError):runtime.worker_environment({'RADIO_DIELECTRIC_PROFILE':'reciprocal'})
    with pytest.raises(ValueError):runtime.worker_environment({'RADIO_RT22_PROFILE':'unknown'})

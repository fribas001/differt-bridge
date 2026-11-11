"""Project-local dispatch for the verified shared Windows CPU RT environment.

Shared package files are never changed. Research profiles are explicit and
process-local; legacy interpreters remain supported. No scientific imports here.
"""
import os
from pathlib import Path
import subprocess

DEFAULT_PYTHON = Path(os.environ.get('SIONNA_SHARED_PYTHON',
    str(Path.home() / 'Documents/Codex/shared-envs/sionna-rt-2.2-py312/Scripts/python.exe')))
HELPER = 'codex_sionna_runtime'


def is_shared(python):
    root = Path(python).resolve().parent.parent
    return (root / 'Lib/site-packages/codex_sionna_runtime/__init__.py').is_file()


def require_native(profile='native', environment=None):
    if profile != 'native':
        raise ValueError('This entry point supports only the native project profile. '
                         'Restore the isolated RT 2.1 recovery kit for historical diagnostics.')
    env = os.environ if environment is None else environment
    if env.get('RADIO_RT22_PROFILE','native') not in ('','native'):
        raise ValueError('Native diagnostics require RADIO_RT22_PROFILE=native')
    for key in ('RADIO_DIELECTRIC_PROFILE', 'SIONNA_GEOMETRY_PROFILE', 'RADIO_SEGMENT_PROFILE'):
        if env.get(key, 'native') not in ('', 'native'):
            raise ValueError(f'{key}={env[key]} needs an explicit research profile or historical runtime; '
                             'start the shared native workflow in a fresh process.')


def research_profile(environment=None):
    env=os.environ if environment is None else environment
    profile=env.get('RADIO_RT22_PROFILE','native')
    if profile not in ('native','phase','reciprocal'):raise ValueError('Unknown RADIO_RT22_PROFILE: '+profile)
    if profile=='native':require_native(environment=env)
    else:
        expected={'RADIO_SEGMENT_PROFILE':'shared_1mm' if profile=='phase' else 'native',
                  'SIONNA_GEOMETRY_PROFILE':'unshifted_float64' if profile=='phase' else 'native',
                  'RADIO_DIELECTRIC_PROFILE':'reciprocal' if profile=='reciprocal' else 'native'}
        for key,value in expected.items():
            if env.get(key,'native')!=value:raise ValueError(f'{profile} profile requires {key}={value}')
    return profile


def worker_environment(environment=None):
    env = dict(os.environ if environment is None else environment)
    research_profile(env)
    # The bootstrap is the only native-library initializer. Never inherit a
    # Blender site-packages directory, an old ELF adapter, or an injected helper.
    for key in ('PYTHONPATH', 'PYTHONHOME', 'DRJIT_LIBLLVM_PATH', 'SIONNA_SITE_PACKAGES'):
        env.pop(key, None)
    env.update(PYTHONNOUSERSITE='1', PYTHONDONTWRITEBYTECODE='1')
    return env


def command(python, arguments, profile=None):
    """Preserve script/module arguments, wrapping shared-interpreter children."""
    args = list(map(str, arguments))
    if not is_shared(python):
        return [str(python), *args]
    unbuffered = False
    while args and args[0] in ('-I', '-B', '-u'):
        unbuffered = args.pop(0) == '-u' or unbuffered
    prefix = [str(python), '-I', '-B', *(['-u'] if unbuffered else [])]
    if args[:2] == ['-m', HELPER]:
        return [*prefix, *args]
    if args[:1] == ['-c']:
        args = [str(Path(__file__).with_name('shared_sionna_inline.py')), *args[1:]]
    selected=research_profile() if profile is None else profile
    if selected not in ('native','phase','reciprocal'):raise ValueError('Unsupported shared profile: '+selected)
    if selected!='native':
        args=[str(Path(__file__).with_name('rt22_research_worker.py')),'--profile',selected,'--',*args]
    return [*prefix, '-m', HELPER, *args]


class BridgeSubprocess:
    """Wrap only one Blender add-on's subprocess attribute, never the module globally.

    This covers path, 2D/3D map and HDF5 workers, plus the Runtime Test button.
    Other engines and Blender's interpreter remain untouched.
    """
    def __init__(self, delegate=subprocess):
        self.delegate = delegate

    def __getattr__(self, name):
        return getattr(self.delegate, name)

    def _call(self, method, args, *positional, **kwargs):
        if isinstance(args, (list, tuple)) and args and is_shared(args[0]):
            kwargs['env'] = worker_environment(kwargs.get('env'))
            args = command(args[0], args[1:],profile=research_profile(kwargs['env']))
            print('SHARED_SIONNA_WORKER', args[:6], flush=True)
        return getattr(self.delegate, method)(args, *positional, **kwargs)

    def Popen(self, args, *positional, **kwargs):
        return self._call('Popen', args, *positional, **kwargs)

    def run(self, args, *positional, **kwargs):
        return self._call('run', args, *positional, **kwargs)


def attach_bridge(bridge):
    """Session-only integration, also safe for factory-startup Blender tests."""
    if isinstance(bridge.subprocess, BridgeSubprocess):
        return
    bridge.subprocess = BridgeSubprocess(bridge.subprocess)
    previous = bridge._sionna_worker_environment

    def environment(settings, python_executable=None):
        if python_executable and is_shared(python_executable):
            return worker_environment(), None
        return previous(settings, python_executable)

    bridge._sionna_worker_environment = environment

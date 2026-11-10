"""Verify explicit RT 2.2 research profiles in fresh, isolated worker processes."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
from shared_sionna import DEFAULT_PYTHON, command, worker_environment


def profile_environment(profile, base=None):
    env = dict(os.environ if base is None else base)
    env.update(RADIO_RT22_PROFILE=profile,
               RADIO_DIELECTRIC_PROFILE='reciprocal' if profile == 'reciprocal' else 'native',
               RADIO_SEGMENT_PROFILE='shared_1mm' if profile == 'phase' else 'native',
               SIONNA_GEOMETRY_PROFILE='unshifted_float64' if profile == 'phase' else 'native',
               DIFFERT_ARITHMETIC_PROFILE='sionna_order' if profile == 'phase' else 'native',
               DIFFERT_FIELD_PRECISION='float32', DIFFERT_DIFFRACTION_GEOMETRY='validated',
               OPENBLAS_NUM_THREADS='1')
    return worker_environment(env)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', type=Path, required=True)
    p.add_argument('--output', type=Path)
    p.add_argument('--blender', default='C:/Program Files/Blender Foundation/Blender 5.2/blender.exe')
    p.add_argument('--run-comparison', action='store_true')
    a = p.parse_args()
    root = a.workspace.resolve()
    scripts = Path(__file__).resolve().parent
    out = a.output.resolve() if a.output else root/'work'/('r22-check-'+datetime.now(timezone.utc).strftime('%m%d-%H%M%S-%f'))
    out.mkdir(parents=True, exist_ok=False)
    temp = out/'temp'
    temp.mkdir()
    records = []
    receipt = dict(status='failed', processes=records, output=str(out))
    def run(label, args, env):
        args = list(map(str, args))
        with (out/(label+'.log')).open('w', encoding='utf-8') as log:
            result = subprocess.run(args, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT)
        records.append(dict(label=label, command=args, returncode=result.returncode))
        if result.returncode:
            raise RuntimeError(label+' failed; see '+str(out/(label+'.log')))
    try:
        from diffraction_cases import base, write_scene
        scene = write_scene(base(), out/'fixture')
        for profile in ('phase', 'reciprocal'):
            env = profile_environment(profile, dict(os.environ, TEMP=str(temp), TMP=str(temp)))
            args = [scripts/'check_rt22_profile.py', '--profile', profile,
                    '--scene', scene, '--output', out/(profile+'-guards.json')]
            run(profile+'-guards', command(DEFAULT_PYTHON, args, profile=profile), env)
            if a.run_comparison:
                run(profile+'-blender', [a.blender, '--background', '--python-exit-code', '1',
                    '--python', scripts/'blender_research_check.py', '--', root, out/profile, profile, 'shared'], env)
        receipt['status'] = 'passed'
    finally:
        (out/'verification.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
        print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()

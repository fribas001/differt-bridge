"""Import the selected historical numerical tables; never run scientific solvers.

Maintainer tool. Ordinary notebook users already have the committed data.
Both roots must point to the preserved study directories described in data/README.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELECTION = {
    'focused_60ghz': ('vegetation', 'focused_solver_comparison_20261017',
                      ['results_table.csv', 'analysis.json', 'verification.json']),
    'multiple_diffraction_60ghz': ('vegetation', 'multidiffraction_20261017',
                                  ['results_table.csv', 'analysis.json', 'verification.json']),
    'edge_fullwave_60ghz': ('vegetation', 'edge_fullwave_20261017',
                           ['analysis.json', 'contract.json', 'verification.json', 'zero_contrast.json']),
    'ris_controls_23_8ghz': ('ris', 'RIS_Independent_Validation_238GHz_2026-10-13',
                            ['rt_comparison.csv', 'fullwave_comparison.csv', 'verification.json']),
}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def sanitize(value, counts):
    """Remove workstation-specific locations while retaining all numeric values."""
    if isinstance(value, dict):
        return {k: sanitize(v, counts) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize(v, counts) for v in value]
    if isinstance(value, str) and re.search(r'^(?:[A-Za-z]:[/\\]|/Users/|/home/)', value):
        counts.append(value)
        return '<historical-path>/' + value.replace('\\', '/').rsplit('/', 1)[-1]
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vegetation-root', type=Path, required=True)
    parser.add_argument('--ris-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'notebooks/data')
    args = parser.parse_args()
    roots = {'vegetation': args.vegetation_root, 'ris': args.ris_root}
    # Check all prerequisites before writing anything.
    inputs = [(study, folder, filename, roots[kind] / folder / filename)
              for study, (kind, folder, files) in SELECTION.items() for filename in files]
    missing = [str(path) for _, _, _, path in inputs if not path.is_file()]
    if missing:
        parser.error('Missing source files: ' + ', '.join(missing))
    entries = []
    for study, folder, filename, source in inputs:
        original = source.read_bytes()
        redactions = []
        payload = original
        if source.suffix == '.json':
            clean = sanitize(json.loads(original), redactions)
            if redactions:
                payload = (json.dumps(clean, indent=2, allow_nan=False) + '\n').encode('utf-8')
        relative = f'{study}/{filename}'
        destination = args.output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
        entries.append(dict(path=relative, study=study, source_relative=f'{folder}/{filename}',
                            source_sha256=sha256(original), sha256=sha256(payload),
                            bytes=len(payload), path_strings_redacted=len(redactions),
                            transform='absolute location strings replaced; numerical values unchanged'
                            if redactions else 'byte-for-byte copy'))
    manifest = dict(schema=1, kind='historical-analysis-inputs', prepared='2026-11-15',
                    scope='Saved numerical summaries for offline analysis, not a complete solver replay archive.',
                    license='GPL-3.0-or-later; project-generated numerical summaries',
                    simulations_run=False, files=entries)
    (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(f'Prepared {len(entries)} files; {sum(e["bytes"] for e in entries):,} bytes')


if __name__ == '__main__':
    main()

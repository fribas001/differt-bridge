"""Small, solver-free helpers shared by the four research notebooks."""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(__file__).resolve().parent / 'data'


def verify_data(directory=DATA):
    directory = Path(directory)
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    for entry in manifest['files']:
        path = (directory / entry['path']).resolve()
        if not path.is_relative_to(directory.resolve()):
            raise ValueError('Data path is outside the bundle')
        payload = path.read_bytes()
        if len(payload) != entry['bytes'] or hashlib.sha256(payload).hexdigest() != entry['sha256']:
            raise ValueError(f'Data integrity check failed: {entry["path"]}')
    return manifest


def _file(relative):
    manifest = verify_data()
    if relative not in {e['path'] for e in manifest['files']}:
        raise ValueError(f'Not a declared analysis input: {relative}')
    return DATA / relative


def read_json(relative):
    return json.loads(_file(relative).read_text(encoding='utf-8'))


def read_csv(relative):
    with _file(relative).open(encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))


def dataframe(relative):
    # Import plotting/analysis dependencies only for interactive use.
    import pandas as pd
    return pd.read_csv(_file(relative))

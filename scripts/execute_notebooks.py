"""Execute all offline notebooks with this interpreter; export executed copies and HTML."""
import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import tempfile

import nbformat
from nbclient import NotebookClient
from nbconvert import HTMLExporter

ROOT = Path(__file__).resolve().parents[1]


def main():
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'build/notebooks')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    paths = sorted((ROOT / 'notebooks').glob('[0-9][0-9]_*.ipynb'))
    if len(paths) != 4:
        raise RuntimeError(f'Expected four research notebooks, found {len(paths)}')
    receipts = []
    # Temporary kernelspec avoids installing anything into a user's Jupyter config.
    from jupyter_client.kernelspec import KernelSpecManager
    with tempfile.TemporaryDirectory(prefix='differt-notebooks-') as temporary:
        kernels = Path(temporary) / 'kernels'
        spec = kernels / 'differt-replay'
        spec.mkdir(parents=True)
        (spec / 'kernel.json').write_text(json.dumps({
            'argv': [sys.executable, '-m', 'ipykernel_launcher', '-f', '{connection_file}'],
            'display_name': 'DiffeRT saved-result replay', 'language': 'python',
            'env': {'MPLBACKEND': 'Agg'},
        }), encoding='utf-8')
        manager = KernelSpecManager(kernel_dirs=[str(kernels)])
        for path in paths:
            notebook = nbformat.read(path, as_version=4)
            nbformat.validate(notebook)
            client = NotebookClient(notebook, timeout=180, kernel_name='differt-replay',
                                    resources={'metadata': {'path': str(ROOT)}}, allow_errors=False)
            client.create_kernel_manager()
            client.km.kernel_spec_manager = manager
            client.execute()
            nbformat.write(notebook, output / path.name)
            html, _ = HTMLExporter().from_notebook_node(notebook)
            (output / (path.stem + '.html')).write_text(html, encoding='utf-8')
            records = [c for c in notebook.cells if c.cell_type == 'code']
            receipts.append({'notebook': path.name, 'code_cells': len(records),
                             'executed_cells': sum(c.execution_count is not None for c in records),
                             'status': 'passed'})
            print(f'PASS {path.name}: {len(records)} code cells', flush=True)
    result = {'scope': 'Offline historical analysis; no native solvers invoked',
              'python': sys.version.split()[0], 'notebooks': receipts,
              'data_manifest_sha256': hashlib.sha256((ROOT / 'notebooks/data/manifest.json').read_bytes()).hexdigest(),
              'packages': {name: importlib.metadata.version(name) for name in
                           ('nbformat', 'nbclient', 'nbconvert', 'ipykernel', 'matplotlib', 'pandas', 'numpy')}}
    (output / 'execution.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()

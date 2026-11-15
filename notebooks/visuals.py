"""Verified, self-contained image displays usable in ordinary or Blender kernels."""
import base64
import hashlib
import html
import json
from pathlib import Path

ASSETS = Path(__file__).resolve().parent / 'assets'


def verify_assets(root=ASSETS):
    root = Path(root)
    manifest = json.loads((root / 'manifest.json').read_text())
    for entry in manifest['files']:
        path = root / entry['path']
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
            raise ValueError(f"Visual asset integrity failure: {entry['path']}")
    return manifest


def show_image(name, caption='', width=1100):
    from IPython.display import Image, Markdown, display
    verify_assets()
    display(Image(filename=str(ASSETS / name), width=width))
    if caption:
        display(Markdown(caption))


def compare_renders(left, right, labels=('Sionna RT', 'DiffeRT')):
    """Two embedded images with no network, widgets or browser-side scripting."""
    from IPython.display import HTML
    cards = []
    for path, label in zip((left, right), labels):
        encoded = base64.b64encode(Path(path).read_bytes()).decode('ascii')
        text = html.escape(label)
        cards.append(f'<figure style="flex:1;min-width:240px;margin:0"><figcaption>{text}</figcaption>'
                     f'<img alt="{text}" style="width:100%" src="data:image/png;base64,{encoded}"></figure>')
    return HTML('<div style="display:flex;flex-wrap:wrap;gap:12px">' + ''.join(cards) + '</div>')

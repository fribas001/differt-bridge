"""Independent FEM refinement at the fixed weak crossed-polarization ports."""
import argparse,json,hashlib,shutil
from pathlib import Path
from dielectric3d_synthesis import run

def main():
    ap=argparse.ArgumentParser();ap.add_argument('root',type=Path);ap.add_argument('--resolution',type=int,default=64);ap.add_argument('--order',type=int,default=8);a=ap.parse_args();root=a.root.resolve();work=root/'work/d3weak';d=json.loads((work/'diagnostics.json').read_text());ports=dict(sources=[d['source']],receivers=d['receivers'],axes=[1]);out=work/f'weak_fem{a.resolution}q{a.order}'
    if a.resolution==64 and a.order==8 and not out.exists():
        seed=work/'fem64';cfg=json.loads((seed/'config.json').read_text());assert cfg['sources']==ports['sources'] and cfg['receivers']==ports['receivers'] and cfg['axes']==[1] and cfg['epsilon']==d['epsilon']
        assert cfg['source_sha256']==hashlib.sha256(Path(__file__).with_name('dielectric3d_fem.py').read_bytes()).hexdigest()
        out.mkdir();files={}
        for i in cfg['indices']:
            p=seed/f'mode_{i:03d}.npz';m=p.with_suffix('.json');meta=json.loads(m.read_text());assert hashlib.sha256(p.read_bytes()).hexdigest()==meta['field_sha256']
            for f in (p,m):shutil.copyfile(f,out/f.name);files[f.name]=hashlib.sha256(f.read_bytes()).hexdigest()
        (out/'seed_provenance.json').write_text(json.dumps(dict(source=str(seed),config=cfg,files=files,scope='Identical q, material, source, receivers, axes and FEM source; no field transformation.'),indent=2),encoding='utf-8')
    run(out,method='fem',resolution=a.resolution,epsilon=complex(*d['epsilon']),order=a.order,ports=ports)

if __name__=='__main__':main()

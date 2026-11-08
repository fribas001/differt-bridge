"""Independent FEM holdouts; no production BIE fields enter the reference."""
import argparse,json
from pathlib import Path
from scipy.constants import epsilon_0
import numpy as np
from dielectric3d_synthesis import run

def main(manifest,output,resolution):
    cases=json.loads(manifest.read_text())['cases'];m=cases[0]['material'];eps=complex(m['relative_permittivity'],-m['conductivity']/(2*np.pi*299792458.*epsilon_0))
    assert all(c['material']==m for c in cases)
    sources=[list(v) for v in dict.fromkeys(tuple(c['tx']) for c in cases)];receivers=[list(v) for v in dict.fromkeys(tuple(r) for c in cases for r in c['receivers'])]
    ports=dict(sources=sources,receivers=receivers,axes=[0,1,2]);run(output,method='fem',resolution=resolution,epsilon=eps,order=8,ports=ports)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('manifest',type=Path);ap.add_argument('output',type=Path);ap.add_argument('--resolution',type=int,default=48);a=ap.parse_args();main(a.manifest,a.output,a.resolution)

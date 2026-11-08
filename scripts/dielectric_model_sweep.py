"""Constraint experiments on audited float64 formulas; not full-wave validation."""
import argparse,copy,json
from pathlib import Path
import numpy as np
from dielectric_cases import make,cases
from dielectric_model import coefficient,go_coefficient

PROFILES=('sionna-native','differt-native','sionna-kp_depth','differt-polarization','differt-incident','differt-symmetric_cosine')
def reverse(c,rx=0):
    r=copy.deepcopy(c);r['tx'],r['receivers']=c['receivers'][rx],[c['tx']];r['tx_pol'],r['rx_pol']=c['rx_pol'],c['tx_pol'];return r
def projected(c,profile,rx):
    a,_=coefficient(c,profile,rx);b,_=coefficient(reverse(c,rx),profile)
    return .5*(a+b)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('output',type=Path);args=ap.parse_args()
    angles=np.linspace(7,263,27);grids={};counts={}
    for profile in PROFILES:
        data=[];count=0
        for pi in angles:
            row=[]
            for pd in angles:
                if min(abs(abs(pd-pi)-180),abs(pd+pi-180),abs(pd+pi-360))<1e-3:row.append(None);continue
                c=make('grid',float(pi),float(pd),'V','concrete');r=reverse(c)
                a,_=coefficient(c,profile);b,_=coefficient(r,profile)
                row.append(float(abs(a-b)/max(abs(a),abs(b),1e-10)));count+=1
            data.append(row)
        grids[profile]=data;counts[profile]=count
    boundary=[]
    selected=[c for c in cases() if c['study']['kind']=='boundary' and c['study']['material']=='concrete' and c['frequency_hz']==3.5e9]
    for c in selected:
        for profile in ('differt-native','sionna-kp_depth'):
            for i,j in ((2,8),(3,7),(4,6)):
                ga,gb=go_coefficient(c,c['study']['boundary'],i),go_coefficient(c,c['study']['boundary'],j)
                if (ga is None)==(gb is None) or abs((ga or gb)[0])<1e-10:continue
                a,b=projected(c,profile,i),projected(c,profile,j)
                jump=(b-a)/ga[0] if ga else (a-b)/gb[0]
                boundary.append(dict(profile=profile+'-reciprocal_average',name=c['name'],skew=c['study']['skew'],boundary=c['study']['boundary'],offset_deg=abs(c['study']['offsets_deg'][i]),jump=[float(jump.real),float(jump.imag)],error=float(abs(jump-1))))
    air=[]
    for profile in PROFILES:
        c=make('zero_contrast',60,100,'V','air');a,_=coefficient(c,profile)
        air.append(dict(profile=profile,coefficient=[a.real,a.imag],magnitude=abs(a)))
    result=dict(scope='Audited formula experiments only. Reciprocity of averaged coefficients is imposed by construction, not evidence of electromagnetic accuracy. All models still require independent dielectric/impedance reference validation.',angles_deg=angles.tolist(),reciprocity_grids=grids,grid_pairs_per_profile=counts,reciprocal_projection_boundaries=boundary,zero_contrast_diffracted_field=air,
        zero_contrast_scope='An opaque/reflection-only edge model is not a transparent dielectric model. This is a missing-model limit; transmission was disabled in the ray-tracer fixtures.')
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    print('Formula grids',counts,'boundary projections',len(boundary),flush=True)

if __name__=='__main__':main()

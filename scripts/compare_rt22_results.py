"""Prespecified migration tolerances, matched physical routes, no fitted correction."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from scipy.optimize import linear_sum_assignment

def compare(old,new):
    rows=[]
    limits=dict(point_m=1e-5,delay_s=1e-13,field_rtol=1e-5,field_atol=2e-10,phase_rad=1e-4,phase_floor=1e-9)
    assert old['manifest_sha256']==new['manifest_sha256']
    assert len(old['cases'])==len(new['cases']) and len(old['cases'])>0
    assert len({c['name'] for c in old['cases']})==len(old['cases'])
    for a,b in zip(old['cases'],new['cases']):
        assert a['name']==b['name']
        valid=a['status']==b['status']=='completed'
        exact=all(a.get(k)==b.get(k) for k in ('array_shapes','input_file_sha256','effective_materials','valid_paths'))
        row=dict(name=a['name'],completed=valid,input_shape_count_match=exact,point_m=0.,delay_s=0.,field_absolute=0.,field_relative=0.,phase_rad=0.,fields_pass=True)
        pa=a.get('paths',[]);pb=b.get('paths',[])
        row['fields_pass'] &= len(pa)==len(pb)
        if len(pa)==len(pb) and pa:
            cost=np.full((len(pa),len(pb)),1e30)
            for i,x in enumerate(pa):
                for j,y in enumerate(pb):
                    if x['rx']==y['rx'] and x['interactions']==y['interactions']:
                        cost[i,j]=np.max(np.abs(np.array(x['points'])-y['points']))
            ix,jx=linear_sum_assignment(cost)
            for i,j in zip(ix,jx):
                x,y=pa[i],pb[j];row['point_m']=max(row['point_m'],float(cost[i,j]));row['delay_s']=max(row['delay_s'],abs(x['delay_s']-y['delay_s']))
                row['fields_pass'] &= x['finite'] and y['finite']
                for key in ('a','cir'):
                    u,v=complex(*x[key]),complex(*y[key]);delta=abs(u-v)
                    row['field_absolute']=max(row['field_absolute'],delta);row['field_relative']=max(row['field_relative'],delta/max(abs(u),1e-30))
                    row['fields_pass'] &= delta<=limits['field_atol']+limits['field_rtol']*abs(u)
                    if u!=v and min(abs(u),abs(v))>limits['phase_floor']:row['phase_rad']=max(row['phase_rad'],abs(float(np.angle(v/u))))
        row['passed']=valid and exact and row['fields_pass'] and row['point_m']<=limits['point_m'] and row['delay_s']<=limits['delay_s'] and row['phase_rad']<=limits['phase_rad']
        rows.append(row)
    return dict(passed=all(r['passed'] for r in rows),before=old['versions'],after=new['versions'],tolerances=limits,cases=rows)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('baseline',type=Path);p.add_argument('new',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    result=compare(json.loads(a.baseline.read_text()),json.loads(a.new.read_text()))
    result['baseline_sha256']=hashlib.sha256(a.baseline.read_bytes()).hexdigest()
    result['new_sha256']=hashlib.sha256(a.new.read_bytes()).hexdigest()
    a.output.write_text(json.dumps(result,indent=2))
    print('CAMPAIGN_COMPARISON',result['passed'],len(result['cases']))
    print('MAXIMA', {k:max(r[k] for r in result['cases']) for k in ('point_m','delay_s','field_absolute','field_relative','phase_rad')})
    for row in result['cases']:
        if not row['passed']:print(row)
    raise SystemExit(0 if result['passed'] else 1)

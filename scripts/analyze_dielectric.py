"""Audit computation, reciprocal geometry, finite boundary limits and formula attribution."""
import argparse,copy,hashlib,json
from pathlib import Path
import numpy as np
from dielectric_model import coefficient,go_coefficient
from diffraction_reference import C,geometry_audit

read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
pair=lambda z:[float(z.real),float(z.imag)]
def difference(a,b):
    scale=max(abs(a),abs(b));null=scale<1e-10
    return dict(absolute=abs(a-b),symmetric_relative=abs(a-b)/scale if not null else None,
                gain_delta_db=float(20*np.log10(abs(b)/abs(a))) if min(abs(a),abs(b))>=1e-10 else None,
                phase_delta_rad=float(np.angle(b/a)) if min(abs(a),abs(b))>=1e-10 else None,near_null=null)
def edge_paths(row,rx=0):return [p for p in row.get('paths',[]) if p['rx']==rx and p['interactions']==[8]]
def boundary_go(case,row,rx):
    boundary=case['study']['boundary'];event=[] if boundary=='incident' else [1]
    paths=[p for p in row.get('paths',[]) if p['rx']==rx and p['interactions']==event]
    if boundary=='incident':return paths
    rot=np.asarray(case['physics']['rotation']);axis=0 if boundary=='reflection0' else 1
    # Identify the actual face rather than choosing the strongest GO path.
    return [p for p in paths if abs((rot.T@np.asarray(p['points'][1]))[axis])<1e-7]

def analyze(work):
    manifest=read(work/'cases.json');cases={c['name']:c for c in manifest['cases']}
    receipts=read(work/'receipt.json');assert receipts['status']=='passed'
    assert hashlib.sha256((work/'cases.json').read_bytes()).hexdigest()==receipts['manifest_sha256']
    profiles={}
    for receipt in receipts['processes']:
        folder=work/receipt['profile'];path=folder/receipt['output']
        assert receipt['passed'] and hashlib.sha256(path.read_bytes()).hexdigest()==receipt['output_sha256']
        data=read(path);assert data['manifest_sha256']==receipts['manifest_sha256']
        assert {c['name'] for c in data['cases']}==set(cases)
        profiles[receipt['profile']]={r['name']:r for r in data['cases']}
    reciprocal=[];boundary=[];models=[];orders=[];obstacles=[];preservation=[];geometry=[]
    for profile,rows in profiles.items():
        for name,c in cases.items():
            row=rows[name];meta=c['study']
            if meta['kind']=='obstacle':
                obstacles.append(dict(profile=profile,name=name,expected=meta['expected_paths'],actual=len(row['paths']),passed=len(row['paths'])==meta['expected_paths']));continue
            if 'reverse_of' in meta:
                previous=rows[meta['reverse_of']];a,b=edge_paths(previous),edge_paths(row)
                entry=dict(profile=profile,name=name,material=meta['material'],polarization=meta['polarization'],skew=meta['skew'],counts=[len(a),len(b)])
                if len(a)==len(b)==1:
                    entry.update(difference(complex(*a[0]['a']),complex(*b[0]['a'])))
                    entry.update(max_reversed_vertex_error_m=float(np.max(np.linalg.norm(np.asarray(a[0]['points'])-np.asarray(b[0]['points'])[::-1],axis=-1))),delay_error_s=abs(a[0]['delay_s']-b[0]['delay_s']))
                reciprocal.append(entry)
            if 'same_geometry_as' in meta:
                a,b=edge_paths(rows[meta['same_geometry_as']]),edge_paths(row)
                entry=dict(profile=profile,name=name,counts=[len(a),len(b)])
                if len(a)==len(b)==1:entry.update(difference(complex(*a[0]['a']),complex(*b[0]['a'])))
                orders.append(entry)
            if meta['kind']=='boundary':
                offsets=meta['offsets_deg'];zero=offsets.index(0.)
                for i in range(zero):
                    j=len(offsets)-1-i;da,db=edge_paths(row,i),edge_paths(row,j)
                    ga,gb=boundary_go(c,row,i),boundary_go(c,row,j)
                    entry=dict(profile=profile,name=name,material=meta['material'],polarization=meta['polarization'],skew=meta['skew'],boundary=meta['boundary'],offset_deg=abs(offsets[i]),diffraction_counts=[len(da),len(db)],go_counts=[len(ga),len(gb)])
                    if len(da)==len(db)==1 and sorted([len(ga),len(gb)])==[0,1]:
                        g=(ga or gb)[0];gvalue=complex(*g['a']);entry['go_magnitude']=abs(gvalue)
                        if abs(gvalue)>=1e-10:
                            aa,bb=complex(*da[0]['a']),complex(*db[0]['a']);jump=(bb-aa if ga else aa-bb)/gvalue
                            total=[sum(complex(*p['cir']) for p in row['paths'] if p['rx']==r) for r in (i,j)]
                            entry.update(jump=pair(jump),jump_error=abs(jump-1),coherent_total_difference_over_go=abs(total[1]-total[0])/abs(complex(*g['cir'])))
                            ref=go_coefficient(c,meta['boundary'],i if ga else j)
                            if ref:entry['go_formula_error']=difference(ref[0],gvalue)
                    boundary.append(entry)
                # Exact edge/GO coincidence is a separate degeneracy, not a one-sided limit.
                entry=dict(profile=profile,name=name,exact_boundary=True,finite=all(p['finite'] for p in row['paths'] if p['rx']==zero),paths=sum(p['rx']==zero for p in row['paths']))
                geometry.append(entry)
            for rx in range(len(c['receivers'])):
                if meta['kind']=='boundary' and meta['offsets_deg'][rx]==0:continue
                paths=edge_paths(row,rx)
                if len(paths)!=1:continue
                if meta['kind']=='mesh_order':continue  # Engine face enumeration can differ; measured order invariance is recorded above.
                try:prediction,detail=coefficient(c,profile,rx)
                except ValueError:continue
                actual=complex(*paths[0]['a']);error=difference(prediction,actual)
                models.append(dict(profile=profile,name=name,rx=rx,material=meta['material'],skew=meta['skew'],prediction=pair(prediction),measured=pair(actual),error=error,**detail))
            if meta['kind']=='reciprocity' and 'reverse_of' not in meta and profile in ('sionna-native','differt-native'):
                paths=edge_paths(row)
                if len(paths)==1:
                    audit=geometry_audit(paths[0],c)
                    geometry.append(dict(profile=profile,name=name,**audit))
        if profile not in ('sionna-native','differt-native'):
            native=profiles[profile.split('-')[0]+'-native']
            for name,row in rows.items():
                def keys(x):return sorted(json.dumps({k:p[k] for k in ('rx','points','interactions','delay_s')},sort_keys=True) for p in x['paths'])
                exact=keys(row)==keys(native[name])
                item=dict(profile=profile,name=name,material=cases[name]['study'].get('material'),exact_path_geometry_and_delays=exact)
                if not exact:
                    def keyed(x):return {json.dumps({k:p[k] for k in ('rx','points','interactions','delay_s')},sort_keys=True):p for p in x['paths']}
                    before,after=keyed(native[name]),keyed(row)
                    item.update(native_paths=len(before),candidate_paths=len(after),removed=[before[k] for k in before.keys()-after.keys()],added=[after[k] for k in after.keys()-before.keys()])
                preservation.append(item)
    summary={}
    for profile,rows in profiles.items():
        rr=[r for r in reciprocal if r['profile']==profile and r.get('symmetric_relative') is not None and r['material']!='pec']
        mm=[r['error'] for r in models if r['profile']==profile and not r['error']['near_null']]
        bb=[r for r in boundary if r['profile']==profile and r['offset_deg']==.001 and 'jump_error' in r and r['material'] not in ('pec','air')]
        summary[profile]=dict(completed=len(rows),coefficient_dtypes=sorted({r.get('coefficient_dtype') for r in rows.values()}),field_precision_profiles=sorted({r.get('field_precision_profile') for r in rows.values()}),
            reciprocal_nonnull_dielectric_pairs=len(rr),max_reciprocity_relative=max((r['symmetric_relative'] for r in rr),default=None),max_reciprocity_gain_db=max((abs(r['gain_delta_db']) for r in rr if r['gain_delta_db'] is not None),default=None),
            formula_checks=len(mm),max_formula_relative=max((r['symmetric_relative'] for r in mm),default=None),
            boundary_checks_at_0_001_deg=len(bb),boundary_within_1_percent=sum(r['jump_error']<.01 for r in bb),max_boundary_error=max((r['jump_error'] for r in bb),default=None))
    return dict(scope='Matched native and isolated-candidate computations; float64 transcriptions explain formulas but are not independent dielectric accuracy references.',requested=sum(r['requested'] for r in receipts['processes']),completed=sum(r['completed'] for r in receipts['processes']),summary=summary,reciprocity=reciprocal,boundaries=boundary,formula_checks=models,mesh_order=orders,obstacles=obstacles,geometry=geometry,preservation=preservation)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('work',type=Path);ap.add_argument('output',type=Path);args=ap.parse_args()
    result=analyze(args.work);args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(result['summary'],indent=2))

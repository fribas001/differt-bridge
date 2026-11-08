"""Build the measured dielectric addendum and standalone scientific figures."""
import argparse,hashlib,html,json
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

LABELS={'sionna-native':'Sionna native','differt-native':'DiffeRT native','sionna-kp_depth':'Sionna KP candidate',
        'differt-polarization':'DiffeRT polarization candidate','differt-incident':'DiffeRT incident-angle candidate','differt-symmetric_cosine':'DiffeRT symmetric-cosine hypothesis'}
COLORS={'sionna-native':'#bd6618','differt-native':'#087d90','sionna-kp_depth':'#6848a2','differt-polarization':'#208344','differt-incident':'#4c639f','differt-symmetric_cosine':'#8f465a'}
ORDER=['sionna-native','differt-native','sionna-kp_depth','differt-polarization','differt-incident','differt-symmetric_cosine']
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
def fmt(v):
    if v is None:return '—'
    if isinstance(v,complex):return f'{v.real:.5g} {v.imag:+.5g}j'
    return f'{v:.5g}' if isinstance(v,(float,np.floating)) else str(v)
def table(headers,rows):
    return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+html.escape(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(fmt(v))+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table></div>'

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--work',required=True,type=Path);ap.add_argument('--output',required=True,type=Path);ap.add_argument('--models',required=True,type=Path);ap.add_argument('--precision',required=True,type=Path);ap.add_argument('--worst',required=True,type=Path);args=ap.parse_args()
    out=args.output;out.mkdir(parents=True,exist_ok=True)
    a=read(out/'analysis.json');f64=read(out/'float64_analysis.json');worst=read(out/'float64_worst_analysis.json');models=read(args.models)
    boundary_geometry=read(out/'boundary_geometry.json')
    assert all(s['checks']==580 for s in boundary_geometry['summary'].values())
    assert all(s['failed']==(40 if p.startswith('sionna-') else 0) for p,s in boundary_geometry['summary'].items())
    assert a['requested']==a['completed']==1716
    assert f64['completed']==46 and worst['completed']==6
    assert len(a['obstacles'])==24 and all(x['passed'] for x in a['obstacles'])
    assert all(x['exact_path_geometry_and_delays'] for x in a['preservation'] if x['material']!='air')
    assert all(not x.get('interior_triangle_hits') for x in a['geometry'])
    assert all(x['finite'] for x in a['geometry'] if x.get('exact_boundary'))
    assert max(x['error']['symmetric_relative'] for x in a['formula_checks'] if not x['error']['near_null'])<.001
    assert a['summary']['sionna-kp_depth']['boundary_within_1_percent']==50
    assert a['summary']['differt-polarization']['boundary_within_1_percent']==34
    assert f64['summary']['differt-symmetric_cosine']['max_reciprocity_relative']<1e-10
    all_profiles={}
    for p in ORDER:
        path=args.work/p/(p.split('-')[0]+'_float32.json');all_profiles[p]={r['name']:r for r in read(path)['cases']}
    # Precision comparisons preserve path identity and event sequence.
    precision=[]
    for folder in (args.precision,args.worst):
        for rec in read(folder/'receipt.json')['processes']:
            p=rec['profile'];data=read(folder/p/rec['output'])
            for row in data['cases']:
                before=all_profiles[p][row['name']]
                key=lambda q:json.dumps({k:q[k] for k in ('rx','points','interactions','delay_s')},sort_keys=True)
                old={key(q):q for q in before['paths']};new={key(q):q for q in row['paths']}
                assert old.keys()==new.keys(),(p,row['name'],'precision changed path geometry')
                for k,q in new.items():
                    a32=complex(*old[k]['a']);a64=complex(*q['a']);scale=max(abs(a32),abs(a64))
                    if q['interactions']!=[8] or scale<1e-10:continue
                    precision.append(dict(profile=p,name=row['name'],rx=q['rx'],nominal_exact_boundary=row['name'].startswith('boundary_') and q['rx']==5,relative=abs(a64-a32)/scale,absolute=abs(a64-a32),phase_rad=float(np.angle(a64/a32)) if min(abs(a32),abs(a64))>=1e-10 else None))
    (out/'precision.json').write_text(json.dumps(precision,indent=2),encoding='utf-8')
    (out/'model_experiments.json').write_text(json.dumps(models,indent=2),encoding='utf-8')
    plt.rcParams.update({'font.size':10.5,'axes.spines.right':False,'axes.spines.top':False,'axes.titleweight':'bold'})
    fig,axes=plt.subplots(2,2,figsize=(15,10),layout='constrained')
    for ax,name,title in [(axes[0,0],'boundary_concrete_broadside_reflection0_HH','Broadside H/H reflection boundary'),(axes[0,1],'boundary_concrete_skew_reflection0_VH','Skew V/H reflection boundary')]:
        for p in ORDER[:4]:
            rows=sorted((r for r in a['boundaries'] if r['profile']==p and r['name']==name and 'jump_error' in r),key=lambda r:r['offset_deg'])
            ax.loglog([r['offset_deg'] for r in rows],[max(r['jump_error'],1e-9) for r in rows],'-o',label=LABELS[p],color=COLORS[p],ms=4)
        ax.invert_xaxis();ax.set(xlabel='Distance from boundary (degrees; closer →)',ylabel='|normalized diffraction jump − 1|',title=title);ax.grid(alpha=.2);ax.legend(fontsize=8)
    ax=axes[1,0]
    for p in ORDER:
        values=sorted(r['symmetric_relative'] for r in a['reciprocity'] if r['profile']==p and r.get('symmetric_relative') is not None and r['material']!='pec')
        ax.semilogy(np.linspace(0,100,len(values)),np.maximum(values,1e-9),label=LABELS[p],color=COLORS[p])
    ax.set(xlabel='Percentile of eligible dielectric pairs',ylabel='|h forward − h reverse| / max(|h|)',title='Reciprocity across materials and polarizations');ax.grid(alpha=.2);ax.legend(fontsize=7.8)
    ax=axes[1,1]
    ordermax=[max(abs(r['gain_delta_db']) for r in a['mesh_order'] if r['profile']==p and r.get('gain_delta_db') is not None) for p in ORDER]
    ax.barh(range(len(ORDER)),ordermax,color=[COLORS[p] for p in ORDER]);ax.set_yticks(range(len(ORDER)),['Sionna native','DiffeRT native','Sionna KP','DiffeRT polarization','DiffeRT incident angle','DiffeRT symmetric cosine'],fontsize=8.5)
    ax.set(xlabel='Maximum gain change (dB)',title='Same triangles, different face enumeration');ax.invert_yaxis()
    for i,value in enumerate(ordermax):ax.text(value+.15,i,fmt(value),va='center',fontsize=8)
    ax.set_xlim(0,max(ordermax)*1.19)
    fig.savefig(out/'dielectric_summary.png',dpi=160);fig.savefig(out/'dielectric_summary.svg');plt.close(fig)
    fig,axes=plt.subplots(2,2,figsize=(12,10),layout='constrained')
    for ax,p in zip(axes.flat,('sionna-native','differt-native','sionna-kp_depth','differt-symmetric_cosine')):
        grid=np.array([[np.nan if x is None else x for x in row] for row in models['reciprocity_grids'][p]])
        im=ax.imshow(grid,origin='lower',extent=[7,263,7,263],vmin=0,vmax=2,aspect='equal',cmap='magma')
        ax.set(xlabel='Observer angle (degrees)',ylabel='Source angle (degrees)',title=LABELS[p])
    fig.colorbar(im,ax=axes.ravel().tolist(),shrink=.8,label='Formula reciprocity residual (0 = reciprocal)')
    fig.suptitle('Float64 formula grid: concrete, V/V — not independent accuracy validation',fontsize=12)
    fig.savefig(out/'reciprocity_grid.png',dpi=160);fig.savefig(out/'reciprocity_grid.svg');plt.close(fig)
    rows=[]
    for p in ORDER:
        s=a['summary'][p];rows.append([LABELS[p],s['max_reciprocity_gain_db'],s['max_reciprocity_relative'],str(s['boundary_within_1_percent'])+'/50',ordermax[ORDER.index(p)]])
    summary_table=table(['Profile','Max reciprocity gain gap (dB)','Max complex residual','Boundary checks within 1% at ±0.001°','Max face-order gap (dB)'],rows)
    selected_names=['boundary_concrete_broadside_reflection0_VV','boundary_concrete_broadside_reflection0_HH','boundary_concrete_skew_reflection0_VH']
    selected_rows=[]
    for name in selected_names:
        for p in ORDER[:4]:
            r=next(r for r in a['boundaries'] if r['name']==name and r['profile']==p and r['offset_deg']==.001)
            selected_rows.append([name.replace('boundary_concrete_',''),LABELS[p],complex(*r['jump']),r['coherent_total_difference_over_go'],r['go_magnitude']])
    boundary_table=table(['Fixture','Profile','Normalized complex jump (target +1)','Coherent field difference / GO','|GO coefficient|'],selected_rows)
    material_rows=[]
    for material in ('concrete','lossless','high_loss','thin','thick'):
        row=[material]
        for p in ('sionna-native','differt-native','sionna-kp_depth'):
            values=[abs(r['gain_delta_db']) for r in a['reciprocity'] if r['profile']==p and r['material']==material and r.get('gain_delta_db') is not None]
            row.append(max(values))
        material_rows.append(row)
    material_table=table(['Material (same numeric inputs)','Sionna native max dB','DiffeRT native max dB','Sionna KP max dB'],material_rows)
    projection=[]
    for p in ('differt-native-reciprocal_average','sionna-kp_depth-reciprocal_average'):
        rr=[r for r in models['reciprocal_projection_boundaries'] if r['profile']==p and r['offset_deg']==.001]
        projection.append([p,'Exact by construction',str(sum(r['error']<.01 for r in rr))+'/'+str(len(rr)),max(r['error'] for r in rr),'Not independently validated'])
    projection_table=table(['Formula-only projection','Reciprocity','Boundary checks within 1%','Max boundary residual','Accuracy status'],projection)
    max_model=max(r['error']['symmetric_relative'] for r in a['formula_checks'] if not r['error']['near_null'])
    nonair=[r for r in a['preservation'] if r['material']!='air']
    nulls=sum(r.get('near_null',False) for r in a['reciprocity'])
    details_rows=[]
    for r in a['reciprocity']:
        if r.get('gain_delta_db') is not None:details_rows.append([LABELS[r['profile']],r['name'],r['gain_delta_db'],r['phase_delta_rad'],r['symmetric_relative'],r['max_reversed_vertex_error_m']])
    detailed_table=table(['Profile','Reciprocal fixture','Reverse/forward gain (dB)','Phase difference (rad)','Complex residual','Reversed vertex error (m)'],details_rows)
    style='''body{font:17px/1.55 system-ui,sans-serif;color:#1d2933;background:#f5f7f8;margin:0}main{max-width:1220px;margin:auto;padding:32px}h1{font-size:38px;line-height:1.15}h2{margin-top:42px}h3{margin-top:28px}a{color:#086d82}img{max-width:100%;background:white;border:1px solid #d9e0e4;border-radius:8px}.callout{background:#e7eff3;border-left:5px solid #087d90;padding:16px 22px}.warn{background:#fff0d9;border-left-color:#bd6618}.scroll{overflow-x:auto;margin:18px 0}table{border-collapse:collapse;background:white;width:100%;font-size:14px}th,td{padding:9px 11px;text-align:left;border-bottom:1px solid #dde4e8;vertical-align:top}th{background:#e7eef2}code,pre{background:#e9edef}pre{padding:14px;overflow:auto;font-size:13px}input{padding:9px;width:min(600px,90%)}.small{font-size:14px;color:#4f5c65}.badge{display:inline-block;background:#d8e9df;padding:5px 10px;margin:4px;border-radius:4px}details{margin-top:22px}footer{margin-top:50px;border-top:1px solid #bcc9cf;padding-top:15px}'''
    page=f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Dielectric diffraction: reciprocity and boundary behavior</title><style>{style}</style><main>
<p><a href="../../../../index.html">Project results</a> · <a href="../diffraction_physics/index.html">Previous diffraction field report</a> · <a href="dielectric_evidence.zip">Numerical evidence and reproducer</a></p>
<h1>Dielectric diffraction: where the two engines still disagree</h1><p>November 3, 2026 · Sionna RT 2.1.0 / DiffeRT 0.12.0 · CPU · controlled, matched wedge geometry</p>
<div class="callout"><strong>The remaining gaps are predominantly field-model inconsistencies, not export rounding.</strong> This investigation isolates dielectric Fresnel weighting, the selection of face incidence angles, missing skew polarization coupling, and face-label dependence. Corrections that pass PEC or broadside checks do not establish a generally correct dielectric model.</div>
<p><span class="badge">1,716 / 1,716 main executions completed</span><span class="badge">52 / 52 float64 controls completed</span><span class="badge">24 / 24 obstacle controls passed</span></p>
<h2>Measured comparison</h2>{summary_table}
<p class="small">286 fixtures per main profile; 74 eligible non-null dielectric reciprocal pairs for each Sionna profile, 70 for each DiffeRT profile. DiffeRT's four unrotated skew cross-polar pairs are null and therefore omitted from gain/phase ratios. Maxima describe these sampled cases, not universal bounds. Native formulas use the existing configured float32 field profile; DiffeRT carrier conversion/storage is complex128, while Sionna exports complex64. Precision was recorded separately.</p>
<img src="dielectric_summary.png" alt="Measured reciprocity, boundary and face-order results"><p><a href="dielectric_summary.svg">Vector figure</a> · <a href="analysis.json">Complete main analysis</a> · <a href="float64_analysis.json">Float64 controls</a></p>
<h2>What was isolated</h2>
<h3>1. Dielectric weighting hidden by the PEC limit</h3><p>DiffeRT places its soft/hard scalar coefficients into the edge-phi and edge-tau components with Fresnel weights that disagree with the corresponding specular reflection at broadside. At the reflection boundary, its native normalized jumps approach <code>−r_p/r_s</code> for V and <code>−r_s/r_p</code> for H. PEC has <code>r_s≈−1</code> and <code>r_p≈+1</code>, so the defect is hidden by that limit.</p>
<p>The isolated polarization candidate swaps the Fresnel weights and their reflected-term signs. It improves the 50 eligible dielectric boundary checks from 14 to 34: all 20 broadside reflection checks pass, while all 16 skew reflection checks still fail. It can worsen reciprocity and face-order sensitivity. It is not a general repair.</p>
<h3>2. Skew reflection requires a full polarization matrix</h3><p>The native DiffeRT edge matrix is diagonal. For the unrotated vertical-edge skew V/H fixture, its diffracted cross component is essentially zero while the specular cross component is nonzero. A zero diffracted jump cannot cancel that GO transition. Adjusting the material angle or swapping diagonal entries cannot supply the missing coupling. Sionna's full reflection-basis transport, combined with the previous isolated KP assembly correction, passes all 50 sampled boundary checks.</p>
<h3>3. Reciprocity is a separate constraint</h3><p>Swapping source and receiver preserves the ray geometry but changes the heuristic material factors. Sionna evaluates both face coefficients using the incident direction; DiffeRT uses an incident-direction angle on one face and an outgoing-direction angle on the other. Its skew evaluation additionally omits the edge-angle factor in these Fresnel cosines. These formula choices reproduce the observed material-dependent discrepancies.</p>{material_table}
<p>The largest sampled native mismatches are 29.754 dB for Sionna with a 1 mm slab and 13.670 dB for DiffeRT with a 1 m slab. The worst DiffeRT case and the 11.762 dB face-order case were repeated with float64 fields. Reciprocal ports are compared directly as complex coefficients, without conjugation; independent specular calculations verify this port convention, including cross polarization.</p>
<h3>4. Triangle order leaks into DiffeRT's material response</h3><p>Swapping the two faces' triangle blocks preserves vertices, winding, surface normals, materials and physical geometry. Native DiffeRT changes by up to 11.762 dB; both Sionna profiles are unchanged. When both faces are illuminated, the choice of which face receives which heuristic incidence angle depends on enumeration. Using the actual incident angles on both faces removes this dependence to the observed float32 floor (maximum complex residual below 2e-5), but does not restore reciprocity or skew boundary consistency.</p>
<h2>Boundary evidence and its interpretation</h2><p>For each nonzero boundary GO ray, the diagnostic is <code>J = (a_diff,shadow − a_diff,illuminated) / a_GO</code>; continuity requires the one-sided limit <code>J→+1</code>. The lit side and face are determined geometrically, not by choosing the strongest path. The coherent-field metric restores each path's propagation phase through its CIR and includes all returned paths. The independent image/Fresnel calculation checks the GO normalization.</p>{boundary_table}
<p>Receiver offsets are ±1°, ±0.1°, ±0.01°, ±0.001° and ±0.0001°. The pass count uses a declared 1% diagnostic tolerance at ±0.001°, not a claim that two finite-separated fields should be identical. Exact boundary samples are retained separately: float32 angular rounding can select different one-sided branches there. No exact-boundary sample is used to validate a one-sided formula limit. A weak GO ray can make a normalized residual large; its absolute magnitude and complete complex field are retained in the evidence.</p>
<h3>A separate geometric effect at the smallest offset</h3><p>Checking the presence of the GO ray independently gives 580 eligible receiver checks per profile. Every DiffeRT profile passes all 580. Each Sionna profile fails 40 at +0.0001°: 20 extra reflection0 rays and 20 missing valid reflectionn rays. The original prose incorrectly described all 40 as extra rays; raw expected/observed flags were correct. These are nonzero offsets, not nominal exact-boundary samples.</p>
<p>The measured Sionna intersection is displaced onto the face. Source inspection shows that its native image method offsets the image-ray target before intersecting the scene; this is consistent with the observed micrometre-scale displacement. This geometric acceptance effect is separate from dielectric Fresnel weighting. It also affects PEC controls and remains under the field-only KP correction. Therefore the 50/50 KP result at ±0.001° must not be read as correct geometry at every smaller offset. No global ray-offset change is proposed, because those offsets also serve visibility checks.</p>
<p>The Sionna curves stop before ±0.0001° where both sides retain the GO ray, making the declared one-sided jump normalization inapplicable. Those samples were audited separately, not counted as successful field limits. <a href="boundary_geometry.json">Full independent GO-presence audit, ideal points and observed intersections</a>.</p>
<h2>Reciprocity constraints and accuracy</h2><p>The symmetric-cosine hypothesis uses an average of the absolute incident and outgoing normal projections. It is a deliberately constructed diagnostic, not a named published wedge solution. Its sampled reciprocity residual falls to {fmt(f64['summary']['differt-symmetric_cosine']['max_reciprocity_relative'])} with float64 fields. It still passes only 34/50 main boundary checks because the skew matrix limitation remains.</p>
<p>Likewise, averaging an audited forward coefficient with its reversed-port coefficient imposes reciprocity by construction. Averaging the native DiffeRT model does not repair its boundary failures. Averaging the Sionna KP model satisfies the sampled concrete boundary constraints too, but this is still not an independent accuracy test:</p>{projection_table}
<img src="reciprocity_grid.png" alt="Reciprocity residual grids calculated from audited float64 formulas"><p class="small">729 angle pairs per profile, V/V concrete at 3.5 GHz. These are formula experiments, not additional ray-tracer executions or full-wave measurements. <a href="reciprocity_grid.svg">Vector figure</a> · <a href="model_experiments.json">Formula experiment data</a></p>
<div class="callout warn"><strong>No dielectric physics patch was installed.</strong> A reciprocal result can still be physically inaccurate. The zero-contrast controls also show that these opaque/reflection-only heuristics do not constitute a complete transparent dielectric model. Transmitted fields were disabled; a physically matched dielectric reference must include the relevant transmission mechanisms.</div>
<h2>Validation, provenance and limits</h2><ul>
<li>Materials: εr=5.24, σ=0.123086944 S/m with 1 mm, 0.1 m and 1 m thicknesses; εr=4 lossless; σ=10 S/m high-loss; a finite-conductivity PEC limit; and zero-contrast controls. Geometry and material inputs are float32-representable and identical between engines.</li>
<li>Broadside, skew, rotated and rotated-skew fixtures include VV, HH, VH and HV where relevant. Main frequency is 3.5 GHz; additional boundary checks use 28 GHz with the same specified εr, σ and thickness, rather than silently re-evaluating an ITU material catalog.</li>
<li>The float64 field controls retain the existing common-scalar policy: wavelength, angular frequency and the permittivity operand are evaluated in float32 and promoted. They are controls of the configured field precision, not a claim that every operand is evaluated in float64. The independent formula transcription uses unrounded physical constants and reproduces the large dielectric discrepancies too.</li>
<li>{len(nonair)}/{len(nonair)} candidate-versus-native non-air checks preserve the exact physical path records and delays. Two air-material Sionna cases add nonzero diffracted paths after changing the assembly; these are disclosed zero-contrast/model-domain exceptions, not obstacle-control successes. All 24 true-obstacle controls pass, including an obstruction 1 mm from the edge.</li>
<li>{sum(not r['error']['near_null'] for r in a['formula_checks'])} non-null measured coefficients agree with the independent NumPy/SciPy <em>implementation transcription</em> within {max_model*100:.4g}% symmetric complex error. This explains the formulas; it does not validate their dielectric physics. DiffeRT's finite-limit branch inside 1e-5 radians also differs slightly from the exact transition expression.</li>
<li>Near-null gain/phase ratios are withheld ({nulls} main reciprocal entries). Actual precision policies, exported dtypes, native process exit codes, source hashes, inputs and all coefficients are retained. No failed worker is converted to a zero-gain observation.</li>
<li>The four new analytic regression tests pass. The broader 262-test suite has 260 passes and two failures in unchanged free-space amplitude checks: relative deviation 7.67e-8 against a 1e-10 tolerance in the existing runtime's float64 profile. Both failures recur in isolation and equal the configured wavelength's rounding error. An isolated process using unrounded common scalars passes both original assertions. The configured-runtime failures remain recorded; no tolerance was relaxed or installed implementation changed. <a href="verification.json">Verification details</a> distinguish these from the successful research executions.</li>
<li>There is no new full-wave or independently evaluated impedance-wedge accuracy benchmark here. The geometry uses two finite thin-slab faces; it must not be confused with an exact homogeneous solid dielectric wedge. Single-edge cases isolate local field formulas; multiple diffraction, GPU behavior and volumetric bending are outside this addendum.</li></ul>
<p>Literature context: <a href="https://onlinelibrary.wiley.com/doi/10.1155/2018/3029152">Tami et al. (2018)</a> documents reciprocity limitations of lossy-wedge heuristics and comparisons against Malyuzhinets-type references. This report does not implement or claim validation of their alternative models. The underlying <a href="https://differt.eertmans.be/latest/reference/_autosummary/differt.em.diffraction_coefficients.html">DiffeRT UTD API</a> and the related <a href="https://github.com/NVlabs/sionna-rt/issues/85">Sionna coefficient issue</a> provide implementation context; upstream acceptance is not implied.</p>
<h2>Recommended next physics benchmark</h2><p>First specify a common boundary-value problem. Use an independently evaluated impedance-wedge reference for the matching high-loss, opaque limit, and a converged FEM/FDTD dielectric calculation for finite transmissive slabs. Validate the full Jones matrix, source/observer reversal, face relabeling, both reflection boundaries, the incident boundary, and the zero-contrast limit. A model should pass those checks together before becoming a default runtime option.</p>
<h2>Reproduce and inspect</h2><p>The evidence ZIP includes fixtures, source snapshots, all nine successful process receipts, raw coefficients, model experiments and checksums. The research scripts reside in the companion checkout; they do not import into Blender or modify installed packages. Native profiles are the default; candidates require an explicit profile list.</p>
<pre>python scripts/run_dielectric.py --differt-python PATH_TO_DIFFERT_PYTHON --sionna-python PATH_TO_SIONNA_PYTHON --llvm-library PATH_TO_LLVM_DLL --output runs/dielectric
# Existing research runtimes supporting explicit field precision:
python scripts/run_dielectric.py ... --precision float32 --profiles differt-native,sionna-native,differt-polarization,sionna-kp_depth,differt-incident,differt-symmetric_cosine
python scripts/analyze_dielectric.py runs/dielectric analysis.json
python -m pytest tests/test_dielectric_model.py</pre>
<p class="small">Preflight testing found and fixed two harness problems before the reported runs: confusing exported complex128 storage with the float32 field policy, and a duplicate metadata key in the Sionna candidate wrapper. The rejected preflight runs are not included in the 1,768 completed executions.</p>
<details><summary>Search the measured reciprocal pairs</summary><p><input id="filter" aria-label="Filter reciprocal rows" placeholder="Filter by engine, material, polarization or fixture"></p><div id="detail">{detailed_table}</div></details>
<footer>Generated {datetime.now(timezone.utc).isoformat()} · <a href="verification.json">Delivery checks and source provenance</a> · <a href="workflow_health.json">Blender and runtime preservation</a> · <a href="SHA256SUMS.txt">Checksums</a> · <a href="precision.json">Matched float32/float64 coefficients</a></footer>
</main><script>document.getElementById('filter').addEventListener('input',e=>{{let q=e.target.value.toLowerCase();document.querySelectorAll('#detail tbody tr').forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q));}});</script></html>'''
    (out/'index.html').write_text(page,encoding='utf-8')
    print('Report and scientific figures built:',out,flush=True)

if __name__=='__main__':main()

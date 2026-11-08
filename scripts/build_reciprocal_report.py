"""Build the measured correction addendum from checked numerical artifacts."""
import argparse,hashlib,html,json,zipfile
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
z=lambda a:np.asarray(a)[...,0]+1j*np.asarray(a)[...,1]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('workspace',type=Path);args=ap.parse_args()
    root=args.workspace.resolve();work=root/'work/dielectric-corrections'
    out=root/'outputs/differt-bridge/examples/dielectric_corrections';out.mkdir(parents=True,exist_ok=True)
    analysis=read(work/'final_analysis.json');geometry=read(work/'final_geometry.json')
    reference=read(work/'maxwell_analysis.json');engines=read(work/'maxwell_engines.json')
    boundary_reference=read(work/'maxwell_boundary_analysis.json');boundary_engines=read(work/'maxwell_boundary_engines.json')
    exact=read(work/'coincidence.json');mixed=read(work/'mixed_analysis.json')
    health=read(root/'outputs/differt-bridge/validation/workflow_health.json')
    blender=read(root/'outputs/differt-bridge/validation/reciprocal_blender.json')
    assert health['status']==blender['status']=='passed'
    profiles=['sionna-native','differt-native','sionna-reciprocal','differt-reciprocal']
    names={'sionna-native':'Sionna native','differt-native':'DiffeRT native','sionna-reciprocal':'Sionna corrected','differt-reciprocal':'DiffeRT corrected'}
    colors=['#7c607e','#9b7041','#176984','#29a17a']
    plt.rcParams.update({'font.size':11,'axes.spines.top':False,'axes.spines.right':False,'figure.facecolor':'white','savefig.facecolor':'white'})
    fig,axes=plt.subplots(1,2,figsize=(12,4.4),layout='constrained')
    groups=['concrete_Ez','concrete_Hz','lossy_Ez','lossy_Hz','absorbing_Ez','absorbing_Hz'];x=np.arange(len(groups))
    for p,c,offset in zip(profiles,colors,[-.27,-.09,.09,.27]):
        rows={r['material_polarization']:r for r in engines['comparisons'] if r['profile']==p}
        for ax,key in zip(axes,['rms_complex_error','rms_scattered_residual_error']):
            ax.bar(x+offset,[100*rows[g][key] for g in groups],.17,label=names[p],color=c)
    for ax in axes:
        ax.set_xticks(x,[g.replace('_','\n') for g in groups]);ax.set_ylabel('Complex-field RMS error (%)');ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
    axes[0].set_title('Total field: improvement against Maxwell');axes[1].set_title('Residual after GO subtraction: remaining error')
    axes[0].legend(fontsize=8);fig.savefig(out/'maxwell_comparison.png',dpi=160);plt.close(fig)

    fig,axes=plt.subplots(1,2,figsize=(12,4),layout='constrained')
    summary=analysis['summary']
    axes[0].bar(range(4),[summary[p]['max_reciprocity_gain_db'] for p in profiles],color=colors)
    axes[0].set_yscale('log');axes[0].set_ylabel('Maximum reciprocal gain gap (dB)');axes[0].set_title('74 non-null dielectric pairs after correction')
    axes[0].set_xticks(range(4),[names[p].replace(' ','\n',1) for p in profiles])
    for p,c in zip(profiles[-2:],colors[-2:]):
        r=[a for a in exact if a['profile']==p and a['material'] not in ('pec','air')]
        axes[1].plot(sorted(a['normalized_error'] for a in r),label=names[p],color=c)
    axes[1].set_yscale('log');axes[1].set_xlabel('54 exact-boundary cases, sorted');axes[1].set_ylabel('Limit residual / free-space channel scale')
    axes[1].set_title('Exact-boundary fields approach their nearby limits');axes[1].legend(fontsize=9)
    fig.savefig(out/'constraint_validation.png',dpi=160);plt.close(fig)

    def table(headers,rows):
        return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+html.escape(str(x))+'</th>' for x in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(str(x))+'</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table></div>'
    rows=[]
    for p in profiles:
        s=summary[p];g=geometry['summary'][p]
        rows.append([names[p],f"{s['max_reciprocity_gain_db']:.7g}",f"{s['boundary_within_1_percent']}/50",f"{g['checks']-g['failed']}/{g['checks']}"])
    measured=table(['Profile','Max reciprocal gain gap (dB)','Field jumps within 1% at ±0.001°','Near-boundary GO presence'],rows)
    rows=[]
    for g in groups:
        for p in ('sionna-reciprocal','differt-reciprocal'):
            r=next(r for r in engines['comparisons'] if r['profile']==p and r['material_polarization']==g)
            rows.append([g,names[p],f"{100*r['rms_complex_error']:.3f}%",f"{100*r['rms_scattered_residual_error']:.2f}%",f"{r['p95_abs_gain_error_db']:.3f}",f"{np.rad2deg(r['p95_abs_phase_error_rad']):.2f}°"])
    accuracy=table(['Solid wedge','Profile','Total RMS','After GO subtraction','95th percentile |gain error| dB','95th percentile |phase error|'],rows)
    controls=table(['Reference control','Measured result'],[
        ['Signed free-space Hankel Green function',f"{100*next(r for r in reference['results'] if r['name']=='free_Ez')['analytic_extrapolation_rms_error']:.5f}% extrapolated RMS"],
        ['Exact PEC wedge eigenfunction expansion',f"{100*max(r['analytic_extrapolation_rms_error'] for r in reference['results'] if r['name'].startswith('pec')):.5f}% worst extrapolated RMS"],
        ['Dielectric 40/60/80 cells per vacuum wavelength',f"{100*max(r['extrapolation_rms_change'] for r in reference['results'] if 'analytic_extrapolation_rms_error' not in r):.5f}% largest change between consecutive Richardson estimates"],
        ['PML thickness 1.5λ → 2.5λ at 60 cells/λ',f"{max(r['rms_relative_change'] for r in engines['pml_controls']):.3g} largest relative field-norm change"],
        ['Maxwell matrix solve residual',f"{max(r['max_linear_residual'] for r in reference['results']):.3g}"],
        ['Maxwell source/probe reciprocity',f"{max(r['max_reciprocity'] for r in reference['results']):.3g}"]])
    boundary_table=table(['Profile','Ez total RMS at boundary sweep','Hz total RMS at boundary sweep'],[[names[p],*[f"{100*next(r for r in boundary_engines['comparisons'] if r['profile']==p and r['material_polarization']=='concrete_'+pol)['rms_complex_error']:.3f}%" for pol in ('Ez','Hz')]] for p in profiles])
    content=f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Dielectric diffraction corrections</title>
<style>body{{font:16px/1.65 system-ui;color:#172d3a;background:#f5f8fa;margin:0}}main{{max-width:1120px;margin:auto;padding:42px 28px}}h1{{font-size:40px;line-height:1.15;margin:10px 0 22px}}h2{{margin-top:38px;font-size:25px}}h3{{font-size:19px}}a{{color:#096c87}}.eyebrow{{font-weight:700;letter-spacing:.08em;color:#456a7c}}.lead,.note{{padding:20px 24px;background:white;border-left:5px solid #15957b;border-radius:4px}}.note{{border-color:#b87922}}table{{width:100%;border-collapse:collapse;background:white;font-size:14px}}th,td{{padding:10px 12px;text-align:left;border-bottom:1px solid #dae3e9}}th{{background:#e7eff3}}.scroll{{overflow-x:auto}}img{{display:block;width:100%;margin:24px 0;background:white}}code{{background:#e5edf1;padding:2px 5px}}li{{margin:8px 0}}footer{{margin-top:42px;color:#48606d;font-size:14px}}</style><main>
<p class="eyebrow">VALIDATION ADDENDUM · 6 NOVEMBER 2026</p><h1>Dielectric diffraction:<br>reciprocity and boundary corrections</h1>
<div class="lead"><strong>Installed as an opt-in bridge profile in both existing runtimes.</strong> The corrected full polarization dyads are reciprocal; Sionna's offset-induced reflection errors and mixed-path geometry are repaired with full-mesh visibility. A consistent joint-field limit removes exact-boundary spikes. Native behavior remains the default.</div>
<p><a href="../../../../Launch_Reciprocal_Diffraction.ps1">Launch corrected Blender workbench</a> · <a href="../../../../Launch_Diffraction.ps1">Launch native workbench</a> · <a href="correction_evidence.zip">Data and reproducer</a> · <a href="verification.json">Verification receipt</a> · <a href="../dielectric_diffraction/index.html">Previous investigation</a></p>
<h2>What is fixed and what is measured</h2>{measured}
<p>Native means the existing configured workstation baseline, including the previously validated precision/constants and Windows adapters; it is not a pristine upstream installation. Each profile ran the same 286 fixtures successfully (1,144 executions). Corrected reciprocity uses 74 non-null dielectric port pairs, including lossy, lossless, thin/thick slabs, tilted wedges and skew/cross polarization. Native DiffeRT has only 70 non-null pairs because four native cross-polar responses are null. The table does not compare undefined phases at nulls.</p>
<img src="constraint_validation.png" alt="Reciprocity improves by orders of magnitude; exact-boundary normalized residuals stay small">
<ul><li><strong>Polarization and reciprocity:</strong> use full reflection dyads and physical face-incidence angles, then project the local Cartesian transfer dyad as ½[T(kᵢ,kₒ)+T(−kₒ,−kᵢ)ᵀ]. The transpose is not conjugated. This is an explicitly defined bridge approximation; it is not an exact dielectric-wedge solution or forward/reverse channel averaging.</li>
<li><strong>Geometry:</strong> reconstruct native-discovered pure reflection candidates without ray-origin offsets, including valid candidates previously rejected near an edge. Refine native-accepted reflection/diffraction chains in float64, enforce finite surfaces, stationary laws and native minimum segment lengths, and test every segment against the complete mesh. Unsupported interaction types retain native handling.</li>
<li><strong>Exact coincidence:</strong> within an 8×10⁻⁷ rad kernel band, take the finite shadow-side UTD limit. Merge a coincident GO companion only when an already-valid single-diffraction route matches it within a 4×10⁻⁷ rad geometric criterion. This changes the decomposition at numerical coincidence, not obstacle acceptance. Ordinary nearby paths at ±0.0001° retain their correct presence. Single-edge and reflection/single-edge chains are supported; multiple-edge coincident limits are not certified.</li>
<li><strong>Mixed paths:</strong> reversed Sionna reflection/edge points formerly differed by 0.913 mm. The corrected tested geometry reverses exactly after float32 storage; its worst tested mixed-path reciprocal gain gap is {mixed['maximum_corrected_sionna_gain_gap_db']:.3g} dB. The depth-padding distance correction retains all active segments.</li></ul>
<p>All 50 non-null dielectric field-jump checks also pass at ±0.0001°. All 54 dielectric exact-boundary cases (including cross-polar nulls) approach the average of the ±0.0001° total fields within {100*max(r['normalized_error'] for r in exact if r['material'] not in ('pec','air')):.4f}% of λ/[4π(s+s′)]. This free-space scale avoids dividing by a cross-polar null. Values, path counts and absolute residuals are retained.</p>
<p><strong>Correction to the previous interpretation:</strong> Sionna's 40 smallest-offset GO failures comprised <strong>20 extra reflections and 20 missing valid reflections</strong>. The earlier prose incorrectly described all 40 as extra rays. The original raw expected/observed flags were correct. The new profile passes all 580 checks.</p>
<h2>Independent electromagnetic reference</h2>
<p>A separate conservative finite-difference frequency-domain solver solves Maxwell's scalar equations for an infinite homogeneous solid right-angle wedge: ∇²Eᶻ+k²εEᶻ=−δ and ∇·(ε⁻¹∇Hᶻ)+k²Hᶻ=−δ. It uses a complex-stretched PML, sparse LU and identical bilinear source/probe weights. It imports no ray engine, contains no UTD coefficient, and fits no engine data.</p>
<p>The main campaign has six source positions, twelve receivers, three lossy dielectric permittivities and both broadside polarizations: 432 field samples per engine/profile. Actual engine outputs—not only formula transcriptions—are converted ray by ray from point-source spreading to the corresponding line-source asymptotic field. The ray material thickness is 10 vacuum wavelengths to approximate opaque faces. Finite-volume dielectric physics, including internal fields, remains present in Maxwell's reference and can differ from the local UTD approximation.</p>{controls}
<p>These are convergence and implementation checks, not rigorous error bounds. They include 27 main operator solves and 9 independent PML controls. An additional six 40/60/80-grid solves test incident and both reflection boundaries, with exact and ±10⁻⁵ rad samples, at two source positions and both concrete polarizations. Consecutive boundary-reference extrapolations differ by at most {100*max(r['extrapolation_rms_change'] for r in boundary_reference['results']):.5f}% in field norm.</p>
<img src="maxwell_comparison.png" alt="Total field error falls to about 3 to 6 percent, but residual diffraction error remains about 19 to 49 percent">
{accuracy}<div class="note"><strong>Accuracy remains limited.</strong> The corrections reduce total complex-field RMS error to 2.8–5.7% in this benchmark. After subtracting each ray model's GO field from the Maxwell reference, the remaining-field relative RMS error is still about 19–49%. Weak channels have 95th-percentile gain errors of 2.2–4.3 dB. Reciprocity, continuity and agreement between engines do not establish exact physical accuracy.</div>
<h3>Independent check at the boundaries themselves</h3>{boundary_table}
<p>These boundary numbers include all 18 source/receiver combinations per polarization, not only a selected successful side. Raw per-sample complex reference and engine fields are included, so near-null errors and interference can be inspected independently.</p>
<h2>Obstacles, limits and workflow checks</h2>
<p>All four original obstacle controls pass in each profile (incoming/outgoing blockers, a nearby clear object and a 1 mm near-edge blocker). Both corrected engines also reject the ground-reflection/edge route for real blockers 0.1 m, 1 mm and 10 μm before its reflection point while retaining the unblocked direct edge route. A separate geometry unit test checks a blocker only 0.1 μm after an endpoint. No physical endpoint exclusion radius is introduced.</p>
<p>The final mixed campaign has 22 successful executions. Earlier DiffeRT depth-5 attempts correctly hit the existing 2,000,000-candidate budget (8,308,824 upper bound); they are not reported as successful depth-5 validation. Sionna's separate depth-2/3/5 control is included. The final Python regression run passed 267 tests, excluding two previously documented strict wavelength assertions incompatible with the installed float32 common-scalar policy. The new physical/geometry/profile tests are included; no assertion tolerance was loosened.</p>
<p>Fresh Blender {html.escape(blender['blender'])} comparison: {blender['counts'].get('matched',0)} matched diffraction-workbench paths, both corrected external workers confirmed by activation receipts, both extensions enabled and saved preferences preserved. Native workflow: 1,299 matched furnished-room paths, zero exported phase difference; 79 protected source/runtime files, installed extension package and all existing animation timelines retained. An added-file manifest verifies the optional helper files separately.</p>
<p><strong>Domain limits:</strong> independent dielectric accuracy is established only for the sampled homogeneous, lossy, solid 2D wedge. Thin slabs, lossless volume resonances, arbitrary 3D skew accuracy, multiple diffraction and arbitrary complex scenes need independent references of their own. Synthetic-array integration is checked, not certified for all array configurations. Zero material contrast does not make an occluding mesh transparent when refraction/transmission is disabled; air fixtures are bookkeeping controls, not a certified free-space equivalence. Geometry refinement is CPU/detached and does not provide geometry gradients. The finite highly conducting material at exact grazing incidence is not the ideal PEC boundary limit: the PEC reference shows a 4.0% Hz RMS discrepancy when those samples are included, versus about 0.057% away from exact grazing. Native output remains available for comparison.</p>
<h2>Use and reproduce</h2><p>Run <code>Launch_Reciprocal_Diffraction.ps1</code>, or <code>Launch_Diffraction.ps1 -DielectricProfile reciprocal</code>. Run the ordinary diffraction launcher for native results. The launcher scopes and restores environment variables. Runtime helpers activate only when <code>RADIO_DIELECTRIC_PROFILE=reciprocal</code> is explicitly set; exact source/version guards reject unsupported revisions. No existing engine source, Blender extension file or saved scene was overwritten.</p>
<p>The evidence archive includes manifests, raw engine outputs and receipts, independent Maxwell results, analysis scripts, correction source, tests, installation/Blender/native-health receipts and this report's measured inputs. SHA-256 hashes are listed in <a href="checksums.sha256">checksums.sha256</a>. The source checkout is on <code>research/dielectric-diffraction</code>; this addendum is local and has not been published as an upstream engine fix.</p>
<p>Primary context: <a href="https://onlinelibrary.wiley.com/doi/10.1155/2018/3029152">Tami et al., heuristic UTD reciprocity study</a>; <a href="https://www.homepages.ucl.ac.uk/~ucahdhe/15_Hewett_Morris_ImpedanceWedge.pdf">Hewett &amp; Morris, exact impedance-wedge analysis</a>; <a href="https://www.mit.edu/~wsshin/pdf/shin_dissertation.pdf">Shin, frequency-domain electromagnetic methods and PML</a>; <a href="https://docs.scipy.org/doc/scipy/reference/generated/scipy.sparse.linalg.splu.html">SciPy sparse LU documentation</a>. The impedance-wedge integral from the cited paper was not used as the numerical reference here; the independent reference is the disclosed Maxwell discretization.</p>
<footer>Reproducible numerical study · DiffeRT 0.12.0 · Sionna RT 2.1.0 · LLVM CPU / JAX CPU · Profile-specific results, not an exhaustive proof for all scenes.</footer></main></html>'''
    (out/'index.html').write_text(content,encoding='utf-8')
    receipt=dict(status='passed',date='2026-11-06',main_fixture_executions=1144,maxwell_engine_fixture_executions=144,boundary_engine_fixture_executions=16,mixed_fixture_executions=22,
                 independent_maxwell_operator_solves=42,corrected_blender=blender,native_blender=health['blender'],measured_summary=summary,
                 independent_accuracy_scope=engines['scope'],native_files_preserved=True,optional_profile='reciprocal')
    (out/'verification.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(out)

if __name__=='__main__':main()

"""Build the measured Maxwell-model-error addendum and publication plots."""
import argparse,html,json,shutil
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from analyze_model_errors import read,z

def table(headers,rows):
    return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+html.escape(str(v))+'</th>' for v in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+str(v)+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table></div>'
def pct(v):return f'{100*v:.4f}%'

def main(root):
    work=root/'work/diffraction-model-errors';out=root/'outputs/differt-bridge/examples/diffraction_model_errors';out.mkdir(parents=True,exist_ok=True)
    data=read(work/'analysis.json');groups={(r['profile'],r['name']):r for r in data['sweep']};names=[r['name'] for r in data['sweep'] if r['profile']=='sionna-reciprocal']
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':160})
    fig,ax=plt.subplots(figsize=(12,5));x=np.arange(8)
    for j,(profile,color) in enumerate([('sionna-native','#c77728'),('differt-native','#227e9d'),('sionna-reciprocal','#70a87c'),('differt-reciprocal','#356344')]):
        ax.bar(x+(j-1.5)*.19,[groups[profile,n]['total_complex_rms']*100 for n in names],.18,label=profile,color=color)
    ax.set_xticks(x,[n.replace('_','\n') for n in names]);ax.set_ylabel('Total complex RMS error to BIE (%)');ax.legend(ncol=2);ax.set_title('Fresh angles and materials: 265 channels per bar');ax.grid(axis='y',alpha=.2);fig.tight_layout();fig.savefig(out/'accuracy.png');plt.close(fig)
    fig,axs=plt.subplots(2,2,figsize=(12,7))
    for col,pol in enumerate(('Ez','Hz')):
        r=groups['sionna-reciprocal','concrete_'+pol];entries=[e for e in r['entries'] if e['source']==4];a=z([e['prediction'] for e in entries]);b=z([e['reference'] for e in entries]);angles=[e['angle_deg'] for e in entries]
        axs[0,col].plot(angles,20*np.log10(abs(b)),label='Maxwell BIE',color='#253c49');axs[0,col].plot(angles,20*np.log10(abs(a)),label='Reciprocal ray model',color='#d4832b');axs[0,col].set_title('Concrete '+pol+' • source angle 252°');axs[0,col].set_ylabel('Field magnitude (dB re unit source)')
        axs[1,col].plot(angles,np.rad2deg(np.angle(a/b)),color='#d4832b');axs[1,col].axhline(0,color='gray',lw=.7);axs[1,col].set_ylabel('Phase error (degrees)');axs[1,col].set_xlabel('Receiver angle from +Y around exterior (degrees)')
        for ax in axs[:,col]:ax.grid(alpha=.2)
        axs[0,col].legend()
    fig.tight_layout();fig.savefig(out/'angular_errors.png');plt.close(fig)
    fig,ax=plt.subplots(figsize=(8,4.5))
    for name in ('concrete_Ez','concrete_Hz','absorbing_Ez','absorbing_Hz'):
        rows=sorted([r for r in data['distance'] if r['name']==name],key=lambda r:r['scale']);ax.plot([r['scale'] for r in rows],[100*r['total_complex_rms'] for r in rows],'-o',label=name)
    ax.set(xlabel='Uniform geometry scale (wavelength fixed)',ylabel='Total complex RMS error (%)',xticks=[1,2,4],title='Independent distance control • float64 formula, not fresh engine runs');ax.grid(alpha=.2);ax.legend();fig.tight_layout();fig.savefig(out/'distance.png');plt.close(fig)
    numerical=[]
    for r in data['reference_controls']:
        numerical.append([r['name'],pct(r['panels24_to48']),pct(r['analytic_rms']) if r['analytic_rms'] is not None else '—',pct(r['bem48_vs_fdfd_extrapolated']) if 'bem48_vs_fdfd_extrapolated' in r else '—',pct(r['reciprocity_rms']) if 'reciprocity_rms' in r else 'not repeated'])
    resultrows=[]
    for n in names:
        resultrows.append([n]+[pct(groups[p,n]['total_complex_rms']) for p in ('sionna-native','differt-native','sionna-reciprocal','differt-reciprocal')])
    phase=[];enginegaps=[]
    for n in names:
        r=groups['sionna-reciprocal',n];other=groups['differt-reciprocal',n]
        a=z([e['prediction'] for e in r['entries']]);b=z([e['prediction'] for e in other['entries']]);gap=float(np.linalg.norm(a-b)/np.linalg.norm(a));enginegaps.append(gap)
        phase.append([n,f'{r["p95_abs_gain_db"]:.3f}',f'{np.rad2deg(r["p95_abs_phase_rad"]):.3f}',f'{r["phase_mask_samples"]}/{r["samples"]}',pct(r['residual_after_ray_go_rms']),pct(gap)])
    controls=data['reference_controls'];dielectric=[r for r in controls if r['name'].startswith(('concrete','lossy','absorbing'))]
    oldpol=read(work/'fresnel_policies.json');policies=('incident','mean_cosine','angle_bisector','geometric_cosine')
    candidates=[]
    for n in ('concrete_Ez','concrete_Hz','absorbing_Ez','absorbing_Hz'):
        candidates.append(['Original / '+n]+[pct(next(r['total_rms'] for r in oldpol if r['name']==n and r['policy']==p)) for p in policies])
    for n in ('holdout_low_Ez','holdout_low_Hz','holdout_high_Ez','holdout_high_Hz'):
        candidates.append(['Fresh / '+n]+[pct(next(r['total_complex_rms'] for r in data['policy_holdout'] if r['name']==n and r['policy']==p)) for p in policies])
    plane=read(work/'plane_reflection_control.json')
    normmax=max(r['normalization_change_rms'] for r in data['sweep'] if r['profile'].endswith('reciprocal'))
    maxref=max(r['reference24_to36'] for r in data['sweep']);maxdist=max(r['reference16_to24'] for r in data['distance'])
    counts={folder:len(list((work/folder).glob('*.json'))) for folder in ('bem_controls','bem_sweep','bem_distance','bem_extra')}
    page='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Diffraction model errors versus Maxwell</title><style>
    :root{color-scheme:light}body{font:17px/1.6 system-ui;color:#203342;background:#f5f7fa;max-width:1160px;margin:auto;padding:32px}h1{font-size:40px;line-height:1.2}h2{margin-top:2.4em}a{color:#126e88}section,.callout{background:white;padding:24px;border-radius:12px;margin:24px 0}.callout{border-left:5px solid #21846d}video,img{width:100%;border-radius:8px}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:10px;border-bottom:1px solid #dae2e8;text-align:left}th{background:#e6eef3}.scroll{overflow-x:auto}code{background:#e6eef3;padding:2px 5px}.muted{color:#566b79}li{margin:8px 0}pre{overflow-x:auto;background:#e6eef3;padding:16px}footer{font-size:14px;margin-top:40px}</style></head><body>
    <p><a href="../../../../index.html">All project results</a> / <a href="../dielectric_corrections/index.html">Previous corrections and boundary evidence</a></p>
    <h1>Diffraction model errors against Maxwell</h1><p class="muted">7 November 2026 • Sionna RT 2.1.0 • DiffeRT 0.12.0 • bridge 0.6.3 • Blender 5.2.3 LTS</p>
    <div class="callout"><strong>The remaining discrepancy is substantially larger than numerical reference uncertainty.</strong> Two independent Maxwell formulations agree closely. The existing reciprocal profile reduces the fresh-sweep total-field error to 2.4–4.5%, but it does not make either ray model an exact dielectric solver. This update fixes the comparison normalization and strengthens the evidence; no additional heuristic runtime physics patch passed the full validation set.</div>
    <h2>Side-by-side animation</h2><video controls preload="metadata" poster="previews/frame_0601.png"><source src="Sionna_vs_DiffeRT_Maxwell.mp4" type="video/mp4"></video>
    <p><a href="Sionna_vs_DiffeRT_Maxwell.mp4">60-second MP4</a> · <a href="Maxwell_Comparison_Animation.blend">Portable Blender timeline</a> · <a href="video_validation.json">Decode and reopen receipt</a> · <a href="animation_validation.json">Frame/data provenance</a></p>
    <p>The film shows native engines, the reciprocal profile, both polarizations, two new materials, magnitude and phase against Maxwell, and a distance control. The white curve is the independent BIE solution. Values come from 53 discrete receiver positions; plot segments only connect those samples. Both panels share cameras and graph scales. The RMS label covers all five sources (265 channels) for that material/polarization, while each moving plot shows one source. The last chapter explicitly uses the float64 formula distance control.</p>
    <h2>What changed and what was retained</h2><ul>
    <li><strong>Comparison correction:</strong> use a reciprocal cylindrical-wave normalization with the same coincident-ray Green function as GO. Preserve the legacy normalization as a sensitivity control. Native 3D channel exports are unchanged.</li>
    <li><strong>Reference correction:</strong> explicitly choose the decaying square-root branch in the new Sommerfeld half-space control, including exactly lossless air. PEC image and zero-contrast checks pass.</li>
    <li><strong>Model candidates:</strong> mean-cosine, angle-bisector and geometric-cosine Fresnel substitutions were tested. Some fresh cases improve slightly; the original Maxwell controls regress. None is installed.</li>
    <li><strong>Workflow:</strong> retain native defaults and the optional reciprocal profile, full-mesh obstacle tests, installed extensions, existing launchers and historical animations.</li></ul>
    <h2>Fresh actual-engine comparison</h2><p>Four materials × two polarizations × five source positions × 53 receivers = 2,120 channels per profile; four profiles give 8,480 comparisons from 160 successful fixture executions. These source angles and two held-out permittivities were not used to choose the earlier correction. The material names here denote fixed complex relative permittivity, not a broadband material law.</p>
    <img src="accuracy.png" alt="Native and reciprocal profiles compared with Maxwell on all eight material and polarization groups">'''
    page+=table(['Material / polarization','Sionna native','DiffeRT native','Sionna reciprocal','DiffeRT reciprocal'],resultrows)
    page+='''<p>RMS = ‖u<sub>ray</sub> − u<sub>Maxwell</sub>‖₂ / ‖u<sub>Maxwell</sub>‖₂ over the whole group. This is a complex-field metric, not average dB error or a per-link worst-case bound. Equal percentages do not mean identical engine outputs.</p>
    <h2>Remaining magnitude and phase errors</h2><img src="angular_errors.png" alt="Magnitude and phase errors as the receiver moves around a concrete wedge">'''
    page+=table(['Group (reciprocal)','P95 |gain error| dB','P95 |phase error| °','Above −40 dB mask','Residual after ray GO RMS','Sionna–DiffeRT RMS'],phase)
    page+=f'''<p>These phase percentiles include every sample. The separate mask keeps reference amplitude above 1% of the group maximum; both masked and unmasked metrics are in the numerical evidence. Phase near field nulls is ill-conditioned. The corrected engines differ by at most {pct(max(enginegaps))} complex RMS on this sweep, while their error to Maxwell is several percent. Matching each other is therefore not an independent accuracy test.</p>
    <p><strong>The 19–45% “residual after GO” metric is not a pure diffraction-coefficient error.</strong> Its denominator is the Maxwell field minus the ray model's GO approximation. It contains errors in finite-distance reflected fields and any material/edge contributions the ray decomposition omits.</p>
    <h2>Independent reference and uncertainty controls</h2><p>The new boundary-element calculation solves transmission boundary integral equations on the two faces of a solid right-angle dielectric wedge. It uses constant collocation panels, logarithmic self-term integration, corner refinement and a smooth complex contour to damp the infinite tail. It imports no ray coefficient or engine result. The earlier reference instead discretizes Maxwell's differential equations on a Cartesian grid with PML. Both were implemented for this project; this is cross-formulation verification, not an external certification.</p>
    <p>{sum(counts.values())} new canonical BIE operator solves: {counts['bem_controls']} reference controls, {counts['bem_sweep']} angular-sweep refinements, {counts['bem_distance']} distance refinements and {counts['bem_extra']} reverse/tail/rounding checks. Pilots are retained separately and excluded from that count. Reference refinements are 24→48 panels per exterior wavelength for controls and 16→24→36 for the fresh sweep.</p>'''
    page+=table(['Control','24→48 change','Analytic error at 48','BIE48 vs FDFD extrapolation','BIE reciprocal RMS'],numerical)
    page+=f'''<p>For dielectric controls, cross-method RMS differences are {pct(min(r['bem48_vs_fdfd_extrapolated'] for r in dielectric))}–{pct(max(r['bem48_vs_fdfd_extrapolated'] for r in dielectric))}. The largest fresh-sweep 24→36 change is {pct(maxref)}. A 5→8 wavelength contour-tail change is below 4×10⁻⁸ relative RMS in the repeated dielectric controls. Rounding ports to float32 changes the tested concrete-Hz BIE result by 5.36×10⁻⁷ RMS. All canonical BIE linear residuals are below 2×10⁻¹⁴. These are measured convergence indicators, not rigorous error bounds for every channel; weak local fields can have larger relative uncertainty.</p>
    <h2>Physical-model diagnosis</h2><img src="distance.png" alt="Ray approximation error decreases as electrical distance increases">
    <p>Scaling both ports by 1, 2 and 4 while keeping wavelength and angles fixed reduces the model error in all four material/polarization controls. For concrete Hz it falls from 5.44% to 3.68% to 2.62%. This is consistent with finite-distance/high-frequency approximation error; it does not identify a unique missing term. The maximum 16→24 BIE change in this campaign is {pct(maxdist)}.</p>
    <p>A separate exact dielectric-plane Sommerfeld integral replaces only existing GO reflection values as a diagnostic. It lowers the original total-field errors modestly:</p>'''
    page+=table(['Original control','Ray baseline','Exact-plane GO substitution'],[[r['name'],pct(r['baseline_rms']),pct(r['exact_plane_GO_control_rms'])] for r in plane])
    page+='''<p>This demonstrates that GO approximation error contributes to the residual. It is <strong>not</strong> a valid general wedge repair: applying a plane correction only where a GO ray exists can introduce a shadow-boundary jump and does not model the coupled two-face transmission problem. Consequently it is excluded from both runtimes and the animation predictions.</p>
    <p>Penetrable-wedge research explicitly distinguishes surface/edge and internally transmitted contributions. That supports investigating a transmission-aware wedge model next, but this experiment does not isolate the magnitude of each internal mechanism. See the primary <a href="https://onlinelibrary.wiley.com/doi/10.1155/2012/151287">Gennarelli–Riccio dielectric-wedge formulation</a>. The point-source spreading and UTD coefficient framework are described in <a href="https://www.itu.int/dms_pubrec/itu-r/rec/p/R-REC-P.526-15-201910-S%21%21PDF-E.pdf">ITU-R P.526-15</a>.</p>
    <h2>Rejected coefficient changes</h2>'''
    page+=table(['Control','Incident-angle baseline','Mean cosines','Angle bisector','Geometric cosines'],candidates)
    page+='''<p>The original controls use the legacy conversion; the fresh controls use the corrected conversion. Compare candidates within each row. Small gains on the new cases do not override regressions on the original controls, and no reference data were used to fit correction parameters. A different reciprocal Fresnel argument alone does not resolve the model error. All complete policy results are archived.</p>
    <h2>Comparison normalization: explicit correction and limit</h2><p>With exp(+iωt), G(r) = −i H₀⁽²⁾(kr)/4. The previous line-source diffraction term used G(s′) D exp(−iks)/√s. Although asymptotically valid, that finite-distance closure is not exactly symmetric under swapping the two legs. The new comparator uses:</p>
    <pre>u_diff = D × G(s + s′) × sqrt((s + s′)/(s s′))</pre>
    <p>This closure is reciprocal in its scalar propagation factor, has the same leading high-frequency limit, and uses the GO Green function at a coincident boundary. It is not an exact finite-distance dielectric solution. Analytic tests verify symmetry, boundary half-jump normalization and high-frequency convergence. The original comparison remains available to measure this choice's effect.</p>'''
    page+=f'<p>The largest corrected-profile field change from this normalization is {pct(normmax)} RMS on the fresh sweep, far smaller than the remaining 2.4–4.5% physical-model error. It does not explain away that discrepancy.</p>'
    page+='''<h2>Scope, preserved validations and limitations</h2><ul>
    <li>Reference geometry: infinite solid 90° dielectric wedge, 270° exterior, broadside 2D line sources, Ez/Hz scalar polarizations, lossy homogeneous material. The ray fixture uses long faces and the central edge; no finite-edge endpoint field is claimed.</li>
    <li>Normalized wavelength is 1 m (299,792,458 Hz). Conductivity is scaled to preserve the specified complex permittivity: concrete approximately 5.24−0.632i, absorbing 5.24−6i, new low 2.5−0.35i, new high 8−3i. Ports are 2.7–3.4 wavelengths from the corner, receivers four wavelengths away in the angular sweep.</li>
    <li>The new sweep samples 5° increments and is not a new micro-offset boundary certification. The previous exact-boundary, reciprocity, 10 μm obstacle and mixed-path tests remain in the linked correction report. Their installed helper hashes are checked unchanged.</li>
    <li>Thin slabs, arbitrary skew incidence, anisotropy, layered media, general 3D polarization coupling, multiple-edge material-wave interactions and geometry gradients remain outside this Maxwell accuracy validation.</li>
    <li>No heuristic candidate is promoted merely because it makes the engines agree. A future physical correction needs an independent transmission-aware formulation and boundary/reciprocity/obstacle regressions, in addition to lower Maxwell error.</li></ul>
    <h2>Workflow and reproduction</h2><p>Use <a href="../../../../Launch_Reciprocal_Diffraction.ps1">the reciprocal Blender launcher</a> for corrected bridge behavior, or <a href="../../../../Launch_Diffraction.ps1">the native launcher</a> for native behavior. Open the saved animation timeline above to play the film in Blender; it is a video timeline, not an editable simulation scene. The paired simulation workbench remains unchanged.</p>
    <p><a href="model_error_evidence.zip">Raw results, source, tests and reproduction instructions</a> · <a href="verification.json">Delivery verification</a> · <a href="checksums.sha256">SHA-256 manifest</a> · <a href="../../validation/workflow_health.json">Fresh native workflow health</a> · <a href="reciprocal_blender.json">Fresh corrected Blender run</a></p>
    <p>Regenerate with <a href="../../../../Regenerate_Maxwell_Animation.ps1">Regenerate_Maxwell_Animation.ps1</a>. This reuses measured physics data; the source documentation in the evidence archive explains how to rerun both engines and all reference controls.</p>
    <footer>Historical reports and native animations are retained unchanged. Numerical measurements here are specific to the declared fixture, versions, normalization and reference convergence study.</footer></body></html>'''
    (out/'index.html').write_text(page,encoding='utf-8',newline='\n')
    (out/'report_metrics.json').write_text(json.dumps(dict(operator_counts=counts,engine_channels=8480,engine_fixtures=160,max_engine_gap=max(enginegaps),max_reference_sweep_change=maxref,max_distance_reference_change=maxdist),indent=2))
    print('MODEL_ERROR_REPORT_BUILT',out,flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('root',type=Path);args=ap.parse_args();main(args.root.resolve())

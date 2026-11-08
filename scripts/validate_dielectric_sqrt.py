"""Independent float64 Maxwell slab, stable-root and derivative controls."""
import json,sys
from pathlib import Path
import numpy as np
import mitsuba as mi
mi.set_variant('llvm_ad_mono_polarized')
import drjit as dr
import sionna.rt.utils.electromagnetics as em
from reciprocal_corrections import install_sionna_opaque_slab
from dielectric_sqrt_candidate import install,stable_complex_sqrt

def reference(er,loss,c,d):
    eta=er-1j*loss;a=np.sqrt(eta-(1-c*c));q=2*np.pi*d*a
    rs=(c-a)/(c+a);rp=(eta*c-a)/(eta*c+a);e=np.exp(-1j*q);e2=e*e
    return np.array([rs*(1-e2)/(1-rs*rs*e2),rp*(1-e2)/(1-rp*rp*e2),(1-rs*rs)*e/(1-rs*rs*e2),(1-rp*rp)*e/(1-rp*rp*e2)])

def main(output):
    install_sionna_opaque_slab()
    samples=[(er,loss,c,d) for er in (2.5,5.24,8.) for loss in (0.,1e-8,1e-6,.0001,.001,.01,.35,.632143019,6.,1e5,6e13,6e17)
             for c in (.0001,.01,.2,.5,.9,1.) for d in (.0001,.1,1.,10.)]
    er,loss,c,d=np.array(samples,dtype=np.float32).astype(float).T
    def calc():return np.stack([np.asarray(x) for x in em.itu_coefficients_single_layer_slab(mi.Float(c),mi.Complex2f(mi.Float(er),mi.Float(-loss)),mi.Float(d),mi.Float(1.))])
    old=calc();install();new=calc();ref=reference(er,loss,c,d)
    errs=np.max(abs(new-ref),axis=0);before=np.max(abs(old-ref),axis=0)
    gradient=[]
    for er0,loss0,cos0,d0 in [(8.,.001,.2,10.),(5.24,.01,.5,1.),(2.5,.35,.9,.1)]:
        v=mi.Float(loss0);dr.enable_grad(v)
        f=em.itu_coefficients_single_layer_slab(mi.Float(cos0),mi.Complex2f(er0,-v),mi.Float(d0),mi.Float(1.))[1]
        objective=dr.real(f)+.37*dr.imag(f);dr.backward(objective);actual=float(np.asarray(dr.grad(v))[0])
        h=1e-6;func=lambda l:reference(er0,l,cos0,d0)[1];expected=((func(loss0+h)-func(loss0-h))/(2*h));expected=expected.real+.37*expected.imag
        gradient.append(dict(parameters=[er0,loss0,cos0,d0],autodiff=actual,finite_difference=float(expected),relative_error=float(abs(actual-expected)/max(abs(expected),1e-8))))
    # Direct root residual, including passive evanescence and extreme scales.
    values=np.array([complex(x,-y) for x in (-1e20,-8.,-.01,0.,1e-20,1.,8.,1e20) for y in (0.,1e-20,1e-8,.001,1.,1e20)],np.complex64)
    roots=np.asarray(stable_complex_sqrt(mi.Complex2f(mi.Float(values.real),mi.Float(values.imag))))
    refroot=np.sqrt(values.astype(np.complex128));root_error=float(np.max(abs(roots-refroot)/np.maximum(abs(refroot),1e-30)))
    def pairs(v):return np.stack([v.real,v.imag],axis=-1).tolist()
    result=dict(status='passed' if np.isfinite(new).all() and float(errs.max())<2e-4 and root_error<3e-7 and max(r['relative_error'] for r in gradient)<.003 else 'failed',samples=len(samples),baseline_max_absolute_error=float(before.max()),patched_max_absolute_error=float(errs.max()),baseline_rms=float(np.sqrt(np.mean(abs(old-ref)**2))),patched_rms=float(np.sqrt(np.mean(abs(new-ref)**2))),root_samples=len(values),root_max_relative_error=root_error,gradients=gradient,parameters=np.stack([er,loss,c,d],axis=-1).tolist(),baseline=pairs(old.T),patched=pairs(new.T),reference=pairs(ref.T))
    output.write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('parameters','baseline','patched','reference')}),flush=True)
    if result['status']!='passed':raise SystemExit(1)

if __name__=='__main__':main(Path(sys.argv[1]))

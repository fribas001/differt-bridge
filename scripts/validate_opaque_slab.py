"""Run in Sionna Python: native/candidate slabs versus float64 Maxwell BCs."""
import sys,json
from pathlib import Path
import numpy as np
import mitsuba as mi
mi.set_variant('llvm_ad_mono_polarized')
import sionna.rt.utils.electromagnetics as em
from reciprocal_corrections import install_sionna_opaque_slab

def main(output):
    samples=[(er,loss,c,d) for er in (1.,2.5,5.24,8.) for loss in (0.,.001,.35,6.,1e5,6e9,6e13,6e15,6e17)
             for c in (.0001,.01,.2,.5,.9,1.) for d in (.0001,.1,1.,10.) if not(er==1. and loss==0.)]
    er,loss,c,d=np.array(samples).T;eta=er-1j*loss
    def calc(f):return np.stack([np.asarray(x) for x in f(mi.Float(c),mi.Complex2f(mi.Float(er),mi.Float(-loss)),mi.Float(d),mi.Float(1.))])
    before=calc(em.itu_coefficients_single_layer_slab);detail=install_sionna_opaque_slab();after=calc(em.itu_coefficients_single_layer_slab)
    a=np.sqrt(eta-(1-c*c));q=2*np.pi*d*a
    rs=(c-a)/(c+a);rp=(eta*c-a)/(eta*c+a);e=np.exp(-1j*q);e2=e*e
    ref=np.array([rs*(1-e2)/(1-rs*rs*e2),rp*(1-e2)/(1-rp*rp*e2),(1-rs*rs)*e/(1-rs*rs*e2),(1-rp*rp)*e/(1-rp*rp*e2)])
    good=np.isfinite(before).all(axis=0);fixed=np.isfinite(after).all(axis=0)
    opaque=q.imag<-80.;unchanged=np.array_equal(before[:,~opaque],after[:,~opaque],equal_nan=True)
    error=np.max(abs(after-ref),axis=0);max_fixed=float(np.max(error[opaque]));worst=int(np.argmax(error))
    result=dict(status='passed' if fixed.all() and unchanged and max_fixed<3e-6 else 'failed',samples=len(samples),native_nonfinite=int((~good).sum()),patched_nonfinite=int((~fixed).sum()),opaque_samples=int(opaque.sum()),opaque_max_absolute_coefficient_error=max_fixed,nonopaque_bitwise_unchanged=unchanged,nonopaque_max_error=float(np.max(error[~opaque])),largest_error_sample=samples[worst],patch=detail)
    def pairs(values):return [[[float(v.real),float(v.imag)] if np.isfinite(v) else None for v in row] for row in values.T]
    output.with_name('opaque_slab_samples.json').write_text(json.dumps(dict(parameters=['relative_permittivity','loss','cos_incidence','thickness_wavelengths'],samples=samples,coefficients=['TE_reflection','TM_reflection','TE_transmission','TM_transmission'],native=pairs(before),patched=pairs(after),maxwell_float64=pairs(ref)),indent=2,allow_nan=False),encoding='utf-8')
    output.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result),flush=True)
    if result['status']!='passed':raise SystemExit(1)

if __name__=='__main__':main(Path(sys.argv[1]))

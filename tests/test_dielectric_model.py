"""Independent PEC/Fresnel constraints and deliberately limited dielectric hypotheses."""
import copy,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from dielectric_cases import make,cases
from dielectric_model import coefficient,go_coefficient
from diffraction_physics_cases import pec_channel

def test_analytic_specular_ports_are_reciprocal_including_cross_polarization():
    for pol in ('VV','HH','VH','HV'):
        c=make('f',60,119,pol,'concrete',z=(-3,5))
        r=copy.deepcopy(c);r['tx'],r['receivers']=c['receivers'][0],[c['tx']];r['tx_pol'],r['rx_pol']=c['rx_pol'],c['tx_pol']
        a=go_coefficient(c,'reflection0');b=go_coefficient(r,'reflection0')
        assert a is not None and b is not None
        assert abs(a[0])>1e-8
        np.testing.assert_allclose(a,b,rtol=1e-12,atol=1e-14)

def test_corrected_formulas_retain_independent_pec_reference():
    chosen=[c for c in cases() if c['study']['kind']=='reciprocity' and c['study']['material']=='pec']
    assert len(chosen)==44
    for c in chosen:
        reference=pec_channel(c)
        for profile in ('differt-polarization','differt-incident','differt-symmetric_cosine','sionna-kp_depth'):
            value,_=coefficient(c,profile)
            assert abs(value-reference)<max(1e-10,abs(reference)*1e-4),(c['name'],profile,value,reference)

def test_broadside_correction_does_not_certify_skew_boundary():
    selected={c['name']:c for c in cases()}
    for pol in ('VV','HH'):
        c=selected[f'boundary_concrete_broadside_reflection0_{pol}']
        a,_=coefficient(c,'differt-polarization',4);b,_=coefficient(c,'differt-polarization',6)
        g=go_coefficient(c,'reflection0',4);assert g is not None
        assert abs((b-a)/g[0]-1)<5e-5
    c=selected['boundary_concrete_skew_reflection0_VH'];g=go_coefficient(c,'reflection0',4);assert abs(g[0])>1e-8
    a,_=coefficient(c,'differt-polarization',4);b,_=coefficient(c,'differt-polarization',6)
    assert abs((b-a)/g[0])<1e-10  # Missing cross component cannot cancel the GO transition.
    a,_=coefficient(c,'sionna-kp_depth',4);b,_=coefficient(c,'sionna-kp_depth',6)
    assert abs((b-a)/g[0]-1)<5e-5

def test_symmetric_cosine_is_reciprocal_but_is_not_an_accuracy_reference():
    selected={c['name']:c for c in cases()}
    for c in selected.values():
        source=c['study'].get('reverse_of')
        if not source:continue
        a,_=coefficient(selected[source],'differt-symmetric_cosine');b,_=coefficient(c,'differt-symmetric_cosine')
        np.testing.assert_allclose(a,b,rtol=5e-12,atol=1e-14)

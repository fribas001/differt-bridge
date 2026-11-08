"""Analytic controls for new comparison/reference code, independent of ray fits."""
import sys
from pathlib import Path
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from line_source_comparison import kernel
from ray_wedge2d import green
from halfspace_reference import reflected
from wedge_bem_reference import WedgeBEM
from maxwell2d_reference import free_green,pec_green

def test_reciprocal_line_conversion_and_boundary_normalization():
    s=np.array([.75,2.,5.,11.]);d=np.array([7.,4.,2.,1.])
    assert np.allclose(kernel(s,d),kernel(d,s),rtol=1e-15,atol=0)
    # A shadow-boundary UTD half-jump must use the coincident GO Green function.
    jump=.5*np.sqrt(s*d/(s+d))
    assert np.allclose(jump*kernel(s,d),.5*green(s+d),rtol=2e-15,atol=0)
    assert np.linalg.norm(kernel(s,d,'legacy')-kernel(d,s,'legacy'))>1e-6

def test_line_conversion_high_frequency_limit():
    error=[]
    for scale in (1,10,100):
        a,b=kernel(2*scale,7*scale),kernel(2*scale,7*scale,'legacy')
        error.append(abs((a-b)/a))
    assert error[2]<error[1]/9<error[0]/81
    with pytest.raises(ValueError):kernel(0,1)

@pytest.mark.parametrize('pol',['Ez','Hz'])
@pytest.mark.parametrize('axis',[0,1])
def test_sommerfeld_exact_pec_image_and_air(pol,axis):
    source=np.array([-1.1,-.7]);receiver=np.array([-2.4,-1.3]);image=source.copy();image[axis]*=-1
    expected=(-1 if pol=='Ez' else 1)*green(np.linalg.norm(receiver-image))
    assert abs(reflected(source,receiver,1,pol,axis,boundary='pec')-expected)<1e-10
    assert abs(reflected(source,receiver,1,pol,axis))<1e-10

@pytest.mark.parametrize('pol',['Ez','Hz'])
def test_sommerfeld_dielectric_reciprocity(pol):
    a,b=[-1.1,.8],[-2.3,-.2]
    assert abs(reflected(a,b,2.5-.35j,pol)-reflected(b,a,2.5-.35j,pol))<1e-13

@pytest.fixture(scope='module')
def bem():return WedgeBEM(12,6,5)

@pytest.mark.parametrize('pol',['Ez','Hz'])
@pytest.mark.parametrize('boundary',['air','pec'])
def test_bie_analytic_controls(bem,pol,boundary):
    sources=np.array([[-2.5,1.5],[-2.5,-1.5]])
    receivers=np.array([[-4.,-1.],[1.,-4.],[-.5,4.]])
    actual,meta=bem.solve(sources,receivers,1+0j,pol,'pec' if boundary=='pec' else 'dielectric')
    expected=np.array([[pec_green(s,r,pol) if boundary=='pec' else free_green(s,r) for r in receivers] for s in sources])
    assert np.linalg.norm(actual-expected)/np.linalg.norm(expected)<.006
    assert meta['linear_residual']<1e-12

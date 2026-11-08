"""Isolated test entry point for the production material-root correction."""
from reciprocal_corrections import stable_material_sqrt as stable_complex_sqrt

def install():
    import sionna.rt.utils.electromagnetics as em
    original=em.complex_sqrt
    em.complex_sqrt=stable_complex_sqrt
    em.itu_coefficients_single_layer_slab.__globals__['complex_sqrt']=stable_complex_sqrt
    return original

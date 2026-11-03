"""Shared physical segment-length policy; no obstacle or endpoint tolerance.

RADIO_SEGMENT_PROFILE=shared_1mm accepts finite unshifted segments with squared
length >= (0.001 m)^2, computed in float64. Native mode preserves each engine's
legacy limits. Preliminary shifted-ray gates defer length decisions to the
unshifted geometry validator; visibility checks remain mandatory.
"""
import os
import numpy as np

SHARED_PROFILE='shared_1mm'
MINIMUM_M=0.001

def segment_profile():
    value=os.environ.get('RADIO_SEGMENT_PROFILE','native')
    if value not in ('native',SHARED_PROFILE):raise ValueError('Unknown RADIO_SEGMENT_PROFILE: '+value)
    return value

def preliminary_minimum(native_default):
    return 0. if segment_profile()==SHARED_PROFILE else native_default

def segments_at_least(points,minimum_m=MINIMUM_M):
    if not np.isfinite(minimum_m) or minimum_m<=0:raise ValueError('Minimum segment length must be positive and finite')
    points=np.asarray(points,np.float64)
    if points.ndim!=2 or points.shape[1]!=3 or len(points)<2 or not np.isfinite(points).all():return False
    delta=np.diff(points,axis=0)
    squared=np.sum(delta*delta,axis=-1,dtype=np.float64)
    return bool(np.all(squared>=float(minimum_m)**2))

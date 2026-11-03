"""Targeted controls for anomalies found by the broad diffraction sweep."""
import copy
import json
from pathlib import Path
from diffraction_cases import benchmark_cases, f32, quad


def controls():
    source={c['name']:c for c in benchmark_cases()}; cases=[]
    def clone(original,name=None):
        c=copy.deepcopy(source[original]); c['name']=name or original; cases.append(c); return c
    for name in ('wedge_v','wedge_h','metal_1e10','metal_h','wedge_reciprocal','skew_heights',
                 'reflection_diffraction','scale_100_0','translated_10km','shadow_boundary_v','shadow_boundary_h','repeat_warm'):
        clone(name)
    for name in ('wedge_h','metal_1e10','metal_h'):
        c=clone(name,name+'_reciprocal'); c['tx'],c['receivers']=c['receivers'][0],[c['tx']]
    for name in ('wedge_v','wedge_h','metal_1e10','metal_h'):
        c=clone(name,name+'_rotate90')
        rot=lambda p:[f32(-p[1]),f32(p[0]),p[2]]
        c['tx']=rot(c['tx']); c['receivers']=[rot(p) for p in c['receivers']]
        for m in c['meshes']: m['vertices']=[rot(p) for p in m['vertices']]
        c['tx_orientation']=c['rx_orientation']=[1.5707963267948966,0.,0.]
    for name in ('wedge_v','metal_1e10'):
        c=clone(name,name+'_face_order'); c['meshes'][0]['triangles']=c['meshes'][0]['triangles'][2:]+c['meshes'][0]['triangles'][:2]
        c=clone(name,name+'_retriangulate'); c['meshes'][0]['triangles']=[[0,1,3],[1,2,3],[0,3,5],[3,4,5]]
    c=clone('skew_heights','skew_single_rx'); c['receivers']=c['receivers'][:1]
    for name in ('wedge_angle_135','reflection_diffraction','wedge_reciprocal'):
        c=clone(name,name+'_high_samples'); c['solver']['samples_per_src']=1048576
    for shift in (10.,100.,1000.):
        c=clone('wedge_v','translated_'+str(int(shift))+'m'); offset=[shift,-shift,shift]
        move=lambda p:[f32(x+s) for x,s in zip(p,offset)]
        c['tx']=move(c['tx']);c['receivers']=[move(p) for p in c['receivers']]
        for m in c['meshes']:m['vertices']=[move(p) for p in m['vertices']]
        c['canonical_edges'][0]['origin']=offset
    c=clone('double_wedge','double_wedge_blocked')
    c['meshes'].append(quad('central_blocker',[(2,-2,-20),(2,0,-20),(2,0,20),(2,-2,20)]))
    return cases


if __name__=='__main__':
    import sys
    Path(sys.argv[1]).write_text(json.dumps(dict(schema='diffraction_cases_v1',cases=controls()),indent=2))

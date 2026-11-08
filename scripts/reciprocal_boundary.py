"""Single-edge exact-coincidence convention: one shadow-side joint contribution."""
import numpy as np

def duplicate_mask(paths,engine):
    valid=np.asarray(paths.valid).copy();flags=np.asarray(paths.interactions);vertices=np.asarray(paths.vertices)
    sources=np.asarray(paths.sources);targets=np.asarray(paths.targets)
    if engine=='sionna':sources=sources.T;targets=targets.T
    synthetic=flags.ndim==4
    removed=np.zeros_like(valid)
    for group in np.ndindex(valid.shape[:-1]):
        if len(group)==2:rx,tx=group;ra=ta=0
        else:rx,ra,tx,ta=group
        ix=(rx,tx) if synthetic else group
        source=sources[tx if synthetic else tx*valid.shape[3]+ta]
        target=targets[rx if synthetic else rx*valid.shape[1]+ra]
        diffs=[];go=[]
        for p in np.flatnonzero(valid[group]):
            f=flags[(slice(None),*ix,p)];active=np.flatnonzero(f);k=f[active].tolist()
            points=vertices[(active,*ix,p)]
            if k.count(8)==1 and all(t in (1,8) for t in k):diffs.append((k,points))
            elif all(t==1 for t in k):go.append((p,points))
        for kinds,dpoints in diffs:
            d=kinds.index(8);q=dpoints[d]
            before=source if d==0 else dpoints[d-1]
            after=target if d==len(dpoints)-1 else dpoints[d+1]
            incoming=q-before;outgoing=after-q
            li,lo=np.linalg.norm(incoming),np.linalg.norm(outgoing)
            if min(li,lo)==0:continue
            for p,points in go:
                # A duplicate must share the same physical route to numerical
                # angular resolution. This never makes an obstructed route valid.
                if len(points)==len(dpoints)-1:
                    expected=np.delete(dpoints,d,axis=0)
                    aligned=not len(expected) or np.max(np.linalg.norm(points-expected,axis=1))*(1/li+1/lo)<4e-7
                    same=aligned and np.linalg.norm(incoming/li-outgoing/lo)<4e-7
                elif len(points)==len(dpoints):
                    same=np.max(np.linalg.norm(points-dpoints,axis=1))*(1/li+1/lo)<4e-7
                else:same=False
                if same:removed[(*group,p)]=True
    return removed

def install_boundary_merge(engine):
    if engine=='sionna':
        from sionna.rt import PathSolver
    else:
        import differt_backend
        PathSolver=differt_backend.PathSolver
    original=PathSolver.__call__
    def solve(self,*args,**kwargs):
        paths=original(self,*args,**kwargs)
        if not kwargs.get('diffraction',False):return paths
        mask=duplicate_mask(paths,engine)
        if np.any(mask):
            if engine=='sionna':
                import mitsuba as mi
                paths._valid=mi.TensorXb(np.asarray(paths.valid)&~mask)
                coefficient_mask=mask[:,None,:,None,:] if mask.ndim==3 and np.asarray(paths.a[0]).ndim==5 else mask
                paths._a_real=mi.TensorXf(np.where(coefficient_mask,0,np.asarray(paths.a[0])))
                paths._a_imag=mi.TensorXf(np.where(coefficient_mask,0,np.asarray(paths.a[1])))
            else:
                paths.valid&=~mask
                paths.a=tuple(np.where(mask,0,a) for a in paths.a)
                paths._baseband_coeff=np.where(mask,0,paths._baseband_coeff)
        return paths
    PathSolver.__call__=solve
    return dict(name='shadow-side joint-field limit',angular_kernel_band_rad=8e-7,coincident_route_tolerance_rad=4e-7,scope='Single-edge coincidence. Coincident GO companions merge into the finite diffraction contribution; no invalid path is accepted.')

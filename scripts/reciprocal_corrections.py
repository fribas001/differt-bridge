"""Version-checked, process-local reciprocal dyads and accepted-path validation."""
import hashlib,inspect,textwrap

_INSTALLED={}

def _guard(function,expected):
    actual=hashlib.sha256(textwrap.dedent(inspect.getsource(function)).encode()).hexdigest()
    if actual!=expected:raise RuntimeError('Unsupported runtime source for reciprocal profile: '+function.__qualname__+' '+actual)

def install_differt():
    import differt.em._solvers as solvers
    from reciprocal_jax import reciprocal_jones
    original=solvers._diffraction_matrix_core;source=textwrap.dedent(inspect.getsource(original))
    marker='    D_s, D_h = diffraction_coefficients('
    assert source.count(marker)==1
    start=source.index(marker)
    code=source[:start]+'''    return reciprocal_jones(k_in,k_out,e_hat,n0,nn,wedge_n,wavenumber,L,n_r_o,n_r_n,d_o,d_n)
'''
    namespace=dict(vars(solvers),reciprocal_jones=reciprocal_jones)
    exec(compile(code,'<reciprocal-full-jones-differt>','exec'),namespace)
    solvers._diffraction_matrix_core=namespace['_diffraction_matrix_core']
    return dict(source_sha256=hashlib.sha256(source.encode()).hexdigest(),patched_sha256=hashlib.sha256(code.encode()).hexdigest(),scope='Full Cartesian reciprocal dyad with both polarization components; native search and visibility retained')

def install_sionna_opaque_slab():
    """Avoid 0*NaN for opaque slabs with enormous optical phase.

    Below exp(-80), propagation factors are negligible (<1.81e-35).
    Mask the phase before exp, then use zero. No conductivity clamp.
    """
    import sionna.rt.utils.electromagnetics as em
    import sionna.rt.utils as utils
    import sionna.rt.radio_materials.radio_material as rm
    original=em.itu_coefficients_single_layer_slab
    _guard(original,'d5b2913cc181239fd4ac00b40c921d62752a74db50431a05cd14854cbf395cac')
    source=textwrap.dedent(inspect.getsource(original))
    old='    exp_j_q = dr.exp(mi.Complex2f(0., -1.)*q)\n    exp_j_2q = dr.exp(mi.Complex2f(0., -2.)*q)'
    new='''    opaque = dr.imag(q) < -80.
    safe_q = dr.select(opaque, mi.Complex2f(0.), q)
    exp_j_q = dr.select(opaque, mi.Complex2f(0.), dr.exp(mi.Complex2f(0., -1.)*safe_q))
    exp_j_2q = dr.select(opaque, mi.Complex2f(0.), dr.exp(mi.Complex2f(0., -2.)*safe_q))'''
    assert source.count(old)==1
    code=source.replace(old,new);namespace=vars(em).copy()
    exec(compile(code,'<stable-opaque-slab-phase>','exec'),namespace)
    patched=namespace['itu_coefficients_single_layer_slab']
    em.itu_coefficients_single_layer_slab=utils.itu_coefficients_single_layer_slab=rm.itu_coefficients_single_layer_slab=patched
    return dict(source_sha256=hashlib.sha256(source.encode()).hexdigest(),patched_sha256=hashlib.sha256(code.encode()).hexdigest(),attenuation_threshold=-80.,scope='Opaque slab exponential only; source-guarded numerical fix, no conductivity clamp')


def stable_material_sqrt(value):
    """Scaled passive complex sqrt; no subtraction of nearly equal numbers."""
    import drjit as dr,mitsuba as mi
    x=dr.real(value);y=dr.imag(value);scale=dr.maximum(dr.abs(x),dr.abs(y))
    safe=dr.select(scale>0.,scale,1.)
    norm=scale*dr.sqrt(dr.square(x/safe)+dr.square(y/safe))
    large=dr.safe_sqrt(.5*(norm+dr.abs(x)));den=dr.select(large>0.,2*large,1.)
    re=dr.select(x>=0.,large,dr.abs(y)/den)
    im=dr.select(x>=0.,y/den,dr.select(y>0.,large,-large))
    return mi.Complex2f(re,im)


def install_sionna_material_sqrt():
    import sionna.rt.utils.electromagnetics as em
    _guard(em.complex_sqrt,'57c9e9292d22422194a073873e1a400677bd8647d6dcf921a2c3d029023f6148')
    _guard(em.fresnel_reflection_coefficients_simplified,'2ff15c9ba82cb9b0b1d4bc2a46719cdd5f7fdea02ae60e33c3b81aa455ab0fb7')
    em.complex_sqrt=stable_material_sqrt
    # The opaque-slab wrapper has its own copied global namespace.
    em.itu_coefficients_single_layer_slab.__globals__['complex_sqrt']=stable_material_sqrt
    return dict(scope='Fresnel and slab material square root only; preserve small passive loss and automatic derivatives',source_sha256=hashlib.sha256(inspect.getsource(stable_material_sqrt).encode()).hexdigest())


def install_sionna_fields():
    import drjit as dr,mitsuba as mi
    from sionna.rt.utils.jones import jones_matrix_rotator_flip_forward
    from sionna.rt.radio_materials.radio_material import RadioMaterial
    from diffraction_physics_worker import install_assembly,install_depth
    slab=install_sionna_opaque_slab()
    material_sqrt=install_sionna_material_sqrt()
    detail=install_assembly();detail['distance']=install_depth();detail['opaque_slab']=slab;detail['material_sqrt']=material_sqrt
    kp=RadioMaterial._diffraction_matrix
    native_cot=kp.__globals__['cot_times_f_utd']
    def boundary_cot(psi,x,n,kl):
        value=native_cot(psi,x,n,kl)
        delta=(psi-dr.round(psi/dr.pi)*dr.pi)*2*n
        v=-n*dr.sqrt(dr.pi*kl)
        return dr.select(dr.abs(delta)<8e-7,mi.Complex2f(v,v),value)
    kp.__globals__['cot_times_f_utd']=boundary_cot
    def reciprocal(self,to_world,ki_local,ko_local,si,eta,wavenumber):
        f=kp(self,to_world,ki_local,ko_local,si,eta,wavenumber)
        # The KP transition distance is symmetric in s,s'; keep explicit semantics.
        rev_si=mi.SurfaceInteraction3f(si)
        rev_si.dp_du=mi.Vector3f(si.dp_du.y,si.dp_du.x,si.dp_du.z)
        r=kp(self,to_world,-ko_local,-ki_local,rev_si,eta,wavenumber)
        rr=mi.Matrix2f(r[0,0],r[0,1],r[1,0],r[1,1])
        ri=mi.Matrix2f(r[2,0],r[2,1],r[3,0],r[3,1])
        fi=jones_matrix_rotator_flip_forward(to_world@ki_local)
        fo=jones_matrix_rotator_flip_forward(to_world@ko_local)
        rr=fo@rr.T@fi;ri=fo@ri.T@fi
        mapped=mi.Matrix4f(rr[0,0],rr[0,1],-ri[0,0],-ri[0,1],
                          rr[1,0],rr[1,1],-ri[1,0],-ri[1,1],
                          ri[0,0],ri[0,1],rr[0,0],rr[0,1],
                          ri[1,0],ri[1,1],rr[1,0],rr[1,1])
        return .5*(f+mapped)
    RadioMaterial._diffraction_matrix=reciprocal
    detail['scope']='Reciprocal full Jones matrix before native field transport; no conjugation or completed-channel averaging'
    return detail

def install_sionna_geometry():
    import numpy as np,drjit as dr,mitsuba as mi
    from sionna.rt.path_solvers.image_method import ImageMethod
    from sionna.rt.path_solvers.paths_buffer import PathsBufferBase
    from sionna.rt.path_solvers import _bridge_geometry as geometry
    original=ImageMethod.__call__
    def checked(self,scene,paths,src_positions,tgt_positions,**kwargs):
        if not kwargs.get('diffraction',False):
            return original(self,scene=scene,paths=paths,src_positions=src_positions,tgt_positions=tgt_positions,**kwargs)
        # Native discovery includes unresolved candidates marked invalid. Keep
        # their expected triangles so an offset-induced rejection can be checked
        # independently instead of permanently losing a valid near-edge path.
        base=PathsBufferBase.from_paths_buffer(paths)
        pure=np.ones(paths.buffer_size,dtype=bool)
        kinds=[]
        for depth in range(1,paths.max_depth+1):
            kind=np.asarray(paths.get_interaction_type(depth,True));kinds.append(kind)
            pure&=(kind==0)|(kind==1)
        paths=original(self,scene=scene,paths=paths,src_positions=src_positions,tgt_positions=tgt_positions,**kwargs)
        valid=np.asarray(paths.valid).copy()
        for depth,kind in enumerate(kinds,1):
            active=mi.Bool(pure&(kind!=0))
            paths.set_shape(depth,base.get_shape(depth,active),active)
            paths.set_primitive(depth,base.get_primitive(depth,active),active)
        # Discovery is native; acceptance is recomputed using exact triangle
        # membership and every scene obstacle. Other interaction masks survive.
        paths.valid=mi.Bool(pure)
        paths=geometry.repair_paths(scene,paths,src_positions,tgt_positions)
        paths.valid=paths.valid|mi.Bool(valid&~pure)
        from reciprocal_geometry import repair_mixed
        supported=np.all(np.isin(np.array(kinds),[0,1,8]),axis=0)
        mixed=supported&~pure&valid
        if np.any(mixed):paths=repair_mixed(scene,paths,src_positions,tgt_positions,mixed)
        paths.schedule();dr.eval()
        return paths
    ImageMethod.__call__=checked
    return dict(scope='Diffraction-enabled solves only. Reconstruct native-discovered pure specular/LoS candidates, including offset-rejected candidates; refine native-accepted R/D chains. Enforce finite surfaces, interaction laws, native segment limits and complete-mesh visibility.',source_sha256=hashlib.sha256(inspect.getsource(original).encode()).hexdigest())

def install(engine,geometry=True):
    if engine in _INSTALLED:return _INSTALLED[engine]
    from importlib.metadata import version
    if engine=='differt':
        if version('differt')!='0.12.0':raise RuntimeError('Reciprocal profile requires validated DiffeRT 0.12.0')
        from differt.em._solvers import _diffraction_matrix_core
        _guard(_diffraction_matrix_core,'5c4338c1083ab944d8d41b160cc679ee4655596090565fb3de08fb139031a8a8')
        result=install_differt()
    elif engine=='sionna':
        if version('sionna-rt')!='2.1.0':raise RuntimeError('Reciprocal profile requires validated Sionna RT 2.1.0')
        from sionna.rt.radio_materials.radio_material import RadioMaterial
        from sionna.rt.path_solvers.field_calculator import FieldCalculator
        from sionna.rt.path_solvers.image_method import ImageMethod
        from sionna.rt.utils.electromagnetics import itu_coefficients_single_layer_slab
        from sionna.rt.utils.electromagnetics import complex_sqrt,fresnel_reflection_coefficients_simplified
        # Check everything before mutating a method. Unknown revisions fail closed.
        _guard(RadioMaterial._diffraction_matrix,'428e490c56d97a1a83d388438f4ac13ebd98cee832a8a89558b82c2bbec9bdb0')
        _guard(FieldCalculator._diffraction_compute_s_s_prime,'42e77c27806a3d05569eed185112b7a2ba88f679ab9c1fd2d009edece7cb963b')
        _guard(itu_coefficients_single_layer_slab,'d5b2913cc181239fd4ac00b40c921d62752a74db50431a05cd14854cbf395cac')
        _guard(complex_sqrt,'57c9e9292d22422194a073873e1a400677bd8647d6dcf921a2c3d029023f6148')
        _guard(fresnel_reflection_coefficients_simplified,'2ff15c9ba82cb9b0b1d4bc2a46719cdd5f7fdea02ae60e33c3b81aa455ab0fb7')
        # ImageMethod hash is dedented here; see the installation receipt.
        original=inspect.getsource(ImageMethod.__call__)
        if hashlib.sha256(original.encode()).hexdigest()!='286a98c088be6dbbd28949ade7c0ad76def517a5a338f77427ee6ac3926ed0b9':
            raise RuntimeError('Unsupported Sionna image method')
        result=install_sionna_fields()
        if geometry:result['geometry']=install_sionna_geometry()
    else:raise ValueError(engine)
    result.update(profile='reciprocal',engine=engine)
    from reciprocal_boundary import install_boundary_merge
    result['boundary_convention']=install_boundary_merge(engine)
    _INSTALLED[engine]=result
    return result

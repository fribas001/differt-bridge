"""Process-local field interventions; installed runtimes and visibility are untouched."""
import hashlib,inspect,json,os,sys,textwrap
from pathlib import Path

def install_differt(profile):
    import differt.em._utd as utd
    import differt.em._solvers as solvers
    source=textwrap.dedent(inspect.getsource(utd.diffraction_coefficients))
    code=source
    replacements=[
        ('D_1 + D_2 + r_s_n * D_3 + r_s_o * D_4','D_1 + D_2 - r_p_n * D_3 - r_p_o * D_4'),
        ('D_1 + D_2 + r_p_n * D_3 + r_p_o * D_4','D_1 + D_2 - r_s_n * D_3 - r_s_o * D_4'),
    ]
    if profile=='incident':
        replacements += [('cos_theta_o = jnp.sin(phi_i_arr)','cos_theta_o = jnp.abs(jnp.sin(phi_i_arr))*sin_beta_0_safe'),
                         ('cos_theta_n = jnp.sin(n_arr * jnp.pi - phi_d_arr)','cos_theta_n = jnp.abs(jnp.sin(n_arr * jnp.pi - phi_i_arr))*sin_beta_0_safe')]
    elif profile=='symmetric_cosine':
        # Constraint-only hypothesis, not a published or independently validated wedge solution.
        replacements += [('cos_theta_o = jnp.sin(phi_i_arr)','cos_theta_o = .5*(jnp.abs(jnp.sin(phi_i_arr))+jnp.abs(jnp.sin(phi_d_arr)))*sin_beta_0_safe'),
                         ('cos_theta_n = jnp.sin(n_arr * jnp.pi - phi_d_arr)','cos_theta_n = .5*(jnp.abs(jnp.sin(n_arr * jnp.pi - phi_i_arr))+jnp.abs(jnp.sin(n_arr * jnp.pi - phi_d_arr)))*sin_beta_0_safe')]
    for old,new in replacements:
        if code.count(old)!=1:raise RuntimeError('Unsupported DiffeRT source: '+old)
        code=code.replace(old,new,1)
    namespace=vars(utd).copy();exec(compile(code,'<dielectric-'+profile+'>','exec'),namespace)
    utd.diffraction_coefficients=solvers.diffraction_coefficients=namespace['diffraction_coefficients']
    return dict(original_source_sha256=hashlib.sha256(source.encode()).hexdigest(),diagnostic_source_sha256=hashlib.sha256(code.encode()).hexdigest(),replacements=replacements)

def main():
    profile=sys.argv.pop(1);engine=sys.argv[1];out=Path(sys.argv[3]);out.mkdir(parents=True,exist_ok=True)
    temporary=(out/'temp').resolve();temporary.mkdir(exist_ok=True)
    os.environ.update(TEMP=str(temporary),TMP=str(temporary),RADIO_SEGMENT_PROFILE='native',SIONNA_GEOMETRY_PROFILE='native',DIFFERT_ARITHMETIC_PROFILE='native')
    import tempfile;tempfile.tempdir=str(temporary)
    detail={}
    if profile=='reciprocal':
        if engine=='sionna':
            import mitsuba as mi;mi.set_variant('llvm_ad_mono_polarized')
        else:
            sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/differt_bridge'))
            import differt_backend
        from reciprocal_corrections import install
        detail=install(engine)
    elif engine=='sionna' and profile=='kp_depth':
        import mitsuba as mi;mi.set_variant('llvm_ad_mono_polarized')
        from diffraction_physics_worker import install_assembly,install_depth
        detail=install_assembly();detail['distance']=install_depth()
    elif engine=='differt' and profile in ('polarization','incident','symmetric_cosine'):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/differt_bridge'))
        import differt_backend
        detail=install_differt(profile)
    elif profile!='native':raise ValueError((engine,profile))
    detail.update(profile=profile,engine=engine,installation='Process-local diagnostic; installed files unchanged')
    (out/'intervention.json').write_text(json.dumps(detail,indent=2),encoding='utf-8')
    os.environ['RADIO_DIELECTRIC_PROFILE']='reciprocal' if profile=='reciprocal' else 'native'
    from diffraction_worker import main as run
    run()

if __name__=='__main__':main()

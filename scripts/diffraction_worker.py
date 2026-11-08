"""Run one manifest through an installed engine without changing it."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sys
import time
import traceback
import numpy as np
from diffraction_cases import write_scene


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def scalar(x):
    return float(np.asarray(x).reshape(-1)[0])


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('engine',choices=['sionna','differt']); ap.add_argument('manifest',type=Path)
    ap.add_argument('output',type=Path); ap.add_argument('--only',default=''); ap.add_argument('--precision',default='native',choices=['native','float32','float64'])
    ap.add_argument('--fermat-steps',type=int,default=0)
    ap.add_argument('--fermat-float64',action='store_true')
    ap.add_argument('--fermat-native64-output',action='store_true',help='Deliberate incompatible-Warp dtype control')
    ap.add_argument('--nondeterministic',action='store_true')
    ap.add_argument('--diffraction-geometry',choices=['native','validated'],default='native')
    args=ap.parse_args(); project=Path(__file__).resolve().parents[1]
    os.environ['DIFFERT_DIFFRACTION_GEOMETRY']=args.diffraction_geometry
    if args.precision=='native':os.environ.pop('DIFFERT_FIELD_PRECISION',None)
    for k,v in dict(RADIO_SEGMENT_PROFILE='native',SIONNA_GEOMETRY_PROFILE='native',DIFFERT_ARITHMETIC_PROFILE='native',
                    **({'DIFFERT_FIELD_PRECISION':args.precision} if args.precision!='native' else {})).items(): os.environ[k]=v
    args.output.mkdir(parents=True,exist_ok=True)
    # Native compilers must use an explicitly writable project directory.
    temporary=(args.output/'temp').resolve(); temporary.mkdir(exist_ok=True)
    os.environ['TEMP']=os.environ['TMP']=str(temporary)
    import tempfile
    tempfile.tempdir=str(temporary)
    os.environ['WP_CACHE_DIR']=str(args.output/'cache')
    sys.path.insert(0,str(project/'src/differt_bridge'))
    if args.engine=='sionna':
        if args.precision not in ('native','float32'):raise RuntimeError('This Sionna variant uses float32 fields')
        field_precision_profile='float32'
        import mitsuba as mi
        mi.set_variant('llvm_ad_mono_polarized')
        import sionna.rt as rt
        versions={k:importlib.metadata.version(k) for k in ['sionna-rt','mitsuba','drjit','numpy']}
    else:
        import differt_backend as rt
        try:
            from differt.em._bridge_precision import field_precision
            field_precision_profile=field_precision()
        except ModuleNotFoundError:
            field_precision_profile='upstream_native'
        if args.precision!='native' and field_precision_profile!=args.precision:
            raise RuntimeError('Requested field precision is not configured in this runtime; use --precision native')
        versions={k:importlib.metadata.version(k) for k in ['differt','jax','jaxlib','warp-lang','numpy']}
        if args.fermat_steps or args.fermat_float64:
            # Diagnostic intervention in this process only. Installed files are untouched.
            import differt.geometry.solvers._dispatch as dispatch
            import jax.numpy as jnp
            original_fermat=dispatch.fermat_path_on_linear_objects
            def controlled_fermat(*values,**kwargs):
                geometry_dtype=values[0].dtype
                if args.fermat_steps: kwargs['steps']=args.fermat_steps
                if args.fermat_float64: values=tuple(jnp.asarray(v,dtype=jnp.float64) for v in values)
                solved=original_fermat(*values,**kwargs)
                # Warp visibility requires float32 geometry; preserve that contract.
                return solved.astype(geometry_dtype) if args.fermat_float64 and not args.fermat_native64_output else solved
            dispatch.fermat_path_on_linear_objects=controlled_fermat
    result=dict(engine=args.engine,precision=args.precision if args.engine=='differt' else 'float32',versions=versions,
                platform=platform.platform(),processor=platform.processor(),python=sys.version,manifest_sha256=digest(args.manifest),
                profiles={k:os.environ.get(k,'native') for k in ('RADIO_SEGMENT_PROFILE','SIONNA_GEOMETRY_PROFILE','DIFFERT_ARITHMETIC_PROFILE','DIFFERT_FIELD_PRECISION','RADIO_DIELECTRIC_PROFILE')},
                diagnostic_interventions=dict(fermat_steps=args.fermat_steps or 'default',fermat_float64=args.fermat_float64,
                    diffraction_geometry=args.diffraction_geometry,
                    concrete_mesh_dispatch=False,
                    fermat_result_cast_back_to_geometry_dtype=args.fermat_float64 and not args.fermat_native64_output,
                    deterministic=not args.nondeterministic),
                started_utc=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),cases=[],status='running')
    selected=set(args.only.split(',')) if args.only else None
    target=args.output/(args.engine+'_'+args.precision+'.json')
    solver=rt.PathSolver(deterministic=not args.nondeterministic)
    for case in json.loads(args.manifest.read_text())['cases']:
        if selected is not None and case['name'] not in selected: continue
        print('DIFFRACTION_START',args.engine,args.precision,case['name'],flush=True)
        row=dict(name=case['name'],category=case['category'],status='running')
        started=time.perf_counter()
        try:
            folder=args.output/'inputs'/case['name']; xml=write_scene(case,folder)
            scene=rt.load_scene(str(xml.resolve()),merge_shapes=False) if args.engine=='sionna' else rt.load_scene(xml)
            scene.frequency=case['frequency_hz']
            scene.tx_array=rt.PlanarArray(num_rows=1,num_cols=case.get('array_cols',1),pattern=case['pattern'],polarization=case['tx_pol'])
            scene.rx_array=rt.PlanarArray(num_rows=1,num_cols=1,pattern=case['pattern'],polarization=case['rx_pol'])
            scene.add(rt.Transmitter(name='TX',position=case['tx'],orientation=case.get('tx_orientation',[0,0,0])))
            for i,pos in enumerate(case['receivers']): scene.add(rt.Receiver(name='RX'+str(i),position=pos,orientation=case.get('rx_orientation',[0,0,0])))
            if args.engine=='differt':
                scene.configure_materials([dict(source_name='wall',model='CUSTOM',**case['material'])])
                scene.bridge_simulation.update(differt_solver=case['differt_solver'],differt_max_candidates=2000000,differt_chunk_size=256,mobility_doppler=False)
                row['effective_materials']=scene.material_summary
            else:
                row['effective_materials']={name:{key:scalar(getattr(m,key)) for key in case['material']} for name,m in scene.radio_materials.items()}
            row['input_file_sha256']={p.name:digest(p) for p in sorted(folder.iterdir())}
            durations=[]; fingerprints=[]
            for repeat in range(case.get('repeats',1)):
                start=time.perf_counter(); paths=solver(scene,**case['solver'])
                aa=paths.a; coeff=np.asarray(aa[0])+1j*np.asarray(aa[1]); valid=np.asarray(paths.valid,dtype=bool)
                durations.append(time.perf_counter()-start)
                fingerprints.append(hashlib.sha256(coeff.tobytes()+valid.tobytes()+np.asarray(paths.vertices).tobytes()).hexdigest())
            row['solve_seconds']=durations
            row['repeat_fingerprints']=fingerprints
            vertices=np.asarray(paths.vertices); interactions=np.asarray(paths.interactions); delays=np.asarray(paths.tau)
            if args.engine=='sionna': cir,_=paths.cir(normalize_delays=False,out_type='numpy')
            else: cir,_=paths.cir(normalize_delays=False)
            cir=np.asarray(cir)[...,0]
            row['coefficient_dtype']=str(coeff.dtype)
            # Carrier conversion and bridge storage can promote complex64 fields
            # to complex128. Export dtype is not the arithmetic precision policy.
            row['field_precision_profile']=field_precision_profile
            row['array_shapes']={k:list(v.shape) for k,v in dict(valid=valid,coefficient=coeff,vertices=vertices,interactions=interactions,delay=delays,cir=cir).items()}
            records=[]
            for index in np.argwhere(valid):
                idx=tuple(map(int,index)); flags=interactions[(slice(None),*idx)]
                active=np.flatnonzero(flags)
                points=[case['tx'],*vertices[(active,*idx)].tolist(),case['receivers'][idx[0]]]
                a=complex(coeff[idx]); b=complex(cir[idx]); delay=float(delays[idx])
                records.append(dict(index=list(idx),rx=idx[0],points=points,interactions=flags[active].astype(int).tolist(),
                    a=[a.real,a.imag],cir=[b.real,b.imag],delay_s=delay,geometric_length_m=float(np.linalg.norm(np.diff(points,axis=0),axis=-1).sum()),
                    finite=bool(np.isfinite([a.real,a.imag,b.real,b.imag,delay,*np.asarray(points).ravel()]).all())))
            row['paths']=records; row['status']='completed'; row['valid_paths']=len(records)
            row['diagnostics']=scene.last_diagnostics if args.engine=='differt' else dict(deterministic=not args.nondeterministic,**case['solver'])
        except Exception:
            row.update(status='error',error=traceback.format_exc())
        row['elapsed_seconds']=time.perf_counter()-started
        result['cases'].append(row)
        target.write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
        print('DIFFRACTION_RESULT',args.engine,case['name'],row['status'],row.get('valid_paths'),round(row['elapsed_seconds'],2),flush=True)
    result['status']='completed' if all(c['status']=='completed' for c in result['cases']) else 'completed_with_errors'
    result['finished_utc']=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()
    target.write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    if result['status']!='completed': raise SystemExit(2)


if __name__=='__main__': main()

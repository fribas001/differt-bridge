"""Probe a newly created runtime without using the old workstation environment."""
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import sys
import numpy as np
import scipy

engine=sys.argv[1];output=Path(sys.argv[2])
result=dict(engine=engine,python=sys.version,prefix=sys.prefix,base_prefix=sys.base_prefix,
            numpy=np.__version__,scipy=scipy.__version__,numpy_file=np.__file__,scipy_file=scipy.__file__,
            user_site_disabled=not __import__('site').ENABLE_USER_SITE)
if engine=='differt':
    import differt,jax,jax.numpy as jnp
    from scipy.sparse.linalg._dsolve import _superlu
    result.update(differt=differt.__version__,jax=jax.__version__,devices=[str(v) for v in jax.devices()],
                  compiled_value=float(jax.jit(lambda x:jnp.sin(x))(jnp.array(.3))),
                  superlu_sha256=hashlib.sha256(Path(_superlu.__file__).read_bytes()).hexdigest())
else:
    import mitsuba as mi
    mi.set_variant('llvm_ad_mono_polarized')
    import drjit as dr,sionna.rt
    value=dr.sum(dr.arange(mi.Float,32));dr.eval(value)
    assert float(value[0])==496.
    result.update(sionna=metadata.version('sionna-rt'),mitsuba=mi.__version__,drjit=dr.__version__,compiled_value=float(value[0]),
                  llvm_adapter=dr._bridge_llvm_batch_status)
assert result['user_site_disabled']
assert Path(np.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
assert Path(scipy.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
result['status']='passed';output.parent.mkdir(parents=True,exist_ok=True)
output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,indent=2))

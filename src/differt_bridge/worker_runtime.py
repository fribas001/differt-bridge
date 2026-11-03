"""Shared external-worker services; no Blender or eager DiffeRT imports.

Caches are bounded to the current scene and worker invocation. They never cache
propagation results, device poses, or evaluated procedural geometry.
"""
import copy
import inspect
import importlib.metadata
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

if __package__:
    from . import plant_materials
else:
    import plant_materials

def package_version():
    for distribution in ("differt",):
        try:
            return importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            pass
    return "unknown"

def now_utc():
    return datetime.now(timezone.utc).isoformat()

def _atomic_replace_with_retry(temporary, destination, attempts=24):
    temporary = Path(temporary)
    destination = Path(destination)
    last_error = None
    for attempt in range(max(1, int(attempts))):
        try:
            os.replace(temporary, destination)
            return
        except (PermissionError, OSError) as exc:
            last_error = exc
            if attempt + 1 >= attempts:
                break
            time.sleep(min(1.0, 0.04 * (attempt + 1)))
    raise last_error or RuntimeError(f"Could not replace {destination}")

def write_json(path, payload, *, best_effort=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(
        path.name + f".{os.getpid()}.{time.time_ns()}.tmp"
    )
    try:
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.flush()
            try:
                os.fsync(handle.fileno())
            except OSError:
                pass
        _atomic_replace_with_retry(temporary, path)
        return True
    except Exception as exc:
        try:
            temporary.unlink(missing_ok=True)
        except Exception:
            pass
        if best_effort:
            print(f"WARNING: could not update status file {path}: {exc}", flush=True)
            return False
        raise

def write_status_json(path, payload):
    # Status updates must never terminate an otherwise valid long simulation.
    return write_json(path, payload, best_effort=True)

def frame_materials(runtime, frame):
    materials = list(frame.get("materials") or runtime.get("materials") or [])
    return materials







def apply_radio_materials(scene, frame, runtime):
    return scene.configure_materials(frame_materials(runtime, frame))


def ensure_tx_array(scene, runtime, factory, profile):
    """Reuse a role array only while scene, profile and array identity agree."""
    signature = json.dumps(profile, sort_keys=True)
    cached = runtime.get("_bridge_tx_array_cache")
    if (cached is None or cached[0] is not scene or cached[1] != signature
            or scene.tx_array is not cached[2]):
        scene.tx_array = factory(runtime, runtime["PlanarArray"])
        runtime["_bridge_tx_array_cache"] = (scene, signature, scene.tx_array)


def make_path_solver(factory, deterministic=True):
    """2.1 reproducibility support, without masking solver construction errors."""
    parameters = inspect.signature(factory).parameters
    if "deterministic" in parameters:
        return factory(deterministic=bool(deterministic))
    if deterministic:
        print("WARNING: this PathSolver lacks deterministic execution support", flush=True)
    return factory()



def exit_worker(code):
    """Finish an isolated worker after its files have been closed.

    Windows' CRT exit invokes DLL detach callbacks that crash in the tested
    Mitsuba/Dr.Jit build, even after a plain import. Terminate only this worker
    after flushing Python streams; preserve the actual success/failure code.
    Never call this from Blender or another embedding application.
    """
    import sys
    code = int(code)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.flush()
        except (OSError, ValueError):
            code = code or 1
    if os.name == "nt":
        import ctypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        kernel.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        kernel.TerminateProcess.restype = ctypes.c_int
        if not kernel.TerminateProcess(kernel.GetCurrentProcess(), code):
            raise ctypes.WinError(ctypes.get_last_error())
    os._exit(code)

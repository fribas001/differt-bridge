"""Nonblocking benchmark orchestration; delegates owned workers to comparison."""
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import shutil
import time
import uuid
import webbrowser

import bpy
from bpy.app.handlers import persistent
from . import benchmark

JOB = {}
_BRIDGE = None


def active():
    return bool(JOB)


def _checkpoint(status, message=''):
    document=JOB['document']; document.update(status=status,message=message)
    path=benchmark.write_report(JOB['folder'],document)
    settings=JOB['scene'].differt_bridge
    settings.benchmark_report=str(path)
    settings.benchmark_status=f"{status}: {len(document['runs'])}/{len(document['plan'])} pairs. {message}"


def stop(status='Cancelled', message='Stopped by user'):
    if not JOB:
        return
    scene=JOB['scene']
    try:
        _BRIDGE._comparison.cancel('Benchmark '+status.lower())
        _checkpoint(status,message)
    finally:
        for engine, values in JOB['restore'].items():
            settings=getattr(scene,engine+'_bridge')
            # Keep callbacks disabled until all swept controls have been restored.
            settings.dynamic_mode=False
            for key,value in values.items():
                if key!='dynamic_mode':setattr(settings,key,value)
            settings.dynamic_mode=values['dynamic_mode']
        JOB.clear()


@persistent
def before_load(_):
    stop('Cancelled','Another Blender file was opened')


def register():
    if before_load not in bpy.app.handlers.load_pre:
        bpy.app.handlers.load_pre.append(before_load)


def unregister():
    stop('Cancelled','DiffeRT-Bridge was disabled')
    if before_load in bpy.app.handlers.load_pre:bpy.app.handlers.load_pre.remove(before_load)
    if bpy.app.timers.is_registered(tick):bpy.app.timers.unregister(tick)


def _start_pair():
    spec=JOB['document']['plan'][len(JOB['document']['runs'])]
    settings=JOB['scene'].sionna_bridge
    settings.max_depth=spec['depth']; settings.seed=spec['seed']
    JOB['previous_report']=JOB['scene'].differt_bridge.comparison_report
    JOB['pair_started']=time.monotonic()
    _BRIDGE._comparison.start(bpy.context,engine_order=spec['engine_order'],managed=True)
    _checkpoint('Running',f"Depth {spec['depth']}, repeat {spec['repeat']}, {spec['engine_order'][0]} first")


def start(context):
    if active() or _BRIDGE._comparison.active():
        raise ValueError('A comparison or benchmark is already running')
    engines=_BRIDGE._comparison.bridges()
    if not all(b._processes_idle() for b in engines.values()):
        raise ValueError('Wait for current simulations before starting a benchmark')
    scene=context.scene; settings=scene.differt_bridge
    if scene.sionna_bridge.timeline_mode!='CURRENT':
        raise ValueError('Choose Current Frame in Sionna before starting a depth benchmark')
    schedule=benchmark.plan(settings.benchmark_depth_first,settings.benchmark_depth_last,
        settings.benchmark_repeats,scene.sionna_bridge.seed,settings.benchmark_vary_seed)
    for engine, bridge in engines.items():
        if bridge._resolve_python_executable(getattr(scene,engine+'_bridge'))[0] is None:
            raise ValueError('Configure the '+engine+' runtime first')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    folder=_BRIDGE._workspace(settings)/'benchmarks'/(stamp+'_'+uuid.uuid4().hex[:8])
    restore={e:{k:getattr(getattr(scene,e+'_bridge'),k) for k in
        ('max_depth','seed',*_BRIDGE._comparison.TEMPORARY)} for e in engines}
    environment=dict(blender=bpy.app.version_string,platform=platform.platform(),machine=platform.machine(),
        frame=scene.frame_current,scene_file=bpy.data.filepath,scene_name=scene.name,
        python_executables={e:str(b._resolve_python_executable(getattr(scene,e+'_bridge'))[0]) for e,b in engines.items()},
        bridge_versions={e:b._ADDON_VERSION for e,b in engines.items()},
        vary_seed=settings.benchmark_vary_seed,timeout_minutes_per_pair=settings.benchmark_timeout_minutes,
        timing='export + fresh worker startup + tracing + import; no warm-up exclusion',
        samples_per_src=scene.sionna_bridge.samples_per_src,max_num_paths_per_src=scene.sionna_bridge.max_num_paths_per_src,
        differt_solver=settings.differt_solver,differt_chunk_size=settings.differt_chunk_size,
        differt_max_candidates=settings.differt_max_candidates)
    JOB.update(scene=scene,frame=scene.frame_current,folder=folder,restore=restore,
        timeout=settings.benchmark_timeout_minutes*60.,baseline={},
        document=dict(schema='radio_depth_benchmark_v1',created_utc=datetime.now(timezone.utc).isoformat(),
                      plan=schedule,runs=[],environment=environment))
    try:
        for e in engines:
            s=getattr(scene,e+'_bridge');s.dynamic_mode=False
            for key in _BRIDGE._comparison.TEMPORARY[6:]:setattr(s,key,False)
        _start_pair()
        if not bpy.app.timers.is_registered(tick):bpy.app.timers.register(tick,first_interval=.5)
    except Exception as exc:
        stop('Failed',str(exc)); raise


def tick():
    if not JOB:return None
    try:
        scene=JOB['scene']
        if bpy.context.scene!=scene or scene.frame_current!=JOB['frame']:
            raise RuntimeError('Active scene or frame changed during the benchmark')
        if time.monotonic()-JOB['pair_started']>JOB['timeout']:
            raise RuntimeError('Paired run exceeded its time limit; completed runs are retained')
        if _BRIDGE._comparison.active():
            _BRIDGE._comparison.tick()
            return .5
        settings=scene.differt_bridge
        if not settings.comparison_status.startswith('Comparison ready:') or settings.comparison_report==JOB['previous_report']:
            raise RuntimeError(settings.comparison_status)
        spec=JOB['document']['plan'][len(JOB['document']['runs'])]
        target=JOB['folder']/f"run_{spec['index']:03d}_depth_{spec['depth']}_repeat_{spec['repeat']}"
        shutil.copytree(Path(settings.comparison_report).parent,target)
        result=benchmark.collect(target,spec,JOB['baseline'],JOB['frame'])
        result['report']=target.name+'/comparison.html'
        if not JOB['baseline']:JOB['baseline']=result['signatures']
        JOB['document']['runs'].append(result)
        settings.comparison_report=str(target/'comparison.html')
        _checkpoint('Running')
        if not result['eligible']:
            stop('Stopped for input review','; '.join(result['issues']))
            return None
        if len(JOB['document']['runs'])==len(JOB['document']['plan']):
            stop('Completed','Original depth, seed and run controls restored')
            return None
        _start_pair()
        return .5
    except Exception as exc:
        stop('Failed',str(exc))
        return None


def build_classes(bridge):
    global _BRIDGE
    _BRIDGE=bridge

    class DIFFERT_OT_RunBenchmark(bpy.types.Operator):
        bl_idname='differt_bridge.run_benchmark'
        bl_label='Run Depth Benchmark'
        bl_description='Repeat paired path runs on the current frame, alternating engine order; restore depth and seed afterward'
        @classmethod
        def poll(cls,context):return not active() and not bridge._comparison.active()
        def execute(self,context):
            try:start(context);return {'FINISHED'}
            except Exception as exc:self.report({'ERROR'},str(exc));return {'CANCELLED'}

    class DIFFERT_OT_StopBenchmark(bpy.types.Operator):
        bl_idname='differt_bridge.stop_benchmark'
        bl_label='Stop Benchmark'
        def execute(self,context):
            stop();return {'FINISHED'}

    class DIFFERT_OT_OpenBenchmark(bpy.types.Operator):
        bl_idname='differt_bridge.open_benchmark'
        bl_label='Open Benchmark Report'
        def execute(self,context):
            path=Path(context.scene.differt_bridge.benchmark_report)
            if not path.is_file():
                self.report({'ERROR'},'Run a benchmark first');return {'CANCELLED'}
            webbrowser.open(path.resolve().as_uri());return {'FINISHED'}

    return DIFFERT_OT_RunBenchmark,DIFFERT_OT_StopBenchmark,DIFFERT_OT_OpenBenchmark

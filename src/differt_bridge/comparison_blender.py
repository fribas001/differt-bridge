"""Sequential two-engine path runs and comparisons of immutable result snapshots."""
import copy
import json
from pathlib import Path
import sys
from types import ModuleType
import time
from datetime import datetime, timezone
import uuid
import webbrowser

import bpy
from bpy.app.handlers import persistent
from . import comparison
from .point_coverage import grid_positions
from . import path_diagnostics_blender as path_view

JOB = {}
_BRIDGE = None
TEMPORARY = ('simulate_paths', 'simulate_radio_map', 'simulate_radio_map_3d',
             'refresh_scene_before_run', 'parameter_analysis_enabled', 'dynamic_mode',
             'auto_compute_paths_on_tx_move', 'auto_compute_radio_map_on_device_move',
             'auto_compute_radio_map_3d_on_device_move')


def bridges():
    sionna = next((module for module in list(sys.modules.values())
                   if isinstance(module, ModuleType) and 'SIONNA_PG_Settings' in vars(module)), None)
    if sionna is None or not hasattr(bpy.types.Scene, 'sionna_bridge'):
        raise ValueError('Enable SionnaRT-Bridge before comparing engines')
    return {'sionna': sionna, 'differt': _BRIDGE}


def active():
    return bool(JOB)


def locked():
    return active() or bool(getattr(_BRIDGE, '_benchmark', None) and _BRIDGE._benchmark.active())


def _status(scene, value):
    scene.differt_bridge.comparison_status = value


def _restore():
    scene = JOB.get('scene')
    if scene is None:
        return
    for engine, values in JOB.get('restore', {}).items():
        settings = getattr(scene, engine + '_bridge', None)
        if settings is not None:
            for name, value in values.items():
                setattr(settings, name, value)


def cancel(reason='Comparison cancelled'):
    if not JOB:
        return
    scene = JOB['scene']
    engine = JOB.get('engine')
    try:
        if engine:
            JOB['bridges'][engine]._cancel_active_runs(reason)
        _restore()
        _status(scene, reason)
    finally:
        JOB.clear()


@persistent
def before_load(_dummy):
    cancel('Comparison stopped: another Blender file was opened')


def unregister():
    cancel('Comparison stopped: DiffeRT-Bridge disabled')
    if before_load in bpy.app.handlers.load_pre:
        bpy.app.handlers.load_pre.remove(before_load)
    if bpy.app.timers.is_registered(tick):
        bpy.app.timers.unregister(tick)


def register():
    if before_load not in bpy.app.handlers.load_pre:
        bpy.app.handlers.load_pre.append(before_load)


def _directory(scene):
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    return _BRIDGE._workspace(scene.differt_bridge) / 'comparisons' / (stamp+'_'+uuid.uuid4().hex[:8])


def _write(scene, studies):
    path, report = comparison.write_report(_directory(scene), studies['sionna'], studies['differt'],
        path_tolerance_m=scene.differt_bridge.comparison_path_tolerance_mm/1000.)
    scene.differt_bridge.comparison_report = str(path)
    flagged = sum(p['status'] != 'matched_inputs' for p in report['pairs'])
    _status(scene, f"Comparison ready: {len(report['pairs'])} links; {flagged} need input review")
    return path, report


def _snapshot(engine, bridge, scene, selected=False):
    if selected:
        study = copy.deepcopy(bridge._parameter_study.selected_study(bridge, scene))
        settings = getattr(scene, engine+'_bridge')
        obj = settings.parameter_study_object or bridge._analytics_target_object(scene, 'PATHS')
        if settings.parameter_study_source == 'IMPORTED':
            obj = None
    else:
        name = getattr(scene, engine+'_bridge').last_paths_object
        obj = bpy.data.objects.get(name)
        study = copy.deepcopy(bridge._parameter_study.dataset_from_object(obj))
    if obj is not None and obj.get('radio_comparison_evidence'):
        evidence = json.loads(obj['radio_comparison_evidence'])
        if evidence.get('run_id') == study['run_id']:
            study['geometry_evidence'] = evidence['geometry_evidence']
            if 'execution' in evidence:
                study['execution'] = evidence['execution']
    if obj is not None:
        study['path_traces'] = path_view.capture(obj, study)
    return study, obj


def _start(engine):
    scene = JOB['scene']
    JOB['engine'] = engine
    JOB['started'] = time.monotonic()
    operator = getattr(getattr(bpy.ops, engine+'_bridge'), 'run_selected')
    if operator() != {'FINISHED'}:
        raise RuntimeError(engine+' could not start')
    state = JOB['bridges'][engine]._RUN_STATE
    config = json.loads(Path(state['config_path']).read_text(encoding='utf-8'))
    JOB['expected_run'] = config['output']['export_run_id']
    JOB['geometry'] = comparison.geometry_evidence(config)
    _status(scene, f"{JOB['order'].index(engine)+1}/2 {engine.title()} paths running")


def start(context, engine_order=('sionna', 'differt'), managed=False):
    if JOB or (locked() and not managed):
        raise ValueError('A comparison is already running')
    if len(engine_order)!=2 or set(engine_order)!={'sionna','differt'}:
        raise ValueError('Run each engine exactly once')
    engines = bridges()
    if not all(b._processes_idle() for b in engines.values()):
        raise ValueError('Wait for current simulations before starting a comparison')
    scene = context.scene
    for engine, bridge in engines.items():
        settings = getattr(scene, engine+'_bridge')
        if bridge._resolve_python_executable(settings)[0] is None:
            raise ValueError('Configure the '+engine+' runtime first')
    restore = {engine: {name:getattr(getattr(scene, engine+'_bridge'), name) for name in TEMPORARY}
               for engine in engines}
    JOB.update(scene=scene, bridges=engines, restore=restore, studies={}, order=list(engine_order))
    try:
        for engine in engines:
            getattr(scene, engine+'_bridge').dynamic_mode = False
        _BRIDGE._workflow_compat.copy_setup(_BRIDGE, context)
        for engine in engines:
            settings = getattr(scene, engine+'_bridge')
            settings.simulate_paths = True
            settings.simulate_radio_map = settings.simulate_radio_map_3d = False
            settings.refresh_scene_before_run = settings.parameter_analysis_enabled = True
            settings.dynamic_mode = False
            for name in TEMPORARY[6:]:
                setattr(settings, name, False)
        _start(JOB['order'][0])
        if not bpy.app.timers.is_registered(tick):
            bpy.app.timers.register(tick, first_interval=0.25)
    except Exception:
        cancel('Comparison failed to start')
        raise


def tick():
    if not JOB:
        return None
    try:
        scene = JOB['scene']
        if bpy.context.scene != scene:
            raise RuntimeError('Active scene changed; comparison stopped')
        engine = JOB['engine']
        bridge = JOB['bridges'][engine]
        # Also supports deterministic background-mode checks without a UI event loop.
        for state, poll in ((bridge._RUN_STATE, getattr(bridge, '_poll_'+engine+'_process')),
                            (bridge._RADIO_MAP_STATE, bridge._poll_radio_map_process),
                            (bridge._RADIO_MAP_3D_STATE, bridge._poll_radio_map_3d_process)):
            process = state.get('process')
            if process is not None and process.poll() is not None:
                poll()
        if not bridge._processes_idle():
            return 0.25
        study, obj = _snapshot(engine, bridge, scene)
        if study['run_id'] != JOB['expected_run']:
            raise RuntimeError(engine+' produced no fresh accepted result: '+getattr(scene, engine+'_bridge').last_status)
        study['geometry_evidence'] = JOB['geometry']
        study['execution'] = {'wall_seconds_including_export_import': time.monotonic()-JOB['started'],
                              'bridge_version': bridge._ADDON_VERSION}
        obj['radio_comparison_evidence'] = json.dumps({key:study[key] for key in ('run_id', 'geometry_evidence', 'execution')})
        JOB['studies'][engine] = study
        if engine == JOB['order'][0]:
            _start(JOB['order'][1])
            return 0.25
        studies = JOB['studies']
        _restore()
        JOB.clear()
        _write(scene, studies)
    except Exception as exc:
        if JOB:
            cancel('Comparison failed: '+str(exc))
        else:
            _status(bpy.context.scene, 'Comparison failed: '+str(exc))
    return None


def update_grid(context, clear=False):
    """Manage only receivers created by this action; retain manual devices."""
    engines = bridges()
    if locked() or not all(b._processes_idle() for b in engines.values()):
        raise ValueError('Wait for simulations before changing the receiver grid')
    scene = context.scene
    settings = scene.differt_bridge
    points = [] if clear else grid_positions(settings.comparison_grid_center,
        settings.comparison_grid_size, settings.comparison_grid_columns, settings.comparison_grid_rows)
    owner = scene.get('radio_comparison_grid_id') or uuid.uuid4().hex
    scene['radio_comparison_grid_id'] = owner
    collection = engines['sionna']._ensure_environment(scene)['rxs']
    existing = {int(o['radio_grid_index']):o for o in scene.objects
                if o.get('radio_grid_owner') == owner and not o.get('differt_source_device')}
    for index, position in enumerate(points):
        obj = existing.get(index)
        if obj is None:
            obj = bpy.data.objects.new(f'Grid_RX_{index+1:03d}', None)
            collection.objects.link(obj)
            obj['radio_grid_owner'] = owner
            obj['radio_grid_index'] = index
            obj.empty_display_type = 'SPHERE'
            obj.empty_display_size = .12
            obj.color = (.1, .7, 1., 1.)
            obj.sionna_device_config.configured = True
        obj['sionna_role'] = 'RX'
        obj.location = position
        obj.hide_set(False)
        obj['radio_grid_active'] = True
    for index, obj in existing.items():
        if index >= len(points):
            if 'sionna_role' in obj: del obj['sionna_role']
            obj['radio_grid_active'] = False
            obj.hide_set(True)
    engines['sionna']._sync_device_representations(scene)
    context.view_layer.update()
    _BRIDGE._workflow_compat.copy_setup(_BRIDGE, context)
    _BRIDGE._sync_device_representations(scene)
    _status(scene, f'Grid ready: {len(points)} receivers; manual devices retained')
    return len(points)


def build_classes(bridge):
    global _BRIDGE
    _BRIDGE = bridge

    class DIFFERT_OT_UpdateComparisonGrid(bpy.types.Operator):
        bl_idname = 'differt_bridge.update_comparison_grid'
        bl_label = 'Create / Update RX Grid'
        bl_description = 'Create cell-center point receivers in Sionna and copy them to DiffeRT; existing manual receivers are retained'
        bl_options = {'REGISTER', 'UNDO'}
        @classmethod
        def poll(cls, context): return not locked()
        def execute(self, context):
            try:
                update_grid(context)
                return {'FINISHED'}
            except Exception as exc:
                self.report({'ERROR'}, str(exc)); return {'CANCELLED'}

    class DIFFERT_OT_ClearComparisonGrid(bpy.types.Operator):
        bl_idname = 'differt_bridge.clear_comparison_grid'
        bl_label = 'Deactivate Grid'
        bl_description = 'Remove generated grid receivers from simulation in both engines; retain their objects and manual devices'
        bl_options = {'REGISTER', 'UNDO'}
        @classmethod
        def poll(cls, context): return not locked()
        def execute(self, context):
            try:
                update_grid(context, clear=True)
                return {'FINISHED'}
            except Exception as exc:
                self.report({'ERROR'}, str(exc)); return {'CANCELLED'}

    class DIFFERT_OT_RunComparison(bpy.types.Operator):
        bl_idname = 'differt_bridge.run_comparison'
        bl_label = 'Run Both — Paths'
        bl_description = 'Copy the Sionna setup, run fresh paths in both engines sequentially, and save a comparison; output selections are restored'
        @classmethod
        def poll(cls, context): return not locked()
        def execute(self, context):
            try:
                start(context)
                return {'FINISHED'}
            except Exception as exc:
                self.report({'ERROR'}, str(exc))
                return {'CANCELLED'}

    class DIFFERT_OT_CancelComparison(bpy.types.Operator):
        bl_idname = 'differt_bridge.cancel_comparison'
        bl_label = 'Stop Comparison'
        def execute(self, context):
            if _BRIDGE._benchmark.active(): _BRIDGE._benchmark.stop()
            else: cancel()
            return {'FINISHED'}

    class DIFFERT_OT_CompareResults(bpy.types.Operator):
        bl_idname = 'differt_bridge.compare_results'
        bl_label = 'Compare Saved Path Results'
        bl_description = 'Compare each bridge\'s selected Parameter Analysis result without running simulations'
        @classmethod
        def poll(cls, context): return not locked()
        def execute(self, context):
            try:
                studies = {e:_snapshot(e,b,context.scene,selected=True)[0] for e,b in bridges().items()}
                _write(context.scene, studies)
                return {'FINISHED'}
            except Exception as exc:
                self.report({'ERROR'}, str(exc))
                return {'CANCELLED'}

    class DIFFERT_OT_OpenComparison(bpy.types.Operator):
        bl_idname = 'differt_bridge.open_comparison'
        bl_label = 'Open Comparison Report'
        def execute(self, context):
            path = Path(context.scene.differt_bridge.comparison_report)
            if not path.is_file():
                self.report({'ERROR'}, 'Create a comparison report first')
                return {'CANCELLED'}
            webbrowser.open(path.resolve().as_uri())
            return {'FINISHED'}

    return (DIFFERT_OT_UpdateComparisonGrid, DIFFERT_OT_ClearComparisonGrid,
            DIFFERT_OT_RunComparison, DIFFERT_OT_CancelComparison,
            DIFFERT_OT_CompareResults, DIFFERT_OT_OpenComparison) + path_view.build_classes(sys.modules[__name__])

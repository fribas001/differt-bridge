"""Workstation defaults kept in user preferences, independently of .blend files."""
from pathlib import Path

import bpy
from bpy.app.handlers import persistent
from bpy.props import StringProperty


def preferences():
    addon = bpy.context.preferences.addons.get(__package__)
    return addon.preferences if addon else None


def apply_defaults(scene=None):
    prefs = preferences()
    if prefs is None or getattr(bpy.data, "scenes", None) is None:
        return
    scenes = [scene] if scene else bpy.data.scenes
    for current in scenes:
        for engine in ("differt", "sionna"):
            settings = getattr(current, engine + "_bridge", None)
            executable = getattr(prefs, engine + "_python", "").strip()
            if settings is None:
                continue
            # Preserve a scene's explicit interpreter or Blender runtime choice.
            has_python = bool(getattr(settings, engine + "_python", "").strip())
            has_packages = bool(getattr(settings, engine + "_site_packages", "").strip())
            explicit_blender = settings.is_property_set("runtime_mode") and settings.runtime_mode == "BLENDER"
            if executable and not (has_python or has_packages or explicit_blender):
                setattr(settings, engine + "_python", executable)
                settings.runtime_mode = "EXTERNAL"
            if prefs.workspace_root and not settings.is_property_set("workspace_dir"):
                settings.workspace_dir = str(Path(bpy.path.abspath(prefs.workspace_root)) / (engine + "_runs"))
            if engine == "sionna" and prefs.llvm_library and not settings.drjit_libllvm_path:
                settings.drjit_libllvm_path = prefs.llvm_library


@persistent
def load_defaults(_dummy):
    apply_defaults()


def _changed(_self, _context):
    apply_defaults()


class DIFFERT_AP_RuntimeDefaults(bpy.types.AddonPreferences):
    bl_idname = __package__

    differt_python: StringProperty(name="Default DiffeRT Python", subtype="FILE_PATH", update=_changed)
    sionna_python: StringProperty(name="Default Sionna Python", subtype="FILE_PATH", update=_changed)
    workspace_root: StringProperty(name="Default Results Folder", subtype="DIR_PATH", update=_changed)
    llvm_library: StringProperty(name="Sionna LLVM Library", subtype="FILE_PATH", update=_changed)

    def draw(self, _context):
        layout = self.layout
        layout.label(text="Defaults for new scenes and scenes without configured runtimes.")
        layout.prop(self, "differt_python")
        layout.prop(self, "sionna_python")
        layout.prop(self, "workspace_root")
        layout.prop(self, "llvm_library")
        layout.label(text="Each sidebar's Runtime panel can override these defaults per scene.")

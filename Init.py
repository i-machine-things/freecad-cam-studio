"""Console-mode init for CAM Studio.

No new document-object types are registered yet (Phase 1 reuses FreeCAD CAM's existing
Path.Main.Job / Path.Op.* objects as-is — see docs/ARCHITECTURE.md). This file exists so the
addon has the conventional Init.py/InitGui.py pair; it will matter once/if this workbench adds
its own FeaturePython types.
"""

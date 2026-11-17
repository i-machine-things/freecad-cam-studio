"""CAM Studio's own TaskPanelOpPage implementations.

Each module here is a Fusion-360-workflow-style replacement for one of
stock FreeCAD CAM's operation edit pages (Path.Op.Gui.*'s own
TaskPanelOpPage classes), built from scratch against the public
Path.Op.Gui.Base.TaskPanelPage contract -- see docs/ARCHITECTURE.md.
No FreeCAD .ui resource files are reused; only the underlying
Path::FeaturePython object properties and small, generic Base.py
helper methods (tool controller / coolant combo population) are shared.
"""

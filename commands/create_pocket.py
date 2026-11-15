"""CamStudio_Pocket: Fusion-360-style "Pocket" operation command.

Phase 1, step A: wires our own toolbar/menu entry through FreeCAD CAM's
existing generic op-creation machinery (Path.Op.Gui.Base.CommandResources /
CommandPathOp -- see docs/ARCHITECTURE.md's "Resolved" section), creating
the exact same PocketShape.ObjectPocket object stock CAM's own "Pocket
Shape" command creates. For now this reuses stock CAM's own
TaskPanelOpPage for the edit dialog; replacing that with CAM Studio's own
Fusion-style page layout is the next step (docs/ROADMAP.md).
"""

import FreeCADGui as Gui
from PySide.QtCore import QT_TRANSLATE_NOOP

import Path.Op.Gui.Base as PathOpGui
import Path.Op.Gui.PocketShape as PathPocketShapeGui
import Path.Op.PocketShape as PathPocketShape

_res = PathOpGui.CommandResources(
    # NOTE: "name" is not just a label -- Path.Op.Gui.Base's ViewProvider uses it both as the
    # TaskPanel's title text AND as the lookup key into Path.Op.Gui.Selection's per-op-type
    # selection-mode registry (PathSelection.select(self.OpName)). It must stay the exact
    # upstream op-type string ("Pocket Shape"), or that lookup raises KeyError. Our own
    # branding lives in menuText/toolTip below, which have no such constraint.
    name="Pocket Shape",
    objFactory=PathPocketShape.Create,
    opPageClass=PathPocketShapeGui.TaskPanelOpPage,
    pixmap="CAM_Pocket",
    menuText=QT_TRANSLATE_NOOP("CamStudio_Pocket", "Pocket"),
    accelKey=None,
    toolTip=QT_TRANSLATE_NOOP(
        "CamStudio_Pocket", "Create a 2D Pocket operation in the active Setup"
    ),
)

Gui.addCommand("CamStudio_Pocket", PathOpGui.CommandPathOp(_res))

"""CamStudio_Pocket: Fusion-360-style "Pocket" operation command.

Wires our own toolbar/menu entry through FreeCAD CAM's existing generic
op-creation machinery (Path.Op.Gui.Base.CommandResources / CommandPathOp
-- see docs/ARCHITECTURE.md's "Resolved" section). Creates ops.pocket's
ObjectPocket (a thin subclass of stock CAM's PocketShape.ObjectPocket
that adds the "Axial Stock to Leave" property Fusion has and stock CAM
doesn't -- see ops/pocket.py), edited through CAM Studio's own page
(pages.pocket.TaskPanelOpPage) instead of stock CAM's.
"""

import FreeCADGui as Gui
from PySide.QtCore import QT_TRANSLATE_NOOP

import Path.Op.Gui.Base as PathOpGui

import ops.pocket as CamStudioPocket
import pages.pocket as CamStudioPocketPage

_res = PathOpGui.CommandResources(
    # NOTE: "name" is not just a label -- Path.Op.Gui.Base's ViewProvider uses it both as the
    # TaskPanel's title text AND as the lookup key into Path.Op.Gui.Selection's per-op-type
    # selection-mode registry (PathSelection.select(self.OpName)). It must stay the exact
    # upstream op-type string ("Pocket Shape"), or that lookup raises KeyError. Our own
    # branding lives in menuText/toolTip below, which have no such constraint.
    name="Pocket Shape",
    objFactory=CamStudioPocket.Create,
    opPageClass=CamStudioPocketPage.TaskPanelOpPage,
    pixmap="CAM_Pocket",
    menuText=QT_TRANSLATE_NOOP("CamStudio_Pocket", "2D Offset Roughing"),
    accelKey=None,
    toolTip=QT_TRANSLATE_NOOP(
        "CamStudio_Pocket",
        "Create a 2D Offset Roughing (pocket clearing) operation in the active Setup",
    ),
)

Gui.addCommand("CamStudio_Pocket", PathOpGui.CommandPathOp(_res))

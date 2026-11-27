"""CamStudio_Adaptive: Fusion-style "2D Adaptive Roughing" operation command.

Same wiring as commands/create_pocket.py: FreeCAD CAM's generic op-creation machinery creates
ops.adaptive's ObjectAdaptive (a thin subclass of FreeCAD's Adaptive operation), edited
through CAM Studio's own page (pages.adaptive.TaskPanelOpPage).
"""

import FreeCADGui as Gui
from PySide.QtCore import QT_TRANSLATE_NOOP

import Path.Op.Gui.Base as PathOpGui

import ops.adaptive as CamStudioAdaptive
import pages.adaptive as CamStudioAdaptivePage

_res = PathOpGui.CommandResources(
    # "name" must stay the upstream op-type string: it's also the key into FreeCAD's
    # per-op selection registry (see the note in commands/create_pocket.py).
    name="Adaptive",
    objFactory=CamStudioAdaptive.Create,
    opPageClass=CamStudioAdaptivePage.TaskPanelOpPage,
    pixmap="CAM_Adaptive",
    menuText=QT_TRANSLATE_NOOP("CamStudio_Adaptive", "2D Adaptive Roughing"),
    accelKey=None,
    toolTip=QT_TRANSLATE_NOOP(
        "CamStudio_Adaptive",
        "Create a 2D Adaptive Roughing (adaptive clearing) operation in the active Setup",
    ),
)

Gui.addCommand("CamStudio_Adaptive", PathOpGui.CommandPathOp(_res))

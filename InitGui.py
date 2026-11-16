"""GUI init for CAM Studio — registers the workbench with FreeCAD.

Phase 1 status: this registers an empty workbench shell. No commands/task panels exist yet
(see docs/ROADMAP.md) — Initialize() intentionally does nothing beyond the registration FreeCAD
requires, so installing this addon today is safe (it adds a toolbar entry that does nothing)
while Phase 1 UI work is still in progress.
"""

import FreeCAD as App
import FreeCADGui as Gui


class CamStudioWorkbench(Gui.Workbench):
    """Fusion-360-CAM-style workflow/UX layer over FreeCAD's existing CAM module objects."""

    MenuText = "CAM Studio"
    ToolTip = "Fusion-360-CAM-style workflow for FreeCAD's CAM module (clean-room addon)"
    Icon = "Resources/icons/workbench.svg"

    def Initialize(self):
        # Deferred imports go here once Phase 1 commands/task panels exist, per FreeCAD's
        # convention of keeping addon startup cost near zero until the workbench is activated.
        # self.appendToolbar("CAM Studio", [])
        # self.appendMenu("CAM Studio", [])
        pass

    def Activated(self):
        pass

    def Deactivated(self):
        pass

    def GetClassName(self):
        return "Gui::PythonWorkbench"


Gui.addWorkbench(CamStudioWorkbench())

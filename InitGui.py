"""GUI init for CAM Studio — registers the workbench with FreeCAD."""

import FreeCAD as App
import FreeCADGui as Gui


class CamStudioWorkbench(Gui.Workbench):
    """Fusion-360-CAM-style workflow/UX layer over FreeCAD's existing CAM module objects."""

    MenuText = "CAM Studio"
    ToolTip = "Fusion-360-CAM-style workflow for FreeCAD's CAM module (clean-room addon)"
    Icon = "Resources/icons/workbench.svg"

    command_list = [
        "CamStudio_CreateJob",
    ]

    def Initialize(self):
        # Deferred import, per FreeCAD's convention of keeping addon startup cost near zero
        # until the workbench is actually activated.
        import commands.create_job  # noqa: F401

        self.appendToolbar("CAM Studio", self.command_list)
        self.appendMenu("CAM Studio", self.command_list)

    def Activated(self):
        pass

    def Deactivated(self):
        pass

    def GetClassName(self):
        return "Gui::PythonWorkbench"


Gui.addWorkbench(CamStudioWorkbench())

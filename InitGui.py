"""GUI init for CAM Studio — registers the workbench with FreeCAD."""

import FreeCAD as App
import FreeCADGui as Gui


class CamStudioWorkbench(Gui.Workbench):
    """Fusion-360-CAM-style workflow/UX layer over FreeCAD's existing CAM module objects."""

    MenuText = "CAM Studio"
    ToolTip = "Fusion-360-CAM-style workflow for FreeCAD's CAM module (clean-room addon)"
    Icon = "Resources/icons/workbench.svg"

    toolbar_list = [
        "CamStudio_Job",
        "CamStudio_MaterialLibrary",
        "Separator",
        "CamStudio_Pocket",
    ]
    menu_list = [
        "CamStudio_Job",
        "CamStudio_MaterialLibrary",
        "Separator",
        "CamStudio_Pocket",
    ]

    def Initialize(self):
        # Deferred import, per FreeCAD's convention of keeping addon startup cost near zero
        # until the workbench is actually activated.
        import commands.create_job  # noqa: F401
        import commands.material_library  # noqa: F401
        import commands.create_pocket  # noqa: F401

        self.appendToolbar("CAM Studio", self.toolbar_list)
        self.appendMenu("CAM Studio", self.menu_list)

    def Activated(self):
        # Jobs already in the open document (made with stock CAM, or before CAM Studio's
        # Setup dialog existed) get CAM Studio's Job view provider, so double-clicking them
        # opens the Setup dialog too.
        from pages.setup import installJobAdoption

        installJobAdoption()

    def Deactivated(self):
        pass

    def GetClassName(self):
        return "Gui::PythonWorkbench"


Gui.addWorkbench(CamStudioWorkbench())

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
        "Separator",
        "CamStudio_Pocket",
        "CamStudio_Adaptive",
    ]
    # FreeCAD CAM's own commands, reused as-is (registered by Path.GuiInit.Startup below).
    actions_list = [
        "CAM_SimulatorGL",
        "CAM_Inspect",
        "CAM_Post",
        "CAM_Sanity",
    ]
    menu_list = [
        "CamStudio_Job",
        "CamStudio_ImportMaterials",
        "Separator",
        "CamStudio_Pocket",
        "CamStudio_Adaptive",
        "Separator",
    ] + actions_list

    def Initialize(self):
        # Deferred import, per FreeCAD's convention of keeping addon startup cost near zero
        # until the workbench is actually activated.
        import commands.create_job  # noqa: F401
        import commands.import_materials  # noqa: F401
        import commands.create_pocket  # noqa: F401
        import commands.create_adaptive  # noqa: F401

        # Simulate / Inspect / Post Process / Check: FreeCAD CAM's own commands. Its GUI
        # init registers them (guarded, so it runs once even if the CAM workbench loads too).
        import Path.GuiInit

        Path.GuiInit.Startup()
        from Path.Main.Gui import SanityCmd  # noqa: F401  (registers CAM_Sanity)

        self.appendToolbar("CAM Studio", self.toolbar_list)
        self.appendToolbar("CAM Studio Actions", self.actions_list)
        self.appendMenu("CAM Studio", self.menu_list)

    def Activated(self):
        # Jobs already in the open document (made with stock CAM, or before CAM Studio's
        # Setup dialog existed) get CAM Studio's Job view provider, so double-clicking them
        # opens the Setup dialog too.
        from pages.setup import installJobAdoption

        installJobAdoption()

    def Deactivated(self):
        pass

    def ContextMenu(self, recipient):
        # As in FreeCAD CAM: right-click a Job or operation to inspect its G-code.
        selection = Gui.Selection.getSelection()
        if len(selection) == 1 and selection[0].isDerivedFrom("Path::Feature"):
            self.appendContextMenu("", "Separator")
            self.appendContextMenu("", ["CAM_Inspect"])

    def GetClassName(self):
        return "Gui::PythonWorkbench"


Gui.addWorkbench(CamStudioWorkbench())

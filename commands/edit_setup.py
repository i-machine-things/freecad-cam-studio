"""CamStudio_EditSetup: open CAM Studio's Setup dialog (pages/setup.py) for the selected
or only Job."""

import FreeCAD
import FreeCADGui as Gui
from PySide.QtCore import QT_TRANSLATE_NOOP


class CommandEditSetup:
    def GetResources(self):
        return {
            "Pixmap": "CAM_Job",
            "MenuText": QT_TRANSLATE_NOOP("CamStudio_EditSetup", "Edit Setup"),
            "ToolTip": QT_TRANSLATE_NOOP(
                "CamStudio_EditSetup",
                "Edit the selected Setup: name and stock material (drives default feeds "
                "and speeds)",
            ),
        }

    def IsActive(self):
        if FreeCAD.ActiveDocument is None:
            return False
        from pages.setup import jobForSelection

        return jobForSelection() is not None

    def Activated(self):
        from pages.setup import jobForSelection, openSetup

        job = jobForSelection()
        if job is not None:
            openSetup(job)


class CommandMaterialLibrary:
    def GetResources(self):
        return {
            "Pixmap": "Std_DlgParameter",
            "MenuText": QT_TRANSLATE_NOOP("CamStudio_MaterialLibrary", "Material Library"),
            "ToolTip": QT_TRANSLATE_NOOP(
                "CamStudio_MaterialLibrary",
                "Edit CAM Studio's stock materials: surface speeds and chipload tables",
            ),
        }

    def IsActive(self):
        return True

    def Activated(self):
        from widgets.material_library import MaterialLibraryDialog

        MaterialLibraryDialog(Gui.getMainWindow()).exec_()


Gui.addCommand("CamStudio_EditSetup", CommandEditSetup())
Gui.addCommand("CamStudio_MaterialLibrary", CommandMaterialLibrary())

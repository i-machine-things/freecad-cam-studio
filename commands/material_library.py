"""CamStudio_MaterialLibrary: edit CAM Studio's stock material library.

(The Setup dialog itself opens by double-clicking a Job -- see pages/setup.py.)"""

import FreeCAD
import FreeCADGui as Gui
from PySide.QtCore import QT_TRANSLATE_NOOP


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


Gui.addCommand("CamStudio_MaterialLibrary", CommandMaterialLibrary())

# The toolbar's Job dropdown needs both of its commands registered first.
from commands.create_job import CommandJobGroup  # noqa: E402

Gui.addCommand("CamStudio_JobGroup", CommandJobGroup())

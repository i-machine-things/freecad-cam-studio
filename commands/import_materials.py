"""CamStudio_ImportMaterials: add the FeedsAndSpeeds material set to FreeCAD's User material
library (cs_materials.library.importFeedsAndSpeedsMaterials). Menu only; runs on request."""

import FreeCAD
import FreeCADGui as Gui
from PySide import QtWidgets
from PySide.QtCore import QT_TRANSLATE_NOOP

translate = FreeCAD.Qt.translate


class CommandImportMaterials:
    def GetResources(self):
        return {
            "MenuText": QT_TRANSLATE_NOOP("CamStudio_ImportMaterials", "Add Feeds && Speeds Materials"),
            "ToolTip": QT_TRANSLATE_NOOP(
                "CamStudio_ImportMaterials",
                "Add brass, plastics, stainless grades and other machining materials (surface "
                "speeds from the FreeCAD Feeds and Speeds addon, CC-BY 3.0) to FreeCAD's User "
                "material library",
            ),
        }

    def IsActive(self):
        return True

    def Activated(self):
        from cs_materials import library

        try:
            written, skipped = library.importFeedsAndSpeedsMaterials()
        except Exception as e:
            QtWidgets.QMessageBox.warning(Gui.getMainWindow(), "CAM Studio", str(e))
            return
        text = translate("CamStudio_ImportMaterials", "Added %d materials to FreeCAD's User library (CAM Studio/Feeds and Speeds).") % len(written)
        if skipped:
            text += "\n" + translate("CamStudio_ImportMaterials", "%d were already there and were left as they are.") % len(skipped)
        QtWidgets.QMessageBox.information(Gui.getMainWindow(), "CAM Studio", text)


Gui.addCommand("CamStudio_ImportMaterials", CommandImportMaterials())

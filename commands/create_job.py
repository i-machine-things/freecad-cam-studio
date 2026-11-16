"""CamStudio_CreateJob: Fusion-360-style "New Setup" entry point.

Reuses FreeCAD CAM's own Job data model and creation pipeline
(Path.Main.Gui.Job.Create) unmodified -- see docs/ARCHITECTURE.md. This
command only supplies CAM Studio's own toolbar/menu entry point and
selection-driven invocation; it creates the exact same Path::FeaturePython
Job object stock CAM's own "New Job" command creates, and reuses stock
CAM's own Job ViewProvider (Job-level editing is not part of this
project's scope -- only operation TaskPanels are, per the roadmap).
"""

import FreeCAD
import FreeCADGui as Gui
from PySide.QtCore import QT_TRANSLATE_NOOP

import Path.Base.Util as PathUtil
import Path.Main.Gui.Job as PathJobGui


class CommandCreateJob:
    def GetResources(self):
        return {
            "Pixmap": "CAM_Job",
            "MenuText": QT_TRANSLATE_NOOP("CamStudio_CreateJob", "New Setup"),
            "ToolTip": QT_TRANSLATE_NOOP(
                "CamStudio_CreateJob",
                "Create a new CAM Setup from the selected solid(s)",
            ),
        }

    def IsActive(self):
        if FreeCAD.ActiveDocument is None:
            return False
        selection = Gui.Selection.getSelection()
        return bool(selection) and all(
            PathUtil.isValidBaseObject(obj) for obj in selection
        )

    def Activated(self):
        selection = Gui.Selection.getSelection()
        if not selection:
            return
        # openTaskPanel=False: stock CAM's own Stock-editing dialog is not part of this
        # project's UI scope (only operation TaskPanels are, per docs/ROADMAP.md) -- the
        # created Job keeps stock CAM's own sensible default stock, editable later the
        # normal way (double-click the Stock item), same as in stock CAM itself.
        job = PathJobGui.Create(selection, None, openTaskPanel=False)
        if job is not None:
            # Fusion opens the Setup dialog as soon as a setup is created; CAM Studio's
            # (pages/setup.py) is where the stock material is picked.
            from pages.setup import openSetup

            openSetup(job)


Gui.addCommand("CamStudio_CreateJob", CommandCreateJob())

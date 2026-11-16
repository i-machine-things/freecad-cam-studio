"""CAM Studio's Job toolbar action.

- CamStudio_Job: with solids selected, creates a new Job (setup) through FreeCAD CAM's own
  creation pipeline (Path.Main.Gui.Job.Create, unmodified) and opens CAM Studio's Setup
  dialog for it, as Fusion opens a new setup. With a Job -- or anything inside one --
  selected, opens that Job's Setup dialog instead. Double-clicking a Job does the same.
"""

import FreeCAD
import FreeCADGui as Gui
from PySide.QtCore import QT_TRANSLATE_NOOP

import Path.Base.Util as PathUtil
import Path.Main.Gui.Job as PathJobGui


def _selectedJob():
    import PathScripts.PathUtils as PathUtils
    from pages.setup import isJob

    for obj in Gui.Selection.getSelection():
        if isJob(obj):
            return obj
        job = PathUtils.findParentJob(obj)
        if job is not None:
            return job
    return None


def _selectedSolids():
    selection = Gui.Selection.getSelection()
    if selection and all(PathUtil.isValidBaseObject(obj) for obj in selection):
        return selection
    return None


class CommandJob:
    def GetResources(self):
        return {
            "Pixmap": "CAM_Job",
            "MenuText": QT_TRANSLATE_NOOP("CamStudio_Job", "Job"),
            "ToolTip": QT_TRANSLATE_NOOP(
                "CamStudio_Job",
                "Create a Job (setup) from the selected solid(s), or open the selected "
                "Job's setup",
            ),
        }

    def IsActive(self):
        if FreeCAD.ActiveDocument is None:
            return False
        return _selectedJob() is not None or _selectedSolids() is not None

    def Activated(self):
        from pages.setup import adoptJob, openSetup

        job = _selectedJob()
        if job is None:
            solids = _selectedSolids()
            if not solids:
                return
            # openTaskPanel=False: CAM Studio's Setup dialog opens instead of FreeCAD's.
            job = PathJobGui.Create(solids, None, openTaskPanel=False)
            if job is None:
                return
        adoptJob(job)
        openSetup(job)


Gui.addCommand("CamStudio_Job", CommandJob())

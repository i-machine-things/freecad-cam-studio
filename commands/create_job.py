"""CAM Studio's Job toolbar action.

- CamStudio_Job: with solids selected, creates a new Job (setup) through FreeCAD CAM's own
  creation pipeline (Path.Main.Gui.Job.Create, unmodified) and opens FreeCAD's Job Edit
  for it -- with CAM Studio's Material row (pages/setup.py) -- as Fusion opens a new
  setup. With a Job, or anything inside one, selected, opens that Job's Job Edit instead
  (the same as double-clicking the Job).
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
        from pages.setup import adoptJob

        job = _selectedJob()
        isNew = job is None
        if isNew:
            solids = _selectedSolids()
            if not solids:
                return
            # Created without its panel so it gets CAM Studio's view provider first; the
            # panel is then opened the way FreeCAD's own Create(openTaskPanel=True) does.
            job = PathJobGui.Create(solids, None, openTaskPanel=False)
            if job is None:
                return
        adoptJob(job)
        proxy = job.ViewObject.Proxy
        if isNew:
            # As in FreeCAD: cancelling a brand-new Job's first edit removes it.
            proxy.deleteOnReject = True
            proxy.editObject(job.Stock)
        else:
            proxy.openTaskPanel()


Gui.addCommand("CamStudio_Job", CommandJob())

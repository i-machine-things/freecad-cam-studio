"""CAM Studio's Setup dialog (Fusion's Setup), first version.

A task panel for a CAM Job, laid out as stacked bars like the operation dialog:
- Setup: the setup's name and the models it machines.
- Stock: the stock material, picked from CAM Studio's material library
  (materials/library.py), which drives each operation's default feeds and speeds.

Not built yet (still FreeCAD's own Job editor, reachable from the Setup bar): work
coordinate system / orientation, stock size and shape, post-processor settings.

The material is stored on the Job as a `StockMaterial` string property (added on first
use -- a dynamic property, so the document still opens in plain FreeCAD).
"""

import FreeCAD
import FreeCADGui as Gui
from PySide import QtGui, QtWidgets

from materials import library
from widgets.collapsible import CollapsibleSection

translate = FreeCAD.Qt.translate


def ensureStockMaterialProperty(job):
    if not hasattr(job, "StockMaterial"):
        job.addProperty(
            "App::PropertyString",
            "StockMaterial",
            "CAM Studio",
            "Stock material from CAM Studio's material library; drives default feeds and "
            "speeds of new operations",
        )


def jobForSelection():
    """The Job of the selected object (a Job, or anything inside one), else the document's
    only Job, else None."""
    import PathScripts.PathUtils as PathUtils

    for obj in Gui.Selection.getSelection():
        if hasattr(obj, "Proxy") and type(obj.Proxy).__name__ == "ObjectJob":
            return obj
        job = PathUtils.findParentJob(obj)
        if job is not None:
            return job
    doc = FreeCAD.ActiveDocument
    jobs = [o for o in doc.Objects if hasattr(o, "Proxy") and type(o.Proxy).__name__ == "ObjectJob"] if doc else []
    return jobs[0] if len(jobs) == 1 else None


class SetupTaskPanel:
    def __init__(self, job):
        self.job = job
        self.form = QtWidgets.QToolBox()
        self.form.setWindowTitle(translate("CamStudio_Setup", "Setup"))
        self.form.addItem(self._setupBar(), QtGui.QIcon(":/icons/CAM_Job.svg"),
                          translate("CamStudio_Setup", "Setup"))
        self.form.addItem(self._stockBar(), QtGui.QIcon(":/icons/CAM_Stock.svg"),
                          translate("CamStudio_Setup", "Stock"))
        self.form.setCurrentIndex(1)

    # -- bars ------------------------------------------------------------------------
    def _setupBar(self):
        w = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(w)
        section = CollapsibleSection(translate("CamStudio_Setup", "Setup"))
        rows = QtWidgets.QFormLayout()
        self.name = QtWidgets.QLineEdit(self.job.Label)
        rows.addRow(translate("CamStudio_Setup", "Name"), self.name)
        models = ", ".join(m.Label for m in getattr(self.job.Model, "Group", [])) or "-"
        modelLabel = QtWidgets.QLabel(models)
        modelLabel.setWordWrap(True)
        rows.addRow(translate("CamStudio_Setup", "Model"), modelLabel)
        more = QtWidgets.QPushButton(
            translate("CamStudio_Setup", "Stock Size, WCS && Post Processor...")
        )
        more.setToolTip(
            translate(
                "CamStudio_Setup",
                "Not in CAM Studio's Setup dialog yet: opens FreeCAD's own Job editor "
                "(this dialog's changes are kept).",
            )
        )
        more.clicked.connect(self._openJobEditor)
        rows.addRow(more)
        section.setContentLayout(rows)
        layout.addWidget(section)
        layout.addStretch(1)
        return w

    def _stockBar(self):
        w = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(w)
        section = CollapsibleSection(translate("CamStudio_Setup", "Stock Material"))
        rows = QtWidgets.QFormLayout()
        rows.setRowWrapPolicy(QtWidgets.QFormLayout.WrapLongRows)
        self.material = QtWidgets.QComboBox()
        self.summary = QtWidgets.QLabel()
        self.summary.setWordWrap(True)
        editLib = QtWidgets.QPushButton(translate("CamStudio_Setup", "Edit Material Library..."))
        editLib.clicked.connect(self._editLibrary)
        self.applyExisting = QtWidgets.QCheckBox(
            translate("CamStudio_Setup", "Also reset feeds && speeds of this setup's existing operations")
        )
        self.applyExisting.setToolTip(
            translate(
                "CamStudio_Setup",
                "New operations always start from the material. Tick this to also overwrite "
                "the Feed & Speed values of operations already in this setup.",
            )
        )
        rows.addRow(translate("CamStudio_Setup", "Material"), self.material)
        rows.addRow(self.summary)
        rows.addRow(editLib)
        rows.addRow(self.applyExisting)
        section.setContentLayout(rows)
        layout.addWidget(section)
        layout.addStretch(1)
        self.material.currentIndexChanged.connect(self._updateSummary)
        self._fillMaterials(getattr(self.job, "StockMaterial", ""))
        return w

    # -- material ----------------------------------------------------------------------
    def _fillMaterials(self, select):
        self.library = library.load()
        self.material.blockSignals(True)
        self.material.clear()
        self.material.addItem(translate("CamStudio_Setup", "(none - use tool controller feeds)"), "")
        for m in self.library:
            self.material.addItem(m["name"], m["name"])
        if select and library.find(select, self.library) is None:
            # Keep a name the library no longer has, visibly, rather than silently dropping it.
            self.material.addItem(
                translate("CamStudio_Setup", "%s (not in library)") % select, select
            )
        index = max(0, self.material.findData(select))
        self.material.setCurrentIndex(index)
        self.material.blockSignals(False)
        self._updateSummary()

    def _updateSummary(self, *_args):
        name = self.material.currentData()
        m = library.find(name, self.library) if name else None
        if not name:
            self.summary.setText(
                translate("CamStudio_Setup", "Operations take their feeds and speeds from the tool controller.")
            )
            return
        if m is None:
            self.summary.setText(
                translate("CamStudio_Setup", "Not in the material library: operations fall back to tool controller feeds.")
            )
            return
        imperial = FreeCAD.Units.Quantity(1.0, FreeCAD.Units.Length).getUserPreferred()[2] == "in"
        unit, scale = ("ft/min", 0.3048) if imperial else ("m/min", 1.0)
        parts = []
        for toolMat in library.TOOL_MATERIALS:
            n = len(m["chipload"][toolMat])
            chip = (translate("CamStudio_Setup", "%d chipload rows") % n) if n else translate(
                "CamStudio_Setup", "no chipload table (feeds from tool chipload or tool controller)"
            )
            parts.append("%s: %.0f %s, %s" % (toolMat, m["surfaceSpeed"][toolMat] / scale, unit, chip))
        self.summary.setText("\n".join(parts))

    def _editLibrary(self):
        from widgets.material_library import MaterialLibraryDialog

        current = self.material.currentData()
        dialog = MaterialLibraryDialog(Gui.getMainWindow(), select=current or None)
        if dialog.exec_():
            self._fillMaterials(current)

    def _openJobEditor(self):
        self.accept()
        self.job.ViewObject.Proxy.setEdit(self.job.ViewObject, 0)

    # -- task panel ----------------------------------------------------------------------
    def getStandardButtons(self):
        return QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel

    def accept(self):
        doc = self.job.Document
        doc.openTransaction("Edit Setup")
        name = self.name.text().strip()
        if name and name != self.job.Label:
            self.job.Label = name
        material = self.material.currentData() or ""
        ensureStockMaterialProperty(self.job)
        self.job.StockMaterial = material
        if self.applyExisting.isChecked():
            for op in getattr(self.job.Operations, "Group", []):
                proxy = getattr(op, "Proxy", None)
                if hasattr(proxy, "loadDefaultFeeds"):
                    proxy.loadDefaultFeeds(op)
                    op.touch()
        doc.commitTransaction()
        doc.recompute()
        Gui.Control.closeDialog()
        return True

    def reject(self):
        Gui.Control.closeDialog()
        return True


def openSetup(job):
    Gui.Control.closeDialog()
    panel = SetupTaskPanel(job)
    Gui.Control.showDialog(panel)
    return panel

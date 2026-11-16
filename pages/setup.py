"""CAM Studio's Setup dialog (Fusion's Setup), first version.

Opened by double-clicking a Job (JobViewProvider below) and right after New Setup, the way
Fusion opens a setup. FreeCAD's own Job editor is still one button away on the Setup bar,
and double-clicking a Job's Model or Stock item still opens FreeCAD's editor on that tab.

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

import Path.Main.Gui.Job as PathJobGui

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


class JobViewProvider(PathJobGui.ViewProvider):
    """FreeCAD's Job view provider, except that double-clicking the Job opens CAM Studio's
    Setup dialog. Everything else -- tree, icons, Model/Stock item editing, FreeCAD's Job
    editor itself (openTaskPanel) -- is inherited unchanged."""

    def __init__(self, vobj):
        super().__init__(vobj)
        # Upstream starts True so cancelling a brand-new Job's first edit deletes it. Our
        # Setup dialog never deletes the Job, and that flag would otherwise carry over to
        # the first time the user opens FreeCAD's Job editor from it.
        self.deleteOnReject = False

    def setEdit(self, vobj=None, mode=0):
        if mode != 0:
            return super().setEdit(vobj, mode)
        job = self.vobj.Object
        if not job.Proxy.integrityCheck(job):
            return False
        openSetup(job)
        return True


def adoptJob(job):
    """Give `job` CAM Studio's view provider if it still has FreeCAD's plain one (Jobs made
    with stock CAM, or before this existed). Returns True if it changed."""
    vobj = getattr(job, "ViewObject", None)
    proxy = getattr(vobj, "Proxy", None) if vobj is not None else None
    if type(proxy) is not PathJobGui.ViewProvider:
        return False
    # Switch the existing, already-attached instance to our subclass rather than assigning
    # a new one: a freshly assigned proxy isn't attached (no vobj, no origin-axis scene
    # nodes), and re-running upstream attach() would add a second axis display. Our class
    # adds no state of its own, and the document saves the new class like any proxy.
    proxy.__class__ = JobViewProvider
    proxy.deleteOnReject = False
    # FreeCAD caches the proxy's Python methods (setEdit, ...) when Proxy is assigned, so
    # re-assign the same instance to make it pick up the new class's methods.
    vobj.Proxy = proxy
    return True


def adoptJobs(doc=None):
    doc = doc or FreeCAD.ActiveDocument
    if doc is None:
        return 0
    return sum(adoptJob(o) for o in doc.Objects if isJob(o))


def isJob(obj):
    return hasattr(obj, "Proxy") and type(obj.Proxy).__name__ == "ObjectJob"


class _AdoptOnActivate:
    """App document observer: when a document becomes active (opened or switched to) while
    CAM Studio is loaded, give its Jobs CAM Studio's view provider. Deferred to the event
    loop so the GUI side of a just-opened document exists."""

    def slotActivateDocument(self, doc):
        from PySide import QtCore

        name = doc.Name
        QtCore.QTimer.singleShot(0, lambda: _adoptByName(name))


def _adoptByName(name):
    try:
        doc = FreeCAD.getDocument(name)
    except Exception:
        return
    adoptJobs(doc)


_observer = None


def installJobAdoption():
    global _observer
    if _observer is None:
        _observer = _AdoptOnActivate()
        FreeCAD.addDocumentObserver(_observer)
    adoptJobs()


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
        # FreeCAD's own Job editor (inherited, not overridden in JobViewProvider).
        self.job.ViewObject.Proxy.openTaskPanel()

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
        self._close()
        return True

    def reject(self):
        self._close()
        return True

    def _close(self):
        Gui.Control.closeDialog()
        # Opened by a double-click, the Job is in edit mode until we end it.
        guiDoc = Gui.getDocument(self.job.Document.Name)
        if guiDoc is not None and guiDoc.getInEdit() is not None:
            guiDoc.resetEdit()


def openSetup(job):
    Gui.Control.closeDialog()
    panel = SetupTaskPanel(job)
    Gui.Control.showDialog(panel)
    return panel

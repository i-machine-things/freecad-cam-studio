"""CAM Studio's additions to FreeCAD's Job Edit panel.

The setup (Job) is edited in FreeCAD's own Job Edit panel -- stock, coordinate system,
post processor, tools -- unchanged. CAM Studio adds one row to its Stock section:

    Material: <stock material>   [Change...]

- Change... opens FreeCAD's own machining-material picker (the same one as the panel's
  unlabelled material button, which this row replaces) and stores the choice where stock
  CAM keeps it: the Job's Stock.ShapeMaterial.
The material's surface speeds, with each tool's own Chipload, drive each operation's default
feeds and speeds (cs_materials/library.py).

It's added by JobViewProvider, a thin subclass of FreeCAD's Job view provider: Jobs created
with CAM Studio's Job button get it, and existing Jobs are switched over while CAM Studio is
active (adoptJob). Everything else -- double-click, the Model/Stock items, the tree -- is
FreeCAD's own behavior. (Module and class name are kept: saved documents reference them.)
"""

import FreeCAD
import FreeCADGui as Gui
from PySide import QtWidgets

import Path.Main.Gui.Job as PathJobGui

translate = FreeCAD.Qt.translate


class JobViewProvider(PathJobGui.ViewProvider):
    """FreeCAD's Job view provider, plus CAM Studio's Material row in Job Edit."""

    def openTaskPanel(self, activate=None):
        super().openTaskPanel(activate)
        try:
            # Keep it alive with the panel: Qt holds only weak references to bound-method
            # slots, so an unreferenced row would leave its buttons doing nothing.
            self.taskPanel.camStudioMaterialRow = MaterialRow(self.vobj.Object, self.taskPanel)
        except Exception as e:  # never break FreeCAD's own panel over our row
            FreeCAD.Console.PrintWarning("CAM Studio: material row not added: %s\n" % e)


class MaterialRow:
    def __init__(self, job, taskPanel):
        self.job = job
        self.taskPanel = taskPanel
        form = taskPanel.form
        upstreamButton = form.findChild(QtWidgets.QAbstractButton, "btnMaterial")
        group = upstreamButton.parentWidget() if upstreamButton is not None else None
        layout = group.layout() if group is not None else None
        if not isinstance(layout, QtWidgets.QBoxLayout):
            raise RuntimeError("Job Edit's Stock section has an unexpected layout")
        upstreamButton.hide()  # same action as our Change... button, minus a label

        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel(translate("CamStudio_Setup", "Material:")))
        row.addSpacing(6)
        self.name = QtWidgets.QLabel()
        row.addWidget(self.name, 1)
        change = QtWidgets.QPushButton(translate("CamStudio_Setup", "Change..."))
        change.setToolTip(translate("CamStudio_Setup", "Pick the stock material (FreeCAD's machining materials)"))
        change.clicked.connect(self._change)
        row.addWidget(change)
        # Right under the stock-type / Refresh row.
        layout.insertLayout(1, row)
        self._refresh()

    def _material(self):
        stock = getattr(self.job, "Stock", None)
        return getattr(stock, "ShapeMaterial", None) if stock is not None else None

    def _refresh(self):
        from cs_materials import library

        material = self._material()
        machining = library.stockMaterial(self.job)
        if machining is not None:
            self.name.setText(machining.Name)
            self.name.setToolTip("")
        elif material is not None and getattr(material, "Name", ""):
            self.name.setText(
                translate("CamStudio_Setup", "%s (no machining data)") % material.Name
            )
            self.name.setToolTip(
                translate(
                    "CamStudio_Setup",
                    "This material has no surface speeds, so operations keep the tool "
                    "controller's feeds and speeds. Pick a machining material.",
                )
            )
        else:
            self.name.setText(translate("CamStudio_Setup", "(none)"))

    def _change(self):
        # FreeCAD's own picker and assignment (stores Stock.ShapeMaterial).
        self.taskPanel.assignMaterial()
        self._refresh()


def adoptJob(job):
    """Give `job` CAM Studio's view provider if it still has FreeCAD's plain one (Jobs made
    with stock CAM, or before CAM Studio). Returns True if it changed.

    The existing, already-attached instance is switched to our subclass (it adds no state)
    rather than replaced: a freshly assigned proxy isn't attached, and re-running upstream
    attach() would add a second origin-axis display. FreeCAD caches the proxy's methods when
    Proxy is assigned, so the same instance is re-assigned to refresh that cache."""
    vobj = getattr(job, "ViewObject", None)
    proxy = getattr(vobj, "Proxy", None) if vobj is not None else None
    if type(proxy) is not PathJobGui.ViewProvider:
        return False
    proxy.__class__ = JobViewProvider
    vobj.Proxy = proxy
    return True


def isJob(obj):
    return hasattr(obj, "Proxy") and type(obj.Proxy).__name__ == "ObjectJob"


def adoptJobs(doc=None):
    doc = doc or FreeCAD.ActiveDocument
    if doc is None:
        return 0
    return sum(adoptJob(o) for o in doc.Objects if isJob(o))


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

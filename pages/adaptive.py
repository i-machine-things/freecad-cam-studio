"""CAM Studio's 2D Adaptive Roughing edit pages.

Same dialog as 2D Offset Roughing (pages/common.py): Tool, Base Geometry, Extensions, Heights,
Passes, Linking. The Tool and Heights bars are the shared ones; Passes and Linking show FreeCAD's
Adaptive settings under Fusion's names and in Fusion's order. What Fusion has and FreeCAD's
Adaptive doesn't is tracked in docs/ROADMAP.md's 2D Adaptive Roughing parity map.
"""

import FreeCAD
from PySide import QtWidgets

import Path.Op.Gui.FeatureExtension as PathFeatureExtensionsGui

from pages.common import (
    BarPage,
    StepoverRow,
    ToolBarPage,
    form_layout,
    qty_commit,
    qty_set,
    quantity_spinbox,
)
from widgets.collapsible import CollapsibleSection

translate = FreeCAD.Qt.translate


class TaskPanelOpPage(ToolBarPage):
    ICON = ":/icons/CAM_Adaptive.svg"

    def opTitle(self):
        return translate("CamStudio_Adaptive", "2D Adaptive Roughing")

    def makeBars(self, obj):
        return [PassesPage(obj, self.features), LinkingPage(obj, self.features)]

    def taskPanelBaseLocationPage(self, obj, features):
        # Same as FreeCAD's Adaptive page: Extensions in the Locations slot.
        if not hasattr(self, "extensionsPanel"):
            self.extensionsPanel = PathFeatureExtensionsGui.TaskPanelExtensionPage(obj, features)
        return self.extensionsPanel


class PassesPage(BarPage):
    """Passes bar: Passes, Multiple Depths, Stock to Leave, then FreeCAD's own options."""

    def __init__(self, obj, features):
        super().__init__(obj, features)
        # FreeCAD's Extensions page looks up the page titled "Operation" that owns the
        # Use outline checkbox; that's this page.
        self.panelTitle = "Operation"

    def getTitle(self, obj):
        return translate("CamStudio_Adaptive", "Passes")

    def getForm(self):
        form = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(form)

        passes = CollapsibleSection(translate("CamStudio_Adaptive", "Passes"))
        rows = form_layout()
        form.tolerance = QtWidgets.QDoubleSpinBox()
        form.tolerance.setRange(0.001, 1.0)
        form.tolerance.setDecimals(3)
        form.tolerance.setSingleStep(0.01)
        form.tolerance.setToolTip(
            translate(
                "CamStudio_Adaptive",
                "FreeCAD's adaptive accuracy factor (not a distance): smaller is more accurate "
                "and slower to calculate, larger is faster.",
            )
        )
        rows.addRow(translate("CamStudio_Adaptive", "Tolerance"), form.tolerance)
        # Fusion's Optimal Load: the cutter's sideways engagement. FreeCAD's adaptive solver
        # holds the engagement to its StepOver (% of the tool diameter).
        self.stepover = StepoverRow(form)
        form.maxStepover.setToolTip(
            translate("CamStudio_Adaptive", "Sideways engagement the solver keeps the cutter at")
        )
        rows.addRow(translate("CamStudio_Adaptive", "Optimal Load"), self.stepover.layout)
        passes.setContentLayout(rows)
        layout.addWidget(passes)

        # Filled in by addDepthRows once the panel hands over FreeCAD's depth fields.
        form.depthsGroup = CollapsibleSection(translate("CamStudio_Adaptive", "Multiple Depths"))
        form.depthsLayout = form_layout()
        form.depthsGroup.setContentLayout(form.depthsLayout)
        form.depthsGroup.hide()
        layout.addWidget(form.depthsGroup)

        stock = CollapsibleSection(translate("CamStudio_Adaptive", "Stock to Leave"))
        stockRows = form_layout()
        form.radialStockToLeave = quantity_spinbox()
        stockRows.addRow(
            translate("CamStudio_Adaptive", "Radial Stock to Leave"), form.radialStockToLeave
        )
        stock.setContentLayout(stockRows)
        layout.addWidget(stock)

        # FreeCAD's adaptive options with no Fusion equivalent, labeled plainly.
        options = CollapsibleSection(translate("CamStudio_Adaptive", "Other Options"))
        optionRows = form_layout()
        form.side = QtWidgets.QComboBox()
        form.side.addItem(translate("CamStudio_Adaptive", "Inside the selection"), "Inside")
        form.side.addItem(
            translate("CamStudio_Adaptive", "Outside the selection, to the stock edge"), "Outside"
        )
        optionRows.addRow(translate("CamStudio_Adaptive", "Clear"), form.side)
        form.forceInsideOut = QtWidgets.QCheckBox(
            translate("CamStudio_Adaptive", "Start inside, clear toward the edges")
        )
        form.forceInsideOut.setToolTip(
            translate(
                "CamStudio_Adaptive",
                "Always enter in the middle of the material and work out (FreeCAD: Force "
                "Inside Out). Off: the solver may enter from an open side.",
            )
        )
        form.finishingProfile = QtWidgets.QCheckBox(
            translate("CamStudio_Adaptive", "Finishing profile pass at the end")
        )
        form.useOutline = QtWidgets.QCheckBox(
            translate("CamStudio_Adaptive", "Use outline of selected geometry (ignore islands)")
        )
        form.stopButton = QtWidgets.QPushButton(translate("CamStudio_Adaptive", "Stop Calculation"))
        form.stopButton.setCheckable(True)
        form.stopButton.setToolTip(
            translate(
                "CamStudio_Adaptive",
                "Stop a long adaptive calculation; the toolpath keeps what was computed so far.",
            )
        )
        for widget in (form.forceInsideOut, form.finishingProfile, form.useOutline, form.stopButton):
            optionRows.addRow(widget)
        options.setContentLayout(optionRows)
        layout.addWidget(options)

        layout.addStretch(1)
        return form

    def addDepthRows(self, depthsForm):
        """Fusion's Multiple Depths section, with FreeCAD's Step Down / Finish Step Down
        fields (still driven by FreeCAD's Depths page, see HeightsBar)."""
        f = self.form
        added = False
        for name, label in (
            ("stepDown", "Maximum Roughing Stepdown"),
            ("finishDepth", "Finishing Stepdown"),
        ):
            widget = getattr(depthsForm, name, None)
            if widget is not None and not widget.isHidden():
                f.depthsLayout.addRow(translate("CamStudio_Adaptive", label), widget)
                added = True
        f.depthsGroup.setVisible(added)

    def initBar(self, obj):
        self.setIcon(":/icons/CAM_Adaptive.svg")

    def updateData(self, obj, prop):
        # Tool chosen on the Tool bar: its diameter sets the Optimal Load distance.
        if prop in ("ToolController", "StepOver"):
            self.stepover.show(obj)

    def getFields(self, obj):
        f = self.form
        tolerance = round(f.tolerance.value(), f.tolerance.decimals())
        if abs(obj.Tolerance - tolerance) > 10.0 ** -f.tolerance.decimals() / 2.0:
            obj.Tolerance = tolerance
        self.stepover.commit(obj)
        qty_commit(obj, "StockToLeave", f.radialStockToLeave)
        if obj.Side != str(f.side.currentData()):
            obj.Side = str(f.side.currentData())
        for prop, widget in self._checkboxes():
            if getattr(obj, prop) != widget.isChecked():
                setattr(obj, prop, widget.isChecked())
        # FreeCAD's adaptive watches StopProcessing while it calculates.
        if f.stopButton.isChecked():
            f.stopButton.setChecked(False)
            obj.Stopped = True
            obj.StopProcessing = True

    def setFields(self, obj):
        f = self.form
        f.tolerance.setValue(obj.Tolerance)
        self.stepover.show(obj)
        qty_set(f.radialStockToLeave, obj.StockToLeave.Value)
        f.side.setCurrentIndex(max(0, f.side.findData(obj.Side)))
        for prop, widget in self._checkboxes():
            widget.setChecked(getattr(obj, prop))
        f.stopButton.setChecked(False)

    def getSignalsForUpdate(self, obj):
        f = self.form
        return (
            [f.tolerance.editingFinished, f.radialStockToLeave.editingFinished,
             f.side.currentIndexChanged, f.stopButton.toggled]
            + self.stepover.signals()
            + [widget.clicked for _prop, widget in self._checkboxes()]
        )

    def _checkboxes(self):
        f = self.form
        return [
            ("ForceInsideOut", f.forceInsideOut),
            ("FinishingProfile", f.finishingProfile),
            ("UseOutline", f.useOutline),
        ]


class LinkingPage(BarPage):
    """Linking bar: Linking, then Ramp -- Fusion's Linking tab order."""

    def getTitle(self, obj):
        return translate("CamStudio_Adaptive", "Linking")

    def getForm(self):
        form = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(form)

        link = CollapsibleSection(translate("CamStudio_Adaptive", "Linking"))
        linkRows = form_layout()
        form.liftHeight = quantity_spinbox()
        form.liftHeight.setToolTip(
            translate(
                "CamStudio_Adaptive",
                "How far the tool lifts for moves through already-cleared area "
                "(FreeCAD: Lift Distance). 0 = stays at cutting depth.",
            )
        )
        form.stayDownRatio = QtWidgets.QDoubleSpinBox()
        form.stayDownRatio.setRange(0.0, 100.0)
        form.stayDownRatio.setDecimals(1)
        form.stayDownRatio.setSuffix(" x")
        form.stayDownRatio.setToolTip(
            translate(
                "CamStudio_Adaptive",
                "Stay down for a link when its path through cleared area is at most this many "
                "times the straight distance; otherwise retract (FreeCAD: Keep Tool Down Ratio).",
            )
        )
        linkRows.addRow(translate("CamStudio_Adaptive", "Lift Height"), form.liftHeight)
        linkRows.addRow(translate("CamStudio_Adaptive", "Stay-Down Path Limit"), form.stayDownRatio)
        link.setContentLayout(linkRows)
        layout.addWidget(link)

        ramp = CollapsibleSection(translate("CamStudio_Adaptive", "Ramp"))
        rampRows = form_layout()
        # FreeCAD's adaptive always enters with a helix; the solver places it.
        form.rampType = QtWidgets.QComboBox()
        form.rampType.addItem(translate("CamStudio_Adaptive", "Helix"), "Helix")
        form.rampType.setEnabled(False)
        form.rampType.setToolTip(
            translate("CamStudio_Adaptive", "FreeCAD's adaptive enters every level with a helix.")
        )
        form.rampAngle = quantity_spinbox(unit="deg")
        form.rampTaperAngle = quantity_spinbox(unit="deg")
        form.rampTaperAngle.setToolTip(
            translate(
                "CamStudio_Adaptive",
                "Narrows the helix as it descends (a cone). Not available with arcs.",
            )
        )
        form.helicalRampDiameter = quantity_spinbox()
        form.helicalRampDiameter.setToolTip(
            translate(
                "CamStudio_Adaptive",
                "Largest helix diameter the solver may use, up to the tool diameter. 0 = tool "
                "diameter.",
            )
        )
        form.useHelixArcs = QtWidgets.QCheckBox(
            translate("CamStudio_Adaptive", "Output the helix as arcs (G2)")
        )
        form.useHelixArcs.clicked.connect(lambda *_: self._updateEnabled())
        rampRows.addRow(translate("CamStudio_Adaptive", "Ramp Type"), form.rampType)
        rampRows.addRow(translate("CamStudio_Adaptive", "Ramping Angle"), form.rampAngle)
        rampRows.addRow(translate("CamStudio_Adaptive", "Ramp Taper Angle"), form.rampTaperAngle)
        rampRows.addRow(
            translate("CamStudio_Adaptive", "Helical Ramp Diameter (0 = tool Ø)"),
            form.helicalRampDiameter,
        )
        rampRows.addRow(form.useHelixArcs)
        ramp.setContentLayout(rampRows)
        layout.addWidget(ramp)

        layout.addStretch(1)
        return form

    def initBar(self, obj):
        self.setIcon(":/icons/CAM_Adaptive.svg")

    def _updateEnabled(self):
        self.form.rampTaperAngle.setEnabled(not self.form.useHelixArcs.isChecked())

    def _quantities(self):
        f = self.form
        return [
            ("LiftDistance", f.liftHeight),
            ("HelixAngle", f.rampAngle),
            ("HelixConeAngle", f.rampTaperAngle),
            ("HelixDiameterLimit", f.helicalRampDiameter),
        ]

    def getFields(self, obj):
        f = self.form
        for prop, widget in self._quantities():
            qty_commit(obj, prop, widget)
        ratio = f.stayDownRatio.value()
        if abs(float(obj.KeepToolDownRatio) - ratio) > 10.0 ** -f.stayDownRatio.decimals() / 2.0:
            obj.KeepToolDownRatio = ratio
        if obj.UseHelixArcs != f.useHelixArcs.isChecked():
            obj.UseHelixArcs = f.useHelixArcs.isChecked()
        self._updateEnabled()

    def setFields(self, obj):
        f = self.form
        for prop, widget in self._quantities():
            qty_set(widget, getattr(obj, prop).Value)
        f.stayDownRatio.setValue(float(obj.KeepToolDownRatio))
        f.useHelixArcs.setChecked(obj.UseHelixArcs)
        self._updateEnabled()

    def getSignalsForUpdate(self, obj):
        f = self.form
        return [widget.editingFinished for _prop, widget in self._quantities()] + [
            f.stayDownRatio.editingFinished,
            f.useHelixArcs.clicked,
        ]

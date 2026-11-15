"""CAM Studio's own Pocket operation edit page.

Fields/groupings follow Fusion 360's 2D Pocket dialog terminology from
docs/spec/02-2d-milling-operations.md ("Tool" / "Passes" groups), backed
by the same Path::FeaturePython properties stock CAM's own Pocket Shape
page uses (see docs/ARCHITECTURE.md). Base geometry selection, Heights,
and Depths are *not* handled here -- those are separate shared pages the
generic Path.Op.Gui.Base.TaskPanel assembles automatically around this
one, and their FreeCAD terminology (Clearance/Safe/Start/Final Depth)
already closely matches Fusion's own Heights tab, so there's no gap to
close there.

No FreeCAD .ui resource file is loaded -- this form is built directly in
Python so CAM Studio owns the full layout, not just the data wiring.
"""

import FreeCAD
import FreeCADGui as Gui
from PySide import QtWidgets
from PySide.QtCore import Qt

import Path.Op.Gui.Base as PathOpGui
import Path.Op.PocketShape as PathPocketShape

import widgets.tool_picker as ToolPicker

translate = FreeCAD.Qt.translate


def _quantity_spinbox(unit="mm"):
    # Gui::QuantitySpinBox, created via UiLoader, only exposes QAbstractSpinBox's base
    # methods through the Python binding -- setValue()/value()/setDecimals() etc. aren't
    # reachable directly. Use the generic Qt property interface instead ("rawValue" is the
    # widget's internal-unit numeric value; "unit" sets its display unit).
    widget = Gui.UiLoader().createWidget("Gui::QuantitySpinBox")
    widget.setProperty("unit", unit)
    return widget


def _qty_get(widget):
    return widget.property("rawValue")


def _qty_set(widget, value):
    widget.setProperty("rawValue", value)


class TaskPanelOpPage(PathOpGui.TaskPanelPage):
    """Page controller for CAM Studio's Pocket command (PocketShape.ObjectPocket)."""

    def getTitle(self, obj):
        return translate("CamStudio_Pocket", "Pocket")

    def getForm(self):
        form = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(form)

        tool_group = QtWidgets.QGroupBox(translate("CamStudio_Pocket", "Tool"))
        tool_layout = QtWidgets.QFormLayout(tool_group)
        form.toolController = QtWidgets.QComboBox()
        form.selectToolButton = QtWidgets.QPushButton(translate("CamStudio_Pocket", "Select..."))
        tool_row = QtWidgets.QHBoxLayout()
        tool_row.addWidget(form.toolController, 1)
        tool_row.addWidget(form.selectToolButton)
        form.coolantController = QtWidgets.QComboBox()
        tool_layout.addRow(translate("CamStudio_Pocket", "Tool"), tool_row)
        tool_layout.addRow(translate("CamStudio_Pocket", "Coolant"), form.coolantController)
        layout.addWidget(tool_group)
        form.selectToolButton.clicked.connect(self._onSelectTool)

        passes_group = QtWidgets.QGroupBox(translate("CamStudio_Pocket", "Passes"))
        passes_layout = QtWidgets.QFormLayout(passes_group)
        form.clearingPattern = QtWidgets.QComboBox()
        form.cutMode = QtWidgets.QComboBox()
        form.stepOverPercent = QtWidgets.QSpinBox()
        form.stepOverPercent.setRange(1, 100)
        form.stepOverPercent.setSuffix("%")
        form.radialStockToLeave = _quantity_spinbox()
        form.axialStockToLeave = _quantity_spinbox()
        form.minTravel = QtWidgets.QCheckBox(
            translate("CamStudio_Pocket", "Minimize travel between cuts")
        )
        form.useRestMachining = QtWidgets.QCheckBox(
            translate("CamStudio_Pocket", "Rest machining (skip already-cleared areas)")
        )
        passes_layout.addRow(translate("CamStudio_Pocket", "Pocket Pattern"), form.clearingPattern)
        passes_layout.addRow(translate("CamStudio_Pocket", "Cutting Direction"), form.cutMode)
        passes_layout.addRow(translate("CamStudio_Pocket", "Stepover"), form.stepOverPercent)
        passes_layout.addRow(
            translate("CamStudio_Pocket", "Radial Stock to Leave"), form.radialStockToLeave
        )
        passes_layout.addRow(
            translate("CamStudio_Pocket", "Axial Stock to Leave"), form.axialStockToLeave
        )
        passes_layout.addRow(form.minTravel)
        passes_layout.addRow(form.useRestMachining)
        layout.addWidget(passes_group)

        # FreeCAD-specific options with no direct Fusion 2D Pocket equivalent -- labeled
        # plainly rather than force-mapped onto Fusion terminology that doesn't fit.
        options_group = QtWidgets.QGroupBox(translate("CamStudio_Pocket", "Other Options"))
        options_layout = QtWidgets.QFormLayout(options_group)
        form.useOutline = QtWidgets.QCheckBox(
            translate("CamStudio_Pocket", "Use outline of selected geometry (ignore islands)")
        )
        form.zigZagAngle = _quantity_spinbox(unit="deg")
        form.useStartPoint = QtWidgets.QCheckBox(
            translate("CamStudio_Pocket", "Use custom start point")
        )
        options_layout.addRow(form.useOutline)
        options_layout.addRow(translate("CamStudio_Pocket", "Zig-Zag Angle"), form.zigZagAngle)
        options_layout.addRow(form.useStartPoint)
        layout.addWidget(options_group)

        linking_group = QtWidgets.QGroupBox(translate("CamStudio_Pocket", "Linking"))
        linking_layout = QtWidgets.QFormLayout(linking_group)
        form.rampType = QtWidgets.QComboBox()
        form.rampType.addItem(translate("CamStudio_Pocket", "Plunge"), "Plunge")
        form.rampType.addItem(translate("CamStudio_Pocket", "Helix"), "Helix")
        form.rampAngle = _quantity_spinbox(unit="deg")
        linking_layout.addRow(translate("CamStudio_Pocket", "Ramp Type"), form.rampType)
        linking_layout.addRow(translate("CamStudio_Pocket", "Ramp Angle"), form.rampAngle)
        layout.addWidget(linking_group)

        layout.addStretch(1)
        return form

    def initPage(self, obj):
        self.setIcon(":/icons/CAM_Pocket.svg")
        enumTups = PathPocketShape.ObjectPocket.pocketPropertyEnumerations(dataType="raw")
        self.populateCombobox(
            self.form,
            enumTups,
            [("cutMode", "CutMode"), ("clearingPattern", "ClearingPattern")],
        )

    def _onSelectTool(self):
        tc = ToolPicker.pick_new_tool_controller(self.job, parent=self.form)
        if tc is None:
            return
        self.setupToolController(self.obj, self.form.toolController)
        self.selectInComboBox(tc.Label, self.form.toolController)
        self.setDirty()

    def updateZigZagAngleEnabled(self, obj):
        self.form.zigZagAngle.setEnabled(obj.ClearingPattern != "Offset")

    def getFields(self, obj):
        if obj.CutMode != str(self.form.cutMode.currentData()):
            obj.CutMode = str(self.form.cutMode.currentData())
        if obj.ClearingPattern != str(self.form.clearingPattern.currentData()):
            obj.ClearingPattern = str(self.form.clearingPattern.currentData())
        if obj.StepOver != self.form.stepOverPercent.value():
            obj.StepOver = self.form.stepOverPercent.value()
        if obj.ExtraOffset.Value != _qty_get(self.form.radialStockToLeave):
            obj.ExtraOffset = _qty_get(self.form.radialStockToLeave)
        if obj.AxialStockToLeave.Value != _qty_get(self.form.axialStockToLeave):
            obj.AxialStockToLeave = _qty_get(self.form.axialStockToLeave)
        if obj.ZigZagAngle != _qty_get(self.form.zigZagAngle):
            obj.ZigZagAngle = _qty_get(self.form.zigZagAngle)
        if obj.MinTravel != self.form.minTravel.isChecked():
            obj.MinTravel = self.form.minTravel.isChecked()
        if obj.UseRestMachining != self.form.useRestMachining.isChecked():
            obj.UseRestMachining = self.form.useRestMachining.isChecked()
        if obj.UseOutline != self.form.useOutline.isChecked():
            obj.UseOutline = self.form.useOutline.isChecked()
        if obj.UseStartPoint != self.form.useStartPoint.isChecked():
            obj.UseStartPoint = self.form.useStartPoint.isChecked()
        if obj.RampType != str(self.form.rampType.currentData()):
            obj.RampType = str(self.form.rampType.currentData())
        if obj.RampAngle.Value != _qty_get(self.form.rampAngle):
            obj.RampAngle = _qty_get(self.form.rampAngle)

        self.updateToolController(obj, self.form.toolController)
        self.updateCoolant(obj, self.form.coolantController)
        self.updateZigZagAngleEnabled(obj)

    def setFields(self, obj):
        self.selectInComboBox(obj.CutMode, self.form.cutMode)
        self.selectInComboBox(obj.ClearingPattern, self.form.clearingPattern)
        self.form.stepOverPercent.setValue(obj.StepOver)
        _qty_set(self.form.radialStockToLeave, obj.ExtraOffset.Value)
        _qty_set(self.form.axialStockToLeave, obj.AxialStockToLeave.Value)
        _qty_set(self.form.zigZagAngle, obj.ZigZagAngle)
        self.form.minTravel.setChecked(obj.MinTravel)
        self.form.useRestMachining.setChecked(obj.UseRestMachining)
        self.form.useOutline.setChecked(obj.UseOutline)
        self.form.useStartPoint.setChecked(obj.UseStartPoint)
        self.selectInComboBox(obj.RampType, self.form.rampType)
        _qty_set(self.form.rampAngle, obj.RampAngle.Value)
        self.updateZigZagAngleEnabled(obj)

        self.setupToolController(obj, self.form.toolController)
        self.setupCoolant(obj, self.form.coolantController)

    def getSignalsForUpdate(self, obj):
        return [
            self.form.cutMode.currentIndexChanged,
            self.form.clearingPattern.currentIndexChanged,
            self.form.stepOverPercent.editingFinished,
            self.form.radialStockToLeave.editingFinished,
            self.form.axialStockToLeave.editingFinished,
            self.form.zigZagAngle.editingFinished,
            self.form.minTravel.clicked,
            self.form.useRestMachining.clicked,
            self.form.useOutline.clicked,
            self.form.useStartPoint.clicked,
            self.form.toolController.currentIndexChanged,
            self.form.coolantController.currentIndexChanged,
            self.form.rampType.currentIndexChanged,
            self.form.rampAngle.editingFinished,
        ]

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
import PathScripts.PathUtils as PathUtils

import widgets.tool_picker as ToolPicker
from widgets.collapsible import CollapsibleSection

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
    # Remember what the widget itself reports right after loading. It rounds to its display
    # precision in the user's unit schema (3 mm reads back as 2.999994 under an inch
    # schema), so "differs from the property" is not the same as "the user edited it".
    widget.setProperty("camStudioLoaded", widget.property("rawValue"))


def _qty_commit(obj, prop, widget):
    """Write the widget's value to obj.<prop> only if the user actually changed the widget
    since it was loaded. Comparing against the property instead would rewrite every
    quantity on the page with its display-rounded form whenever any one field changed."""
    value = widget.property("rawValue")
    if value == widget.property("camStudioLoaded"):
        return
    setattr(obj, prop, value)
    widget.setProperty("camStudioLoaded", value)


def _feed_display_unit():
    """(unit label, mm/s per display unit, decimals) for a feed-rate field: always per
    minute -- the CNC convention -- in the length system the user's unit schema displays
    every other field on the page in. Under an imperial schema that's in/min, so a feed
    doesn't sit in mm/min beside distances shown in inches."""
    lengthUnit = FreeCAD.Units.Quantity(1.0, FreeCAD.Units.Length).getUserPreferred()[2]
    if lengthUnit in ("in", "ft", "thou", "yd", "mi"):
        unit, decimals = "in/min", 3
    else:
        unit, decimals = "mm/min", 2
    return unit, FreeCAD.Units.Quantity("1 " + unit).Value, decimals


class TaskPanelOpPage(PathOpGui.TaskPanelPage):
    """Page controller for CAM Studio's Pocket command (PocketShape.ObjectPocket)."""

    def getTitle(self, obj):
        return translate("CamStudio_Pocket", "2D Offset Roughing")

    def getForm(self):
        form = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(form)

        tool_group = CollapsibleSection(translate("CamStudio_Pocket", "Tool"))
        tool_layout = QtWidgets.QFormLayout()
        form.toolController = QtWidgets.QComboBox()
        form.selectToolButton = QtWidgets.QPushButton(translate("CamStudio_Pocket", "Select..."))
        tool_row = QtWidgets.QHBoxLayout()
        tool_row.addWidget(form.toolController, 1)
        tool_row.addWidget(form.selectToolButton)
        form.coolantController = QtWidgets.QComboBox()
        tool_layout.addRow(translate("CamStudio_Pocket", "Tool"), tool_row)
        tool_layout.addRow(translate("CamStudio_Pocket", "Coolant"), form.coolantController)
        tool_group.setContentLayout(tool_layout)
        layout.addWidget(tool_group)
        form.selectToolButton.clicked.connect(self._onSelectTool)

        passes_group = CollapsibleSection(translate("CamStudio_Pocket", "Passes"))
        passes_layout = QtWidgets.QFormLayout()
        passes_layout.setRowWrapPolicy(QtWidgets.QFormLayout.WrapLongRows)
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
        form.finishingPasses = QtWidgets.QSpinBox()
        form.finishingPasses.setRange(0, 20)
        # Plain spinbox, not _quantity_spinbox: Gui::QuantitySpinBox's "unit" property only
        # accepts FreeCAD's own "preferred display unit" for a Quantity type -- for Velocity
        # that's "mm/s" in this app's unit-system preference, not the "mm/min" every CNC/CAM
        # context (including FreeCAD's own ToolController feed fields) actually uses. Forcing
        # "mm/min" directly onto the widget is silently ignored (falls back to mm/s) -- a real
        # 60x unit-confusion risk for a feed rate, not just cosmetic. Converting explicitly in
        # getFields/setFields (FinishFeedrate's own internal unit is mm/s) avoids relying on
        # that widget at all. The display unit still follows the user's unit schema, via
        # _feed_display_unit: per minute always, mm or inch to match the other fields.
        feedUnit, form.finishFeedScale, feedDecimals = _feed_display_unit()
        form.finishFeedrate = QtWidgets.QDoubleSpinBox()
        form.finishFeedrate.setRange(0, 100000)
        form.finishFeedrate.setDecimals(feedDecimals)
        form.finishFeedrate.setSuffix(" " + feedUnit)
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
        passes_layout.addRow(
            translate("CamStudio_Pocket", "Number of Finishing Passes"), form.finishingPasses
        )
        passes_layout.addRow(
            translate("CamStudio_Pocket", "Finish Feedrate (0 = same as cutting)"),
            form.finishFeedrate,
        )
        passes_group.setContentLayout(passes_layout)
        layout.addWidget(passes_group)

        # FreeCAD-specific options with no direct Fusion 2D Pocket equivalent -- labeled
        # plainly rather than force-mapped onto Fusion terminology that doesn't fit.
        options_group = CollapsibleSection(translate("CamStudio_Pocket", "Other Options"))
        options_layout = QtWidgets.QFormLayout()
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
        options_group.setContentLayout(options_layout)
        layout.addWidget(options_group)

        linking_group = CollapsibleSection(translate("CamStudio_Pocket", "Linking"))
        linking_layout = QtWidgets.QFormLayout()
        # The task panel is narrow by default; the long labels here would otherwise force
        # the form wider than it and clip the fields behind a horizontal scroll bar.
        linking_layout.setRowWrapPolicy(QtWidgets.QFormLayout.WrapLongRows)
        form.rampType = QtWidgets.QComboBox()
        form.rampType.addItem(translate("CamStudio_Pocket", "Plunge"), "Plunge")
        form.rampType.addItem(translate("CamStudio_Pocket", "Helix"), "Helix")
        form.rampAngle = _quantity_spinbox(unit="deg")
        form.helicalRampDiameter = _quantity_spinbox()
        form.minimumRampDiameter = _quantity_spinbox()
        form.maxRampStepdown = _quantity_spinbox()
        linking_layout.addRow(translate("CamStudio_Pocket", "Ramp Type"), form.rampType)
        linking_layout.addRow(translate("CamStudio_Pocket", "Ramp Angle"), form.rampAngle)
        linking_layout.addRow(
            translate("CamStudio_Pocket", "Helical Ramp Diameter (0 = auto)"),
            form.helicalRampDiameter,
        )
        linking_layout.addRow(
            translate("CamStudio_Pocket", "Minimum Ramp Diameter"), form.minimumRampDiameter
        )
        linking_layout.addRow(
            translate("CamStudio_Pocket", "Maximum Ramp Stepdown (0 = unconstrained)"),
            form.maxRampStepdown,
        )
        # Lead-In and Lead-Out: enabled separately, each an arc tangent to the cut (radius +
        # sweep) with an optional straight leg outside it -- see ops/pocket.py's
        # _applyLeadInOut. Row order follows Fusion's Linking tab.
        helixNote = translate(
            "CamStudio_Pocket", "Not available while Ramp Type is Helix (the helix is the entry)."
        )
        form.useLeadIn = QtWidgets.QCheckBox(translate("CamStudio_Pocket", "Lead-In (Entry)"))
        form.useLeadIn.setToolTip(helixNote)
        form.leadInRadius = _quantity_spinbox()
        form.leadInSweepAngle = _quantity_spinbox(unit="deg")
        form.leadInDistance = _quantity_spinbox()
        form.leadInPerpendicular = QtWidgets.QCheckBox(
            translate("CamStudio_Pocket", "Perpendicular Lead-In")
        )
        form.useLeadOut = QtWidgets.QCheckBox(translate("CamStudio_Pocket", "Lead-Out (Exit)"))
        form.useLeadOut.setToolTip(helixNote)
        form.sameAsLeadIn = QtWidgets.QCheckBox(
            translate("CamStudio_Pocket", "Same as Lead-In")
        )
        form.leadOutDistance = _quantity_spinbox()
        form.leadOutRadius = _quantity_spinbox()
        form.leadOutSweepAngle = _quantity_spinbox(unit="deg")
        form.leadOutPerpendicular = QtWidgets.QCheckBox(
            translate("CamStudio_Pocket", "Perpendicular Lead-Out")
        )
        perpendicularTip = translate(
            "CamStudio_Pocket",
            "Run the straight leg square to the lead arc instead of tangent to it -- useful "
            "where a tangent leg would run into a wall, such as inside a bore.",
        )
        form.leadInPerpendicular.setToolTip(perpendicularTip)
        form.leadOutPerpendicular.setToolTip(perpendicularTip)
        linking_layout.addRow(form.useLeadIn)
        linking_layout.addRow(
            translate("CamStudio_Pocket", "Horizontal Lead-In Radius"), form.leadInRadius
        )
        linking_layout.addRow(
            translate("CamStudio_Pocket", "Lead-In Sweep Angle"), form.leadInSweepAngle
        )
        linking_layout.addRow(
            translate("CamStudio_Pocket", "Linear Lead-In Distance"), form.leadInDistance
        )
        linking_layout.addRow(form.leadInPerpendicular)
        linking_layout.addRow(form.useLeadOut)
        linking_layout.addRow(form.sameAsLeadIn)
        linking_layout.addRow(
            translate("CamStudio_Pocket", "Linear Lead-Out Distance"), form.leadOutDistance
        )
        linking_layout.addRow(
            translate("CamStudio_Pocket", "Horizontal Lead-Out Radius"), form.leadOutRadius
        )
        linking_layout.addRow(
            translate("CamStudio_Pocket", "Lead-Out Sweep Angle"), form.leadOutSweepAngle
        )
        linking_layout.addRow(form.leadOutPerpendicular)
        linking_group.setContentLayout(linking_layout)
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

    def _pruneToolComboSentinels(self, obj):
        # The inherited setupToolController() appends "Copy <name>..."/"New tool
        # controller..." sentinel entries (plus a separator) after the real tool
        # controllers, meant for a combo wired to the stock editToolController flow we
        # don't implement here (we have our own "Select..." button instead). Left in
        # place, selecting one would silently mis-resolve in getFields's plain label
        # lookup instead of doing anything. Truncate back to just the real controllers.
        combo = self.form.toolController
        realCount = len(PathUtils.getToolControllers(obj))
        while combo.count() > realCount:
            combo.removeItem(combo.count() - 1)

    def _onSelectTool(self):
        tc = ToolPicker.pick_new_tool_controller(self.job, parent=self.form)
        if tc is None:
            return
        self.setupToolController(self.obj, self.form.toolController)
        self._pruneToolComboSentinels(self.obj)
        self.selectInComboBox(tc.Label, self.form.toolController)
        self.setDirty()

    def updateZigZagAngleEnabled(self, obj):
        self.form.zigZagAngle.setEnabled(obj.ClearingPattern != "Offset")

    def updateRampFieldsEnabled(self, obj):
        isHelix = obj.RampType == "Helix"
        self.form.rampAngle.setEnabled(isHelix)
        self.form.helicalRampDiameter.setEnabled(isHelix)
        self.form.minimumRampDiameter.setEnabled(isHelix)
        self.form.maxRampStepdown.setEnabled(isHelix)
        # Mutually exclusive with Lead-In/Lead-Out for now -- see ops/pocket.py's
        # _applyLeadInOut docstring.
        self.form.useLeadIn.setEnabled(not isHelix)
        self.form.useLeadOut.setEnabled(not isHelix)
        self.updateLeadInOutFieldsEnabled(obj)

    def updateLeadInOutFieldsEnabled(self, obj):
        form = self.form
        notHelix = obj.RampType != "Helix"
        inActive = bool(obj.UseLeadIn) and notHelix
        for widget in (
            form.leadInRadius,
            form.leadInSweepAngle,
            form.leadInDistance,
            form.leadInPerpendicular,
        ):
            widget.setEnabled(inActive)
        outActive = bool(obj.UseLeadOut) and notHelix
        form.sameAsLeadIn.setEnabled(outActive)
        ownValues = outActive and not obj.SameAsLeadIn
        for widget in (
            form.leadOutDistance,
            form.leadOutRadius,
            form.leadOutSweepAngle,
            form.leadOutPerpendicular,
        ):
            widget.setEnabled(ownValues)

    def getFields(self, obj):
        if obj.CutMode != str(self.form.cutMode.currentData()):
            obj.CutMode = str(self.form.cutMode.currentData())
        if obj.ClearingPattern != str(self.form.clearingPattern.currentData()):
            obj.ClearingPattern = str(self.form.clearingPattern.currentData())
        if obj.StepOver != self.form.stepOverPercent.value():
            obj.StepOver = self.form.stepOverPercent.value()
        _qty_commit(obj, "ExtraOffset", self.form.radialStockToLeave)
        _qty_commit(obj, "AxialStockToLeave", self.form.axialStockToLeave)
        _qty_commit(obj, "ZigZagAngle", self.form.zigZagAngle)
        if obj.MinTravel != self.form.minTravel.isChecked():
            obj.MinTravel = self.form.minTravel.isChecked()
        if obj.UseRestMachining != self.form.useRestMachining.isChecked():
            obj.UseRestMachining = self.form.useRestMachining.isChecked()
        if obj.FinishingPasses != self.form.finishingPasses.value():
            obj.FinishingPasses = self.form.finishingPasses.value()
        # Only write back a real edit: the widget shows a rounded value, so comparing exactly
        # would overwrite the stored feed with its rounded display form whenever any other
        # field on the page changed.
        scale = self.form.finishFeedScale
        finishFeedMmPerSec = self.form.finishFeedrate.value() * scale
        resolution = 10.0 ** -self.form.finishFeedrate.decimals() * scale
        if abs(obj.FinishFeedrate.Value - finishFeedMmPerSec) > resolution / 2.0:
            obj.FinishFeedrate = finishFeedMmPerSec
        if obj.UseOutline != self.form.useOutline.isChecked():
            obj.UseOutline = self.form.useOutline.isChecked()
        if obj.UseStartPoint != self.form.useStartPoint.isChecked():
            obj.UseStartPoint = self.form.useStartPoint.isChecked()
        if obj.RampType != str(self.form.rampType.currentData()):
            obj.RampType = str(self.form.rampType.currentData())
        _qty_commit(obj, "RampAngle", self.form.rampAngle)
        _qty_commit(obj, "HelicalRampDiameter", self.form.helicalRampDiameter)
        _qty_commit(obj, "MinimumRampDiameter", self.form.minimumRampDiameter)
        _qty_commit(obj, "MaxRampStepdown", self.form.maxRampStepdown)
        for prop, widget in self._leadCheckboxes():
            if getattr(obj, prop) != widget.isChecked():
                setattr(obj, prop, widget.isChecked())
        for prop, widget in self._leadQuantities():
            _qty_commit(obj, prop, widget)

        self.updateToolController(obj, self.form.toolController)
        self.updateCoolant(obj, self.form.coolantController)
        self.updateZigZagAngleEnabled(obj)
        self.updateRampFieldsEnabled(obj)

    def setFields(self, obj):
        self.selectInComboBox(obj.CutMode, self.form.cutMode)
        self.selectInComboBox(obj.ClearingPattern, self.form.clearingPattern)
        self.form.stepOverPercent.setValue(obj.StepOver)
        _qty_set(self.form.radialStockToLeave, obj.ExtraOffset.Value)
        _qty_set(self.form.axialStockToLeave, obj.AxialStockToLeave.Value)
        _qty_set(self.form.zigZagAngle, obj.ZigZagAngle)
        self.form.minTravel.setChecked(obj.MinTravel)
        self.form.useRestMachining.setChecked(obj.UseRestMachining)
        self.form.finishingPasses.setValue(obj.FinishingPasses)
        self.form.finishFeedrate.setValue(obj.FinishFeedrate.Value / self.form.finishFeedScale)
        self.form.useOutline.setChecked(obj.UseOutline)
        self.form.useStartPoint.setChecked(obj.UseStartPoint)
        self.selectInComboBox(obj.RampType, self.form.rampType)
        _qty_set(self.form.rampAngle, obj.RampAngle.Value)
        _qty_set(self.form.helicalRampDiameter, obj.HelicalRampDiameter.Value)
        _qty_set(self.form.minimumRampDiameter, obj.MinimumRampDiameter.Value)
        _qty_set(self.form.maxRampStepdown, obj.MaxRampStepdown.Value)
        for prop, widget in self._leadCheckboxes():
            widget.setChecked(getattr(obj, prop))
        for prop, widget in self._leadQuantities():
            _qty_set(widget, getattr(obj, prop).Value)
        self.updateZigZagAngleEnabled(obj)
        self.updateRampFieldsEnabled(obj)

        self.setupToolController(obj, self.form.toolController)
        self._pruneToolComboSentinels(obj)
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
            self.form.finishingPasses.editingFinished,
            self.form.finishFeedrate.editingFinished,
            self.form.useOutline.clicked,
            self.form.useStartPoint.clicked,
            self.form.toolController.currentIndexChanged,
            self.form.coolantController.currentIndexChanged,
            self.form.rampType.currentIndexChanged,
            self.form.rampAngle.editingFinished,
            self.form.helicalRampDiameter.editingFinished,
            self.form.minimumRampDiameter.editingFinished,
            self.form.maxRampStepdown.editingFinished,
        ] + [
            widget.clicked for _prop, widget in self._leadCheckboxes()
        ] + [
            widget.editingFinished for _prop, widget in self._leadQuantities()
        ]

    def _leadCheckboxes(self):
        """(property name, checkbox) for every Lead-In/Lead-Out bool."""
        form = self.form
        return [
            ("UseLeadIn", form.useLeadIn),
            ("LeadInPerpendicular", form.leadInPerpendicular),
            ("UseLeadOut", form.useLeadOut),
            ("SameAsLeadIn", form.sameAsLeadIn),
            ("LeadOutPerpendicular", form.leadOutPerpendicular),
        ]

    def _leadQuantities(self):
        """(property name, quantity spin box) for every Lead-In/Lead-Out length/angle."""
        form = self.form
        return [
            ("LeadInRadius", form.leadInRadius),
            ("LeadInSweepAngle", form.leadInSweepAngle),
            ("LeadInDistance", form.leadInDistance),
            ("LeadOutDistance", form.leadOutDistance),
            ("LeadOutRadius", form.leadOutRadius),
            ("LeadOutSweepAngle", form.leadOutSweepAngle),
        ]

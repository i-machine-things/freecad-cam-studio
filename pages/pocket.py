"""CAM Studio's own 2D Offset Roughing (pocket) edit pages.

The dialog's shared bars -- Tool (Feed & Speed) and Heights -- and the bar layout are in
pages/common.py; this module adds the pocket's own Passes and Linking bars.
"""

import FreeCAD
from PySide import QtWidgets

import Path.Op.Gui.FeatureExtension as PathFeatureExtensionsGui

from pages.common import (
    BarPage,
    StepoverRow,
    ToolBarPage,
    feed_display_unit,
    qty_commit,
    qty_set,
    quantity_spinbox,
)
from widgets.collapsible import CollapsibleSection

translate = FreeCAD.Qt.translate


class TaskPanelOpPage(ToolBarPage):
    """Tool bar and entry point (pages/common.py), with the pocket's Passes and Linking bars."""

    ICON = ":/icons/CAM_Pocket.svg"

    def opTitle(self):
        return translate("CamStudio_Pocket", "2D Offset Roughing")

    def makeBars(self, obj):
        return [PassesPage(obj, self.features), LinkingPage(obj, self.features)]

    def taskPanelBaseLocationPage(self, obj, features):
        # Same hook stock CAM's Pocket Shape page uses: show pocket Extensions in the
        # Locations slot instead of the generic start-point Base Location page.
        if not hasattr(self, "extensionsPanel"):
            self.extensionsPanel = PathFeatureExtensionsGui.TaskPanelExtensionPage(obj, features)
        return self.extensionsPanel


class PassesPage(BarPage):
    """Passes bar: cutting direction, stepover, stock to leave, finishing passes, plus the
    FreeCAD-only options Fusion has no equivalent for."""

    def __init__(self, obj, features):
        super().__init__(obj, features)
        # FreeCAD's Extensions page looks up the page titled "Operation" that owns the
        # Use outline checkbox; that's this page now.
        self.panelTitle = "Operation"

    def getTitle(self, obj):
        return translate("CamStudio_Pocket", "Passes")

    def getForm(self):
        form = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(form)

        passes_group = CollapsibleSection(translate("CamStudio_Pocket", "Passes"))
        passes_layout = QtWidgets.QFormLayout()
        passes_layout.setRowWrapPolicy(QtWidgets.QFormLayout.WrapLongRows)
        # Fusion's "Sideways Compensation": which side of the path the tool sits on, Left or
        # Right. Backed by FreeCAD's CutMode (Climb/Conventional); the mapping depends on the
        # spindle direction, so the labels are filled in by _fillSidewaysCompensation.
        form.cutMode = QtWidgets.QComboBox()
        # Fusion's "Maximum Stepover" is a distance; shown with FreeCAD's percent on one row.
        self.stepover = StepoverRow(form)
        # Which way the offset rings progress: FreeCAD's StartAt (Center / Edge).
        form.clearingOrder = QtWidgets.QComboBox()
        form.clearingOrder.addItem(translate("CamStudio_Pocket", "Inside out"), "Center")
        form.clearingOrder.addItem(translate("CamStudio_Pocket", "Outside in"), "Edge")
        form.clearingOrder.setToolTip(
            translate(
                "CamStudio_Pocket",
                "Inside out: start in the middle and work out to the walls. Outside in: start "
                "at the walls and work inward. Sideways Compensation stays correct either way.",
            )
        )
        form.radialStockToLeave = quantity_spinbox()
        form.axialStockToLeave = quantity_spinbox()
        form.minTravel = QtWidgets.QCheckBox(
            translate("CamStudio_Pocket", "Minimize travel between cuts")
        )
        form.useRestMachining = QtWidgets.QCheckBox(
            translate("CamStudio_Pocket", "Rest machining (skip already-cleared areas)")
        )
        form.finishingPasses = QtWidgets.QSpinBox()
        form.finishingPasses.setRange(0, 20)
        # Plain spinbox, not quantity_spinbox: Gui::QuantitySpinBox's "unit" property only
        # accepts FreeCAD's own "preferred display unit" for a Quantity type -- for Velocity
        # that's "mm/s" in this app's unit-system preference, not the "mm/min" every CNC/CAM
        # context (including FreeCAD's own ToolController feed fields) actually uses. Forcing
        # "mm/min" directly onto the widget is silently ignored (falls back to mm/s) -- a real
        # 60x unit-confusion risk for a feed rate, not just cosmetic. Converting explicitly in
        # getFields/setFields (FinishFeedrate's own internal unit is mm/s) avoids relying on
        # that widget at all. The display unit still follows the user's unit schema, via
        # feed_display_unit: per minute always, mm or inch to match the other fields.
        feedUnit, form.finishFeedScale, feedDecimals = feed_display_unit()
        form.finishFeedrate = QtWidgets.QDoubleSpinBox()
        form.finishFeedrate.setRange(0, 100000)
        form.finishFeedrate.setDecimals(feedDecimals)
        form.finishFeedrate.setSuffix(" " + feedUnit)
        passes_layout.addRow(translate("CamStudio_Pocket", "Sideways Compensation"), form.cutMode)
        passes_layout.addRow(translate("CamStudio_Pocket", "Maximum Stepover"), self.stepover.layout)
        passes_layout.addRow(translate("CamStudio_Pocket", "Clearing Order"), form.clearingOrder)
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
        options_layout.addRow(form.useOutline)
        options_group.setContentLayout(options_layout)
        layout.addWidget(options_group)

        form.useMultipleDepths = QtWidgets.QCheckBox(translate("CamStudio_Pocket", "Multiple Depths"))
        form.useMultipleDepths.setToolTip(
            translate("CamStudio_Pocket", "Cut in several depth levels. Off: a single pass at the bottom.")
        )
        form.finishingStepdowns = QtWidgets.QSpinBox()
        form.finishingStepdowns.setRange(0, 50)
        form.finishingStepdowns.setToolTip(
            translate("CamStudio_Pocket", "Finishing levels at the bottom, each Finishing Stepdown deep. 0 = none.")
        )
        form.useEvenStepdowns = QtWidgets.QCheckBox(translate("CamStudio_Pocket", "Use Even Stepdowns"))
        form.useEvenStepdowns.setToolTip(
            translate(
                "CamStudio_Pocket",
                "Space the roughing levels evenly, each at most the Maximum Roughing Stepdown, "
                "instead of full steps plus a thinner last one.",
            )
        )
        form.useMultipleDepths.clicked.connect(lambda *_: self._updateDepthEnabled(self.obj))
        form.finishingStepdowns.valueChanged.connect(lambda *_: self._updateDepthEnabled(self.obj))
        # Filled in by addDepthRows once the panel hands over FreeCAD's depth fields.
        form.depthsGroup = CollapsibleSection(translate("CamStudio_Pocket", "Multiple Depths"))
        form.depthsLayout = QtWidgets.QFormLayout()
        form.depthsGroup.setContentLayout(form.depthsLayout)
        form.depthsGroup.hide()
        layout.insertWidget(1, form.depthsGroup)

        layout.addStretch(1)
        return form

    def addDepthRows(self, depthsForm):
        """Fusion's Multiple Depths section. FreeCAD's Step Down / Finish Step Down fields
        (still driven by FreeCAD's Depths page logic, see HeightsBar) appear here under
        Fusion's names, between CAM Studio's own options (ops/pocket.py depthLevels)."""
        f = self.form
        stepDown = getattr(depthsForm, "stepDown", None)
        finishDepth = getattr(depthsForm, "finishDepth", None)
        self.depthWidgets = [w for w in (stepDown, finishDepth) if w is not None and not w.isHidden()]
        f.depthsLayout.addRow(f.useMultipleDepths)
        if stepDown in self.depthWidgets:
            f.depthsLayout.addRow(translate("CamStudio_Pocket", "Maximum Roughing Stepdown"), stepDown)
        f.depthsLayout.addRow(translate("CamStudio_Pocket", "Finishing Stepdowns"), f.finishingStepdowns)
        if finishDepth in self.depthWidgets:
            f.depthsLayout.addRow(translate("CamStudio_Pocket", "Finishing Stepdown"), finishDepth)
        f.depthsLayout.addRow(f.useEvenStepdowns)
        self.finishDepthWidget = finishDepth
        f.depthsGroup.show()
        self._updateDepthEnabled(self.obj)

    def _updateDepthEnabled(self, obj):
        f = self.form
        multiple = f.useMultipleDepths.isChecked()
        for w in getattr(self, "depthWidgets", []):
            w.setEnabled(multiple)
        f.finishingStepdowns.setEnabled(multiple)
        f.useEvenStepdowns.setEnabled(multiple)
        fd = getattr(self, "finishDepthWidget", None)
        if fd is not None:
            fd.setEnabled(multiple and f.finishingStepdowns.value() > 0)

    def initBar(self, obj):
        self.setIcon(":/icons/CAM_Pocket.svg")
        self._fillSidewaysCompensation(obj)

    def updateData(self, obj, prop):
        # Tool chosen on the Tool bar: its diameter sets the stepover distance, its spindle
        # direction the Left/Right labels.
        if prop in ("ToolController", "StepOver"):
            self.stepover.show(obj)
        if prop == "ToolController":
            self._fillSidewaysCompensation(obj)

    def _spindleClockwise(self, obj):
        tc = getattr(obj, "ToolController", None)
        try:
            return tc.Tool.Proxy.get_spindle_direction().value != "M4"
        except Exception:
            return getattr(tc, "SpindleDir", "Forward") != "Reverse"

    def _fillSidewaysCompensation(self, obj):
        """Left/Right items for FreeCAD's Climb/Conventional. With a clockwise (M3) spindle,
        keeping the tool to the left of the material-side path (G41-style) is climb milling;
        a reversed spindle swaps them."""
        cw = self._spindleClockwise(obj)
        combo = self.form.cutMode
        current = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        items = [
            (translate("CamStudio_Pocket", "Left (climb)") if cw else translate("CamStudio_Pocket", "Left (conventional)"),
             "Climb" if cw else "Conventional"),
            (translate("CamStudio_Pocket", "Right (conventional)") if cw else translate("CamStudio_Pocket", "Right (climb)"),
             "Conventional" if cw else "Climb"),
        ]
        for text, data in items:
            combo.addItem(text, data)
        index = combo.findData(current if current else obj.CutMode)
        combo.setCurrentIndex(max(0, index))
        combo.blockSignals(False)

    def getFields(self, obj):
        if obj.CutMode != str(self.form.cutMode.currentData()):
            obj.CutMode = str(self.form.cutMode.currentData())
        if obj.StartAt != str(self.form.clearingOrder.currentData()):
            obj.StartAt = str(self.form.clearingOrder.currentData())
        self.stepover.commit(obj)
        if hasattr(obj, "UseMultipleDepths"):
            for prop, widget in (("UseMultipleDepths", self.form.useMultipleDepths),
                                 ("UseEvenStepdowns", self.form.useEvenStepdowns)):
                if getattr(obj, prop) != widget.isChecked():
                    setattr(obj, prop, widget.isChecked())
            if obj.FinishingStepdowns != self.form.finishingStepdowns.value():
                obj.FinishingStepdowns = self.form.finishingStepdowns.value()
        qty_commit(obj, "ExtraOffset", self.form.radialStockToLeave)
        qty_commit(obj, "AxialStockToLeave", self.form.axialStockToLeave)
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

    def setFields(self, obj):
        self._fillSidewaysCompensation(obj)
        self.form.cutMode.setCurrentIndex(max(0, self.form.cutMode.findData(obj.CutMode)))
        self.form.clearingOrder.setCurrentIndex(max(0, self.form.clearingOrder.findData(obj.StartAt)))
        self.stepover.show(obj)
        if hasattr(obj, "UseMultipleDepths"):
            self.form.useMultipleDepths.setChecked(obj.UseMultipleDepths)
            self.form.useEvenStepdowns.setChecked(obj.UseEvenStepdowns)
            self.form.finishingStepdowns.setValue(obj.FinishingStepdowns)
            self._updateDepthEnabled(obj)
        qty_set(self.form.radialStockToLeave, obj.ExtraOffset.Value)
        qty_set(self.form.axialStockToLeave, obj.AxialStockToLeave.Value)
        self.form.minTravel.setChecked(obj.MinTravel)
        self.form.useRestMachining.setChecked(obj.UseRestMachining)
        self.form.finishingPasses.setValue(obj.FinishingPasses)
        self.form.finishFeedrate.setValue(obj.FinishFeedrate.Value / self.form.finishFeedScale)
        self.form.useOutline.setChecked(obj.UseOutline)

    def getSignalsForUpdate(self, obj):
        return self.stepover.signals() + [
            self.form.cutMode.currentIndexChanged,
            self.form.clearingOrder.currentIndexChanged,
            self.form.useMultipleDepths.clicked,
            self.form.useEvenStepdowns.clicked,
            self.form.finishingStepdowns.editingFinished,
            self.form.radialStockToLeave.editingFinished,
            self.form.axialStockToLeave.editingFinished,
            self.form.minTravel.clicked,
            self.form.useRestMachining.clicked,
            self.form.finishingPasses.editingFinished,
            self.form.finishFeedrate.editingFinished,
            self.form.useOutline.clicked,
        ]


class LinkingPage(BarPage):
    """Linking bar: Linking, Leads & Transitions, then Ramp -- Fusion's Linking tab order."""

    def getTitle(self, obj):
        return translate("CamStudio_Pocket", "Linking")

    def getForm(self):
        form = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(form)

        # Fusion's Linking tab opens with its own "Linking" section (how the tool moves
        # between passes). Only Keep Tool Down is here so far: it's FreeCAD's KeepToolDown,
        # which stays down for links up to one tool diameter. Fusion's Maximum Stay-Down
        # Distance needs those links checked against uncut material first -- see ROADMAP.
        link_group = CollapsibleSection(translate("CamStudio_Pocket", "Linking"))
        link_layout = QtWidgets.QFormLayout()
        form.keepToolDown = QtWidgets.QCheckBox(translate("CamStudio_Pocket", "Keep Tool Down"))
        form.keepToolDown.setToolTip(
            translate(
                "CamStudio_Pocket",
                "Stay at depth instead of retracting when the next pass starts within one "
                "tool diameter.",
            )
        )
        link_layout.addRow(form.keepToolDown)
        link_group.setContentLayout(link_layout)
        layout.addWidget(link_group)

        leads_group = CollapsibleSection(translate("CamStudio_Pocket", "Leads && Transitions"))  # && = literal & in a QToolButton
        leads_layout = QtWidgets.QFormLayout()
        leads_layout.setRowWrapPolicy(QtWidgets.QFormLayout.WrapLongRows)
        # Lead-In and Lead-Out: enabled separately, each an arc tangent to the cut (radius +
        # sweep) with an optional straight leg outside it -- see ops/pocket.py's
        # _applyLeadInOut. Row order follows Fusion's Linking tab.
        form.useLeadIn = QtWidgets.QCheckBox(translate("CamStudio_Pocket", "Lead-In (Entry)"))
        form.leadInRadius = quantity_spinbox()
        form.leadInSweepAngle = quantity_spinbox(unit="deg")
        form.leadInDistance = quantity_spinbox()
        form.leadInPerpendicular = QtWidgets.QCheckBox(
            translate("CamStudio_Pocket", "Perpendicular Lead-In")
        )
        form.useLeadOut = QtWidgets.QCheckBox(translate("CamStudio_Pocket", "Lead-Out (Exit)"))
        form.sameAsLeadIn = QtWidgets.QCheckBox(
            translate("CamStudio_Pocket", "Same as Lead-In")
        )
        form.leadOutDistance = quantity_spinbox()
        form.leadOutRadius = quantity_spinbox()
        form.leadOutSweepAngle = quantity_spinbox(unit="deg")
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
        leads_layout.addRow(form.useLeadIn)
        leads_layout.addRow(
            translate("CamStudio_Pocket", "Horizontal Lead-In Radius"), form.leadInRadius
        )
        leads_layout.addRow(
            translate("CamStudio_Pocket", "Lead-In Sweep Angle"), form.leadInSweepAngle
        )
        leads_layout.addRow(
            translate("CamStudio_Pocket", "Linear Lead-In Distance"), form.leadInDistance
        )
        leads_layout.addRow(form.leadInPerpendicular)
        leads_layout.addRow(form.useLeadOut)
        leads_layout.addRow(form.sameAsLeadIn)
        leads_layout.addRow(
            translate("CamStudio_Pocket", "Linear Lead-Out Distance"), form.leadOutDistance
        )
        leads_layout.addRow(
            translate("CamStudio_Pocket", "Horizontal Lead-Out Radius"), form.leadOutRadius
        )
        leads_layout.addRow(
            translate("CamStudio_Pocket", "Lead-Out Sweep Angle"), form.leadOutSweepAngle
        )
        leads_layout.addRow(form.leadOutPerpendicular)
        leads_group.setContentLayout(leads_layout)
        layout.addWidget(leads_group)

        ramp_group = CollapsibleSection(translate("CamStudio_Pocket", "Ramp"))
        ramp_layout = QtWidgets.QFormLayout()
        # The task panel is narrow by default; long labels would otherwise force the form
        # wider than it and clip the fields behind a horizontal scroll bar.
        ramp_layout.setRowWrapPolicy(QtWidgets.QFormLayout.WrapLongRows)
        form.rampType = QtWidgets.QComboBox()
        form.rampType.addItem(translate("CamStudio_Pocket", "Plunge"), "Plunge")
        form.rampType.addItem(translate("CamStudio_Pocket", "Plunge Outside Stock"), "Plunge Outside Stock")
        form.rampType.addItem(translate("CamStudio_Pocket", "Helix"), "Helix")
        form.rampAngle = quantity_spinbox(unit="deg")
        form.helicalRampDiameter = quantity_spinbox()
        form.minimumRampDiameter = quantity_spinbox()
        form.maxRampStepdown = quantity_spinbox()
        form.rampClearanceHeight = quantity_spinbox()
        form.outsidePlungeDistance = quantity_spinbox()
        form.outsidePlungeDistance.setToolTip(
            translate(
                "CamStudio_Pocket",
                "Plunge Outside Stock: how far outside each area's edge the tool center plunges. "
                "0 = 1.25 x tool diameter.",
            )
        )
        ramp_layout.addRow(translate("CamStudio_Pocket", "Ramp Type"), form.rampType)
        ramp_layout.addRow(translate("CamStudio_Pocket", "Ramp Angle"), form.rampAngle)
        ramp_layout.addRow(
            translate("CamStudio_Pocket", "Helical Ramp Diameter (0 = 1 x tool \u00d8)"),
            form.helicalRampDiameter,
        )
        ramp_layout.addRow(
            translate("CamStudio_Pocket", "Minimum Ramp Diameter"), form.minimumRampDiameter
        )
        ramp_layout.addRow(
            translate("CamStudio_Pocket", "Maximum Ramp Stepdown (0 = unconstrained)"),
            form.maxRampStepdown,
        )
        ramp_layout.addRow(
            translate("CamStudio_Pocket", "Ramp Clearance Height"), form.rampClearanceHeight
        )
        ramp_layout.addRow(
            translate("CamStudio_Pocket", "Plunge Distance (0 = 1.25 x tool \u00d8)"),
            form.outsidePlungeDistance,
        )
        ramp_group.setContentLayout(ramp_layout)
        layout.addWidget(ramp_group)

        # Fusion's Positions: where each pass is entered (ops/pocket.py
        # _applyPreferredEntries restarts each entered ring nearest these points).
        positions_group = CollapsibleSection(translate("CamStudio_Pocket", "Positions"))
        positions_layout = QtWidgets.QFormLayout()
        positions_layout.setRowWrapPolicy(QtWidgets.QFormLayout.WrapLongRows)
        form.pickPreferred = QtWidgets.QPushButton(translate("CamStudio_Pocket", "Select"))
        form.pickPreferred.setToolTip(
            translate(
                "CamStudio_Pocket",
                "Click a point in the 3D view; each pass is entered at its point nearest the "
                "closest preferred position. Select again to add more.",
            )
        )
        form.clearPreferred = QtWidgets.QPushButton(translate("CamStudio_Pocket", "Clear"))
        buttons = QtWidgets.QHBoxLayout()
        buttons.addWidget(form.pickPreferred)
        buttons.addWidget(form.clearPreferred)
        positions_layout.addRow(
            translate("CamStudio_Pocket", "Preferred Lead-In Positions"), buttons
        )
        form.preferredInfo = QtWidgets.QLabel()
        form.preferredInfo.setWordWrap(True)
        positions_layout.addRow(form.preferredInfo)
        positions_group.setContentLayout(positions_layout)
        layout.addWidget(positions_group)
        form.pickPreferred.clicked.connect(self._pickPreferred)
        form.clearPreferred.clicked.connect(self._clearPreferred)
        layout.addStretch(1)
        return form

    def initBar(self, obj):
        self.setIcon(":/icons/CAM_Pocket.svg")

    def updateRampFieldsEnabled(self, obj):
        isHelix = obj.RampType == "Helix"
        self.form.rampAngle.setEnabled(isHelix)
        self.form.helicalRampDiameter.setEnabled(isHelix)
        self.form.minimumRampDiameter.setEnabled(isHelix)
        self.form.maxRampStepdown.setEnabled(isHelix)
        self.form.rampClearanceHeight.setEnabled(isHelix)
        self.form.outsidePlungeDistance.setEnabled(obj.RampType == "Plunge Outside Stock")
        self.updateLeadInOutFieldsEnabled(obj)

    def updateLeadInOutFieldsEnabled(self, obj):
        form = self.form
        inActive = bool(obj.UseLeadIn)
        for widget in (
            form.leadInRadius,
            form.leadInSweepAngle,
            form.leadInDistance,
            form.leadInPerpendicular,
        ):
            widget.setEnabled(inActive)
        outActive = bool(obj.UseLeadOut)
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
        if obj.RampType != str(self.form.rampType.currentData()):
            obj.RampType = str(self.form.rampType.currentData())
        qty_commit(obj, "RampAngle", self.form.rampAngle)
        qty_commit(obj, "HelicalRampDiameter", self.form.helicalRampDiameter)
        qty_commit(obj, "MinimumRampDiameter", self.form.minimumRampDiameter)
        qty_commit(obj, "MaxRampStepdown", self.form.maxRampStepdown)
        qty_commit(obj, "RampClearanceHeight", self.form.rampClearanceHeight)
        qty_commit(obj, "OutsidePlungeDistance", self.form.outsidePlungeDistance)
        if hasattr(obj, "PreferredEntryPoints"):
            pts = list(getattr(self, "preferredPoints", []))
            current = [(round(v.x, 9), round(v.y, 9)) for v in obj.PreferredEntryPoints]
            if current != [(round(v.x, 9), round(v.y, 9)) for v in pts]:
                obj.PreferredEntryPoints = pts
        if obj.KeepToolDown != self.form.keepToolDown.isChecked():
            obj.KeepToolDown = self.form.keepToolDown.isChecked()
        for prop, widget in self._leadCheckboxes():
            if getattr(obj, prop) != widget.isChecked():
                setattr(obj, prop, widget.isChecked())
        for prop, widget in self._leadQuantities():
            qty_commit(obj, prop, widget)
        self.updateRampFieldsEnabled(obj)

    def setFields(self, obj):
        self.selectInComboBox(obj.RampType, self.form.rampType)
        qty_set(self.form.rampAngle, obj.RampAngle.Value)
        qty_set(self.form.helicalRampDiameter, obj.HelicalRampDiameter.Value)
        qty_set(self.form.minimumRampDiameter, obj.MinimumRampDiameter.Value)
        qty_set(self.form.maxRampStepdown, obj.MaxRampStepdown.Value)
        qty_set(self.form.rampClearanceHeight, obj.RampClearanceHeight.Value)
        qty_set(self.form.outsidePlungeDistance, obj.OutsidePlungeDistance.Value)
        if hasattr(obj, "PreferredEntryPoints"):
            self.preferredPoints = list(obj.PreferredEntryPoints)
            self._showPreferred()
        self.form.keepToolDown.setChecked(obj.KeepToolDown)
        for prop, widget in self._leadCheckboxes():
            widget.setChecked(getattr(obj, prop))
        for prop, widget in self._leadQuantities():
            qty_set(widget, getattr(obj, prop).Value)
        self.updateRampFieldsEnabled(obj)

    # -- Preferred Lead-In Positions ----------------------------------------------------------
    def _showPreferred(self):
        pts = getattr(self, "preferredPoints", [])
        if not pts:
            self.form.preferredInfo.setText(
                translate("CamStudio_Pocket", "None: each pass starts where FreeCAD starts it.")
            )
            return
        scale = 25.4 if FreeCAD.Units.Quantity(1.0, FreeCAD.Units.Length).getUserPreferred()[2] == "in" else 1.0
        unit = "in" if scale != 1.0 else "mm"
        self.form.preferredInfo.setText(
            "; ".join("(%.3f, %.3f) %s" % (p.x / scale, p.y / scale, unit) for p in pts)
        )

    def _pickPreferred(self):
        """Wait for one left-click in the 3D view and add the point under it (on the part if
        the click hits it, else in the view plane). Uses the view's own mouse callback --
        Draft's Snapper.getPoint opens its own task dialog, which destroys this one."""
        import FreeCADGui

        view = FreeCADGui.ActiveDocument.ActiveView if FreeCADGui.ActiveDocument else None
        if view is None or getattr(self, "_pickCallback", None) is not None:
            return

        def onClick(info):
            if info.get("Button") != "BUTTON1" or info.get("State") != "DOWN":
                return
            pos = info.get("Position")
            hit = view.getObjectInfo(pos)
            if hit:
                point = FreeCAD.Vector(hit["x"], hit["y"], hit["z"])
            else:
                point = view.getPoint(*pos)
            view.removeEventCallback("SoMouseButtonEvent", self._pickCallback)
            self._pickCallback = None
            self._addPreferred(point)

        self._pickCallback = view.addEventCallback("SoMouseButtonEvent", onClick)
        self.form.preferredInfo.setText(
            translate("CamStudio_Pocket", "Click a point in the 3D view...")
        )

    def cleanupPage(self, obj):
        # Don't leave a pick waiting after the dialog closes.
        import FreeCADGui

        if getattr(self, "_pickCallback", None) is not None and FreeCADGui.ActiveDocument:
            try:
                FreeCADGui.ActiveDocument.ActiveView.removeEventCallback(
                    "SoMouseButtonEvent", self._pickCallback
                )
            except Exception:
                pass
            self._pickCallback = None

    def _addPreferred(self, point, _info=None):
        if point is None:
            return
        self.preferredPoints = list(getattr(self, "preferredPoints", [])) + [
            FreeCAD.Vector(point.x, point.y, 0)
        ]
        self._showPreferred()
        self.pageGetFields()

    def _clearPreferred(self):
        self.preferredPoints = []
        self._showPreferred()
        self.pageGetFields()

    def getSignalsForUpdate(self, obj):
        return [
            self.form.rampType.currentIndexChanged,
            self.form.rampAngle.editingFinished,
            self.form.helicalRampDiameter.editingFinished,
            self.form.minimumRampDiameter.editingFinished,
            self.form.maxRampStepdown.editingFinished,
            self.form.rampClearanceHeight.editingFinished,
            self.form.outsidePlungeDistance.editingFinished,
            self.form.keepToolDown.clicked,
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

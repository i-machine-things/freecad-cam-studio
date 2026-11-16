"""CAM Studio's own 2D Offset Roughing (pocket) edit pages.

FreeCAD's task panel stacks its pages as collapsible bars (Base Geometry,
Extensions, Depths, Heights, Operation). Fusion splits the same dialog into
tabs (Tool, Multi-axis, Geometry, Heights, Passes, Linking). We keep
FreeCAD's bars and line them up with Fusion's tabs: the single "Operation"
bar becomes three bars -- Tool, Passes and Linking -- and the bars are
ordered Tool, Base Geometry, Extensions, Heights, Depths,
Passes, Linking. Multi-axis is left out until it has fields.

The upstream TaskPanel only knows about one op page (TaskPanelOpPage, the
Tool bar here). That page adds the Passes and Linking pages to the panel
and reorders the bars from its own initPage -- see _attachBars. Base
geometry, Heights and Depths stay the shared upstream pages.

No FreeCAD .ui resource file is loaded -- this form is built directly in
Python so CAM Studio owns the full layout, not just the data wiring.
"""

import FreeCAD
import FreeCADGui as Gui
from PySide import QtWidgets
from PySide.QtCore import Qt

import Path.Op.Gui.Base as PathOpGui
import Path.Op.Gui.FeatureExtension as PathFeatureExtensionsGui
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


class _BarPage(PathOpGui.TaskPanelPage):
    """A page for one bar of the dialog. Guards initPage so it runs once: the Tool page
    initializes these itself, and the upstream TaskPanel loop may visit them again."""

    _initialized = False

    def initPage(self, obj):
        if self._initialized:
            return
        self._initialized = True
        self.initBar(obj)

    def initBar(self, obj):
        pass


class TaskPanelOpPage(PathOpGui.TaskPanelPage):
    """Tool bar, and the entry point the upstream TaskPanel knows about. Adds the Passes and
    Linking bars to the panel and orders all bars like Fusion's tabs (see _attachBars)."""

    def getTitle(self, obj):
        # The TaskPanel asks for the title twice: once for the panel heading, then -- after
        # renaming this page "Operation" -- for this page's own bar.
        if getattr(self, "title", None) == "Operation":
            return translate("CamStudio_Pocket", "Tool")
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

        layout.addStretch(1)
        return form

    def initPage(self, obj):
        self.setIcon(":/icons/CAM_Pocket.svg")
        self._attachBars(obj)

    def _attachBars(self, obj):
        """Add the Passes and Linking pages to the panel and put the bars in Fusion's tab
        order. Runs while the upstream TaskPanel is initializing its pages; this page is the
        last one it built, so every page already in the list has been initialized. The new
        pages are initialized here directly (and ignore a second initPage), so this works
        whether or not the upstream loop goes on to visit them."""
        parent = self.parent
        pages = getattr(parent, "featurePages", None)
        if pages is None or getattr(self, "bars", None):
            return
        self.bars = [PassesPage(obj, self.features), LinkingPage(obj, self.features)]
        for bar in self.bars:
            bar.parent = parent
            bar.initPage(obj)
            bar.onDirtyChanged(parent.pageDirtyChanged)

        def rank(page):
            # Heights before Depths, as Fusion's Heights tab lists clearance/retract first.
            if isinstance(page, PathOpGui.TaskPanelHeightsPage):
                return 1
            if isinstance(page, PathOpGui.TaskPanelDepthsPage):
                return 2
            return 0

        upstream = sorted((p for p in pages if p is not self), key=rank)
        pages[:] = [self] + upstream + self.bars

    def taskPanelBaseLocationPage(self, obj, features):
        # Same hook stock CAM's Pocket Shape page uses: show pocket Extensions in the
        # Locations slot instead of the generic start-point Base Location page.
        if not hasattr(self, "extensionsPanel"):
            self.extensionsPanel = PathFeatureExtensionsGui.TaskPanelExtensionPage(obj, features)
        return self.extensionsPanel

    def registerSignalHandlers(self, obj):
        # Upstream opens the last bar; Fusion opens on the Tool tab.
        toolbox = getattr(self.parent, "form", None)
        if isinstance(toolbox, QtWidgets.QToolBox):
            toolbox.setCurrentIndex(0)

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

    def getFields(self, obj):
        self.updateToolController(obj, self.form.toolController)
        self.updateCoolant(obj, self.form.coolantController)

    def setFields(self, obj):
        self.setupToolController(obj, self.form.toolController)
        self._pruneToolComboSentinels(obj)
        self.setupCoolant(obj, self.form.coolantController)

    def getSignalsForUpdate(self, obj):
        return [
            self.form.toolController.currentIndexChanged,
            self.form.coolantController.currentIndexChanged,
        ]


class PassesPage(_BarPage):
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
        form.useStartPoint = QtWidgets.QCheckBox(
            translate("CamStudio_Pocket", "Use custom start point")
        )
        options_layout.addRow(form.useOutline)
        options_layout.addRow(form.useStartPoint)
        options_group.setContentLayout(options_layout)
        layout.addWidget(options_group)

        layout.addStretch(1)
        return form

    def initBar(self, obj):
        self.setIcon(":/icons/CAM_Pocket.svg")
        enumTups = PathPocketShape.ObjectPocket.pocketPropertyEnumerations(dataType="raw")
        self.populateCombobox(
            self.form,
            enumTups,
            [("cutMode", "CutMode")],
        )

    def getFields(self, obj):
        if obj.CutMode != str(self.form.cutMode.currentData()):
            obj.CutMode = str(self.form.cutMode.currentData())
        if obj.StepOver != self.form.stepOverPercent.value():
            obj.StepOver = self.form.stepOverPercent.value()
        _qty_commit(obj, "ExtraOffset", self.form.radialStockToLeave)
        _qty_commit(obj, "AxialStockToLeave", self.form.axialStockToLeave)
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

    def setFields(self, obj):
        self.selectInComboBox(obj.CutMode, self.form.cutMode)
        self.form.stepOverPercent.setValue(obj.StepOver)
        _qty_set(self.form.radialStockToLeave, obj.ExtraOffset.Value)
        _qty_set(self.form.axialStockToLeave, obj.AxialStockToLeave.Value)
        self.form.minTravel.setChecked(obj.MinTravel)
        self.form.useRestMachining.setChecked(obj.UseRestMachining)
        self.form.finishingPasses.setValue(obj.FinishingPasses)
        self.form.finishFeedrate.setValue(obj.FinishFeedrate.Value / self.form.finishFeedScale)
        self.form.useOutline.setChecked(obj.UseOutline)
        self.form.useStartPoint.setChecked(obj.UseStartPoint)

    def getSignalsForUpdate(self, obj):
        return [
            self.form.cutMode.currentIndexChanged,
            self.form.stepOverPercent.editingFinished,
            self.form.radialStockToLeave.editingFinished,
            self.form.axialStockToLeave.editingFinished,
            self.form.minTravel.clicked,
            self.form.useRestMachining.clicked,
            self.form.finishingPasses.editingFinished,
            self.form.finishFeedrate.editingFinished,
            self.form.useOutline.clicked,
            self.form.useStartPoint.clicked,
        ]


class LinkingPage(_BarPage):
    """Linking bar: Leads & Transitions, then Ramp -- Fusion's Linking tab order."""

    def getTitle(self, obj):
        return translate("CamStudio_Pocket", "Linking")

    def getForm(self):
        form = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(form)

        leads_group = CollapsibleSection(translate("CamStudio_Pocket", "Leads && Transitions"))  # && = literal & in a QToolButton
        leads_layout = QtWidgets.QFormLayout()
        leads_layout.setRowWrapPolicy(QtWidgets.QFormLayout.WrapLongRows)
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
        form.rampType.addItem(translate("CamStudio_Pocket", "Helix"), "Helix")
        form.rampAngle = _quantity_spinbox(unit="deg")
        form.helicalRampDiameter = _quantity_spinbox()
        form.minimumRampDiameter = _quantity_spinbox()
        form.maxRampStepdown = _quantity_spinbox()
        ramp_layout.addRow(translate("CamStudio_Pocket", "Ramp Type"), form.rampType)
        ramp_layout.addRow(translate("CamStudio_Pocket", "Ramp Angle"), form.rampAngle)
        ramp_layout.addRow(
            translate("CamStudio_Pocket", "Helical Ramp Diameter (0 = auto)"),
            form.helicalRampDiameter,
        )
        ramp_layout.addRow(
            translate("CamStudio_Pocket", "Minimum Ramp Diameter"), form.minimumRampDiameter
        )
        ramp_layout.addRow(
            translate("CamStudio_Pocket", "Maximum Ramp Stepdown (0 = unconstrained)"),
            form.maxRampStepdown,
        )
        ramp_group.setContentLayout(ramp_layout)
        layout.addWidget(ramp_group)
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
        self.updateRampFieldsEnabled(obj)

    def setFields(self, obj):
        self.selectInComboBox(obj.RampType, self.form.rampType)
        _qty_set(self.form.rampAngle, obj.RampAngle.Value)
        _qty_set(self.form.helicalRampDiameter, obj.HelicalRampDiameter.Value)
        _qty_set(self.form.minimumRampDiameter, obj.MinimumRampDiameter.Value)
        _qty_set(self.form.maxRampStepdown, obj.MaxRampStepdown.Value)
        for prop, widget in self._leadCheckboxes():
            widget.setChecked(getattr(obj, prop))
        for prop, widget in self._leadQuantities():
            _qty_set(widget, getattr(obj, prop).Value)
        self.updateRampFieldsEnabled(obj)

    def getSignalsForUpdate(self, obj):
        return [
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

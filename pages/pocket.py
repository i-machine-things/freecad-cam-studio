"""CAM Studio's own 2D Offset Roughing (pocket) edit pages.

FreeCAD's task panel stacks its pages as collapsible bars (Base Geometry,
Extensions, Depths, Heights, Operation). Fusion splits the same dialog into
tabs (Tool, Multi-axis, Geometry, Heights, Passes, Linking). We keep
FreeCAD's bars and line them up with Fusion's tabs: the single "Operation"
bar becomes three bars -- Tool, Passes and Linking -- and the bars are
ordered Tool, Base Geometry, Extensions, Heights, Passes, Linking, with
FreeCAD's Heights and Depths pages folded into one Heights bar (HeightsBar). Multi-axis is left out until it has fields.

The upstream TaskPanel only knows about one op page (TaskPanelOpPage, the
Tool bar here). That page adds the Passes and Linking pages to the panel
and reorders the bars from its own initPage -- see _attachBars. Base
geometry, Heights and Depths stay the shared upstream pages.

No FreeCAD .ui resource file is loaded -- this form is built directly in
Python so CAM Studio owns the full layout, not just the data wiring.
"""

import math

import FreeCAD
import FreeCADGui as Gui
from PySide import QtWidgets
from PySide.QtCore import Qt

import Path.Base.Gui.Util as PathGuiUtil
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


def _length_display_unit():
    """(unit label, mm per display unit, decimals) for small lengths such as feed per tooth,
    following the user's unit schema."""
    lengthUnit = FreeCAD.Units.Quantity(1.0, FreeCAD.Units.Length).getUserPreferred()[2]
    if lengthUnit in ("in", "ft", "thou", "yd", "mi"):
        return "in", 25.4, 4
    return "mm", 1.0, 3


def _rate_box(suffix, decimals, maximum=1e7):
    box = QtWidgets.QDoubleSpinBox()
    box.setRange(0, maximum)
    box.setDecimals(decimals)
    box.setSuffix(" " + suffix)
    return box


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
        tool_group.setContentLayout(tool_layout)
        layout.addWidget(tool_group)
        form.selectToolButton.clicked.connect(self._onSelectTool)

        # Feed & Speed, per operation (Fusion's Tool tab). Values live on the op (see
        # ops/pocket.py loadFeedsFromTool); picking another tool reloads them from it.
        # Surface Speed, Feed per Tooth and Plunge Feed per Revolution are derived: editing
        # one recalculates its partner field instead of being stored.
        feedUnit, form.feedScale, feedDecimals = _feed_display_unit()
        lenUnit, form.lenScale, lenDecimals = _length_display_unit()
        imperial = lenUnit == "in"
        form.surfaceUnit = "ft/min" if imperial else "m/min"
        form.surfaceScale = 304.8 if imperial else 1000.0  # mm/min per display unit
        fs_group = CollapsibleSection(translate("CamStudio_Pocket", "Feed && Speed"))
        fs_layout = QtWidgets.QFormLayout()
        fs_layout.setRowWrapPolicy(QtWidgets.QFormLayout.WrapLongRows)
        form.spindleSpeed = _rate_box("rpm", 0, 200000)
        form.surfaceSpeed = _rate_box(form.surfaceUnit, 2)
        form.rampSpindleSpeed = _rate_box("rpm", 0, 200000)
        form.cuttingFeedrate = _rate_box(feedUnit, feedDecimals)
        form.feedPerTooth = _rate_box(lenUnit, lenDecimals, 1000)
        form.leadInFeedrate = _rate_box(feedUnit, feedDecimals)
        form.leadOutFeedrate = _rate_box(feedUnit, feedDecimals)
        form.rampFeedrate = _rate_box(feedUnit, feedDecimals)
        form.plungeFeedrate = _rate_box(feedUnit, feedDecimals)
        form.plungeFeedPerRev = _rate_box(lenUnit, lenDecimals, 1000)
        form.chipThinning = QtWidgets.QCheckBox(translate("CamStudio_Pocket", "Chip Thinning"))
        form.chipThinning.setToolTip(
            translate(
                "CamStudio_Pocket",
                "With a stepover under half the tool diameter, chips come out thinner than the "
                "feed per tooth. This raises the cutting feed to bring them back to the "
                "chipload. Engagement is higher in corners and on the first, full-width cut.",
            )
        )
        form.chipThinningInfo = QtWidgets.QLabel()
        form.chipThinningInfo.setWordWrap(True)
        for label, widget in (
            ("Spindle Speed", form.spindleSpeed),
            ("Surface Speed", form.surfaceSpeed),
            ("Ramp Spindle Speed", form.rampSpindleSpeed),
            ("Cutting Feedrate", form.cuttingFeedrate),
            ("Feed per Tooth", form.feedPerTooth),
            (None, form.chipThinning),
            (None, form.chipThinningInfo),
            ("Lead-In Feedrate", form.leadInFeedrate),
            ("Lead-Out Feedrate", form.leadOutFeedrate),
            ("Ramp Feedrate", form.rampFeedrate),
            ("Plunge Feedrate", form.plungeFeedrate),
            ("Plunge Feed per Revolution", form.plungeFeedPerRev),
            ("Coolant", form.coolantController),
        ):
            if label is None:
                fs_layout.addRow(widget)
            else:
                fs_layout.addRow(translate("CamStudio_Pocket", label), widget)
        # Re-apply the defaults for the current tool and stock material (Fusion fills an
        # operation from the tool preset the same way when the tool is picked).
        form.resetFeeds = QtWidgets.QPushButton(translate("CamStudio_Pocket", "Reset to Defaults"))
        form.resetFeeds.setToolTip(
            translate(
                "CamStudio_Pocket",
                "Replace this operation's speeds and feeds with the defaults for its tool and "
                "the setup's stock material",
            )
        )
        form.resetFeeds.clicked.connect(self._onResetFeeds)
        form.feedSource = QtWidgets.QLabel()
        form.feedSource.setWordWrap(True)
        fs_layout.addRow(form.resetFeeds)
        fs_layout.addRow(form.feedSource)
        form.chipThinning.clicked.connect(self._refreshDerived)
        fs_group.setContentLayout(fs_layout)
        layout.addWidget(fs_group)
        # Keep each derived field and its partner in step as either is edited.
        form.spindleSpeed.editingFinished.connect(self._refreshDerived)
        form.cuttingFeedrate.editingFinished.connect(self._refreshDerived)
        form.plungeFeedrate.editingFinished.connect(self._refreshDerived)
        form.surfaceSpeed.editingFinished.connect(self._onSurfaceSpeedEdited)
        form.feedPerTooth.editingFinished.connect(self._onFeedPerToothEdited)
        form.plungeFeedPerRev.editingFinished.connect(self._onPlungePerRevEdited)

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
        passes = PassesPage(obj, self.features)
        self.bars = [passes, LinkingPage(obj, self.features)]
        for bar in self.bars:
            bar.parent = parent
            bar.initPage(obj)
            bar.onDirtyChanged(parent.pageDirtyChanged)

        # Fusion has one Heights tab (clearance, retract, top, bottom) and keeps the
        # stepdowns under Passes. FreeCAD splits these over a Heights and a Depths page.
        # Fold both into one Heights bar that reuses their (expression-aware) fields and
        # logic, and move the stepdown fields to the Passes bar.
        heights = next((p for p in pages if isinstance(p, PathOpGui.TaskPanelHeightsPage)), None)
        depths = next((p for p in pages if isinstance(p, PathOpGui.TaskPanelDepthsPage)), None)
        upstream = [p for p in pages if p is not self and p is not heights and p is not depths]
        if heights is not None and depths is not None:
            heightsBar = HeightsBar(obj, self.features, heights, depths)
            heightsBar.parent = parent
            heightsBar.onDirtyChanged(parent.pageDirtyChanged)
            passes.addDepthRows(depths.form)
            upstream.append(heightsBar)
        else:
            upstream += [p for p in (heights, depths) if p is not None]
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

    # -- Feed & Speed ----------------------------------------------------------------
    def _feedFields(self):
        """(property, spin box) for the op's own speed-type feed properties (mm/s)."""
        f = self.form
        return [
            ("CuttingFeedrate", f.cuttingFeedrate),
            ("LeadInFeedrate", f.leadInFeedrate),
            ("LeadOutFeedrate", f.leadOutFeedrate),
            ("RampFeedrate", f.rampFeedrate),
            ("PlungeFeedrate", f.plungeFeedrate),
        ]

    def _toolGeometry(self):
        tc = getattr(self.obj, "ToolController", None)
        tool = tc.Tool if tc is not None else None
        diameter = tool.Diameter.Value if tool is not None else 0.0
        flutes = int(getattr(tool, "Flutes", 0) or 0) if tool is not None else 0
        return diameter, flutes

    def _setFeedFields(self, obj):
        f = self.form
        f.spindleSpeed.setValue(obj.SpindleSpeed)
        f.rampSpindleSpeed.setValue(obj.RampSpindleSpeed)
        for prop, box in self._feedFields():
            box.setValue(getattr(obj, prop).Value / f.feedScale)
            box.setProperty("camStudioLoaded", box.value())
        f.spindleSpeed.setProperty("camStudioLoaded", f.spindleSpeed.value())
        f.rampSpindleSpeed.setProperty("camStudioLoaded", f.rampSpindleSpeed.value())
        f.chipThinning.setChecked(bool(getattr(obj, "ChipThinning", False)))
        self._refreshDerived()
        try:
            f.feedSource.setText(self._describeDefaults(obj))
        except Exception as e:
            f.feedSource.setText(str(e))

    def updateData(self, obj, prop):
        # Stepover lives on the Passes bar; keep the chip-thinning line in step with it.
        if prop in ("StepOver", "ChipThinning") and hasattr(self.form, "chipThinningInfo"):
            self._refreshChipThinning()

    def _commitFeedFields(self, obj):
        # Only write a field the user changed since it was loaded (the boxes round to their
        # display precision -- see _qty_commit).
        f = self.form
        for prop, box in [("SpindleSpeed", f.spindleSpeed), ("RampSpindleSpeed", f.rampSpindleSpeed)]:
            if box.value() != box.property("camStudioLoaded"):
                setattr(obj, prop, box.value())
                box.setProperty("camStudioLoaded", box.value())
        for prop, box in self._feedFields():
            if box.value() != box.property("camStudioLoaded"):
                setattr(obj, prop, box.value() * f.feedScale)
                box.setProperty("camStudioLoaded", box.value())
        if hasattr(obj, "ChipThinning") and obj.ChipThinning != f.chipThinning.isChecked():
            obj.ChipThinning = f.chipThinning.isChecked()

    def _refreshDerived(self):
        f = self.form
        diameter, flutes = self._toolGeometry()
        rpm = f.spindleSpeed.value()
        cutting = f.cuttingFeedrate.value() * f.feedScale * 60.0  # mm/min
        plunge = f.plungeFeedrate.value() * f.feedScale * 60.0
        f.surfaceSpeed.setValue(math.pi * diameter * rpm / f.surfaceScale)
        f.feedPerTooth.setValue(cutting / (rpm * flutes) / f.lenScale if rpm > 0 and flutes > 0 else 0)
        f.feedPerTooth.setEnabled(flutes > 0)
        f.plungeFeedPerRev.setValue(plunge / rpm / f.lenScale if rpm > 0 else 0)
        self._refreshChipThinning()

    def _refreshChipThinning(self):
        f = self.form
        obj = self.obj
        on = f.chipThinning.isChecked()
        stepover = float(getattr(obj, "StepOver", 100))
        if not on:
            f.chipThinningInfo.setText("")
            f.chipThinningInfo.hide()
            return
        f.chipThinningInfo.show()
        probe = type("Probe", (), {"ChipThinning": True, "StepOver": stepover})()
        factor = obj.Proxy.chipThinningFactor(probe)
        if factor == 1.0:
            f.chipThinningInfo.setText(
                translate(
                    "CamStudio_Pocket",
                    "No change at %.0f%% stepover (applies under 50%%).",
                )
                % stepover
            )
            return
        effective = f.cuttingFeedrate.value() * factor
        f.chipThinningInfo.setText(
            translate("CamStudio_Pocket", "At %.0f%% stepover: cutting feed x%.2f = %s %s")
            % (stepover, factor, ("%%.%df" % f.cuttingFeedrate.decimals()) % effective,
               f.cuttingFeedrate.suffix().strip())
        )

    def _onSurfaceSpeedEdited(self):
        f = self.form
        diameter, _flutes = self._toolGeometry()
        if diameter > 0:
            f.spindleSpeed.setValue(f.surfaceSpeed.value() * f.surfaceScale / (math.pi * diameter))
            f.spindleSpeed.editingFinished.emit()

    def _onFeedPerToothEdited(self):
        f = self.form
        _diameter, flutes = self._toolGeometry()
        rpm = f.spindleSpeed.value()
        if flutes > 0 and rpm > 0:
            mmPerMin = f.feedPerTooth.value() * f.lenScale * rpm * flutes
            f.cuttingFeedrate.setValue(mmPerMin / 60.0 / f.feedScale)
            f.cuttingFeedrate.editingFinished.emit()

    def _onResetFeeds(self):
        obj = self.obj
        obj.Proxy.loadDefaultFeeds(obj)
        self._setFeedFields(obj)
        self.setDirty()

    def _describeDefaults(self, obj):
        """One line saying where Reset to Defaults takes its values from."""
        defaults = obj.Proxy.materialDefaults(obj) if hasattr(obj.Proxy, "materialDefaults") else None
        if defaults is None:
            return translate(
                "CamStudio_Pocket",
                "Defaults: tool controller (the setup's stock has no machining material).",
            )
        text = translate("CamStudio_Pocket", "Defaults: %s, %s tool") % (
            defaults.get("material", "?"),
            defaults.get("toolMaterial", "?"),
        )
        if defaults.get("chipload") is not None:
            text += translate("CamStudio_Pocket", "; feeds from the tool's chipload.")
        else:
            text += translate(
                "CamStudio_Pocket",
                "; the tool has no Chipload set, so feeds come from the tool controller.",
            )
        return text

    def _onPlungePerRevEdited(self):
        f = self.form
        rpm = f.spindleSpeed.value()
        if rpm > 0:
            mmPerMin = f.plungeFeedPerRev.value() * f.lenScale * rpm
            f.plungeFeedrate.setValue(mmPerMin / 60.0 / f.feedScale)
            f.plungeFeedrate.editingFinished.emit()

    def getFields(self, obj):
        before = obj.ToolController
        self.updateToolController(obj, self.form.toolController)
        self.updateCoolant(obj, self.form.coolantController)
        if not hasattr(obj, "CuttingFeedrate"):
            return
        if obj.ToolController is not before:
            # A different tool: start again from its values, as Fusion does.
            obj.Proxy.loadFeedsFromTool(obj)
            self._setFeedFields(obj)
        else:
            self._commitFeedFields(obj)

    def setFields(self, obj):
        self.setupToolController(obj, self.form.toolController)
        self._pruneToolComboSentinels(obj)
        self.setupCoolant(obj, self.form.coolantController)
        if hasattr(obj, "CuttingFeedrate"):
            self._setFeedFields(obj)

    def getSignalsForUpdate(self, obj):
        f = self.form
        return [
            f.toolController.currentIndexChanged,
            f.coolantController.currentIndexChanged,
            f.spindleSpeed.editingFinished,
            f.rampSpindleSpeed.editingFinished,
            f.chipThinning.clicked,
        ] + [box.editingFinished for _prop, box in self._feedFields()]


class HeightsBar(PathOpGui.TaskPanelPage):
    """One Heights bar, as in Fusion, in place of FreeCAD's separate Heights and Depths
    pages. Those pages are still built (and initialized) by the upstream TaskPanel; this
    bar takes their field widgets into its own layout under Fusion's names and forwards
    every page callback to them, so expressions, the "set from selection" buttons and
    value handling stay exactly upstream's.

    Fusion lists Clearance, Retract, Feed, Top and Bottom height. Mapped from what
    FreeCAD's generated G-code actually does (not from the names): the tool rapids down to
    Safe Height and feeds from there, so Safe Height is Fusion's *Feed* Height; between
    passes it retracts to Clearance Height, so there is no separate Retract Height; Start
    and Final Depth are Top and Bottom Height."""

    def __init__(self, obj, features, heightsPage, depthsPage):
        self.children = [heightsPage, depthsPage]
        self.heightsPage = heightsPage
        self.depthsPage = depthsPage
        super().__init__(obj, features)
        self.panelTitle = "Heights"
        self.setIcon(":/icons/CAM_Heights.svg")
        for child in self.children:
            # A child marking itself dirty (e.g. its "set from selection" button) has to
            # show up on this bar: the panel only asks the pages in its list.
            child.onDirtyChanged(lambda _page: self.setDirty())

    def getTitle(self, obj):
        return translate("CamStudio_Pocket", "Heights")

    def getForm(self):
        h, d = self.heightsPage.form, self.depthsPage.form
        # Retract Height is CAM Studio's own property (ops/pocket.py), bound with the same
        # expression-aware helper FreeCAD's height fields use.
        self.retractField = _quantity_spinbox()
        self.retract = None
        if hasattr(self.obj, "RetractHeight"):
            self.retract = PathGuiUtil.QuantitySpinBox(self.retractField, self.obj, "RetractHeight")

        form = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(form)
        section = CollapsibleSection(translate("CamStudio_Pocket", "Heights"))
        rows = QtWidgets.QFormLayout()
        rows.setRowWrapPolicy(QtWidgets.QFormLayout.WrapLongRows)
        for label, tip, field, button in (
            (translate("CamStudio_Pocket", "Clearance Height"),
             translate("CamStudio_Pocket", "Height for rapid moves clear of everything. "
                       "The tool also retracts to it between passes (FreeCAD has no "
                       "separate retract height)"),
             h.clearanceHeight, None),
            (translate("CamStudio_Pocket", "Retract Height"),
             translate("CamStudio_Pocket", "Height the tool retracts to between passes. "
                       "Kept between Feed Height and Clearance Height"),
             self.retractField if self.retract is not None else None, None),
            (translate("CamStudio_Pocket", "Feed Height"),
             translate("CamStudio_Pocket", "The tool rapids down to this height, then "
                       "feeds from here into the cut (FreeCAD: Safe Height)"),
             h.safeHeight, None),
            (translate("CamStudio_Pocket", "Top Height"),
             translate("CamStudio_Pocket", "Top of the cut (FreeCAD: Start Depth)"),
             d.startDepth, d.startDepthSet),
            (translate("CamStudio_Pocket", "Bottom Height"),
             translate("CamStudio_Pocket", "Bottom of the cut (FreeCAD: Final Depth)"),
             d.finalDepth, d.finalDepthSet),
        ):
            # FreeCAD's Depths page hides fields the op doesn't use; skip those. (Only check
            # FreeCAD's widgets: ours has no parent yet, which Qt also reports as hidden.)
            if field is None or (field is not self.retractField and field.isHidden()):
                continue
            field.setToolTip(tip)
            if button is not None and not button.isHidden():
                row = QtWidgets.QHBoxLayout()
                row.addWidget(field, 1)
                row.addWidget(button)
                rows.addRow(label, row)
            else:
                rows.addRow(label, field)
        section.setContentLayout(rows)
        layout.addWidget(section)
        layout.addStretch(1)
        return form

    def initPage(self, obj):
        pass  # the children were initialized by the upstream TaskPanel

    def getFields(self, obj):
        for child in self.children:
            child.getFields(obj)
        if self.retract is not None:
            self.retract.updateProperty()

    def setFields(self, obj):
        for child in self.children:
            child.setFields(obj)
        if self.retract is not None:
            self.retract.updateWidget()

    def getSignalsForUpdate(self, obj):
        signals = [s for child in self.children for s in child.getSignalsForUpdate(obj)]
        if self.retract is not None:
            signals.append(self.retractField.editingFinished)
        return signals

    def registerSignalHandlers(self, obj):
        for child in self.children:
            child.registerSignalHandlers(obj)

    def pageUpdateData(self, obj, prop):
        for child in self.children:
            child.pageUpdateData(obj, prop)
        if prop in ("RetractHeight", "ClearanceHeight") and self.retract is not None:
            self.retract.updateWidget()

    def updateSelection(self, obj, sel):
        for child in self.children:
            child.updateSelection(obj, sel)

    def cleanupPage(self, obj):
        for child in self.children:
            child.cleanupPage(obj)

    def setClean(self):
        super().setClean()
        for child in getattr(self, "children", []):
            child.isdirty = False


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
        # Fusion's "Sideways Compensation": which side of the path the tool sits on, Left or
        # Right. Backed by FreeCAD's CutMode (Climb/Conventional); the mapping depends on the
        # spindle direction, so the labels are filled in by _fillSidewaysCompensation.
        form.cutMode = QtWidgets.QComboBox()
        # Fusion's "Maximum Stepover" is a distance. FreeCAD stores StepOver as a whole
        # percent of the tool diameter, so the distance is converted (and snaps to 1%).
        form.maxStepover = _quantity_spinbox()
        form.stepOverPercent = QtWidgets.QSpinBox()
        form.stepOverPercent.setRange(1, 100)
        form.stepOverPercent.setSuffix(" %")
        form.stepOverPercent.setToolTip(
            translate("CamStudio_Pocket", "The same stepover as a percent of the tool diameter. Edit either box.")
        )
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
        passes_layout.addRow(translate("CamStudio_Pocket", "Sideways Compensation"), form.cutMode)
        # One setting, shown two ways on one row: distance = percent of the tool diameter.
        # Both boxes are editable and kept in step (see _commitStepover).
        stepoverRow = QtWidgets.QHBoxLayout()
        stepoverRow.addWidget(form.maxStepover, 3)
        stepoverRow.addWidget(QtWidgets.QLabel("="))
        stepoverRow.addWidget(form.stepOverPercent, 2)
        stepoverRow.addWidget(QtWidgets.QLabel(translate("CamStudio_Pocket", "of tool \u00d8")))
        passes_layout.addRow(translate("CamStudio_Pocket", "Maximum Stepover"), stepoverRow)
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
            self._showStepover(obj)
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

    def _toolDiameter(self, obj):
        tc = getattr(obj, "ToolController", None)
        try:
            return float(tc.Tool.Diameter.Value)
        except Exception:
            return 0.0

    def _showStepover(self, obj):
        d = self._toolDiameter(obj)
        _qty_set(self.form.maxStepover, obj.StepOver / 100.0 * d if d > 0 else 0.0)
        self.form.maxStepover.setEnabled(d > 0)
        self.form.stepOverPercent.blockSignals(True)
        self.form.stepOverPercent.setValue(obj.StepOver)
        self.form.stepOverPercent.blockSignals(False)
        self.form.stepOverPercent.setProperty("camStudioLoaded", obj.StepOver)

    def _commitStepover(self, obj):
        """FreeCAD's whole-percent StepOver from whichever of the two linked fields the
        user changed (percent wins if both did), then show both in step again."""
        percentBox = self.form.stepOverPercent
        distance = self.form.maxStepover
        percent = None
        if percentBox.value() != percentBox.property("camStudioLoaded"):
            percent = percentBox.value()
        elif distance.property("rawValue") != distance.property("camStudioLoaded"):
            d = self._toolDiameter(obj)
            if d > 0:
                percent = int(min(100, max(1, round(distance.property("rawValue") / d * 100.0))))
        if percent is None:
            return
        if obj.StepOver != percent:
            obj.StepOver = percent
        self._showStepover(obj)  # snap the distance to what the percent really gives

    def getFields(self, obj):
        if obj.CutMode != str(self.form.cutMode.currentData()):
            obj.CutMode = str(self.form.cutMode.currentData())
        self._commitStepover(obj)
        if hasattr(obj, "UseMultipleDepths"):
            for prop, widget in (("UseMultipleDepths", self.form.useMultipleDepths),
                                 ("UseEvenStepdowns", self.form.useEvenStepdowns)):
                if getattr(obj, prop) != widget.isChecked():
                    setattr(obj, prop, widget.isChecked())
            if obj.FinishingStepdowns != self.form.finishingStepdowns.value():
                obj.FinishingStepdowns = self.form.finishingStepdowns.value()
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
        self._fillSidewaysCompensation(obj)
        self.form.cutMode.setCurrentIndex(max(0, self.form.cutMode.findData(obj.CutMode)))
        self._showStepover(obj)
        if hasattr(obj, "UseMultipleDepths"):
            self.form.useMultipleDepths.setChecked(obj.UseMultipleDepths)
            self.form.useEvenStepdowns.setChecked(obj.UseEvenStepdowns)
            self.form.finishingStepdowns.setValue(obj.FinishingStepdowns)
            self._updateDepthEnabled(obj)
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
            self.form.maxStepover.editingFinished,
            self.form.stepOverPercent.editingFinished,
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
            self.form.useStartPoint.clicked,
        ]


class LinkingPage(_BarPage):
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
        form.leadInRadius = _quantity_spinbox()
        form.leadInSweepAngle = _quantity_spinbox(unit="deg")
        form.leadInDistance = _quantity_spinbox()
        form.leadInPerpendicular = QtWidgets.QCheckBox(
            translate("CamStudio_Pocket", "Perpendicular Lead-In")
        )
        form.useLeadOut = QtWidgets.QCheckBox(translate("CamStudio_Pocket", "Lead-Out (Exit)"))
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
        form.rampType.addItem(translate("CamStudio_Pocket", "Plunge Outside Stock"), "Plunge Outside Stock")
        form.rampType.addItem(translate("CamStudio_Pocket", "Helix"), "Helix")
        form.rampAngle = _quantity_spinbox(unit="deg")
        form.helicalRampDiameter = _quantity_spinbox()
        form.minimumRampDiameter = _quantity_spinbox()
        form.maxRampStepdown = _quantity_spinbox()
        form.rampClearanceHeight = _quantity_spinbox()
        form.outsidePlungeDistance = _quantity_spinbox()
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
        ramp_layout.addRow(
            translate("CamStudio_Pocket", "Ramp Clearance Height"), form.rampClearanceHeight
        )
        ramp_layout.addRow(
            translate("CamStudio_Pocket", "Plunge Distance (0 = 1.25 x tool \u00d8)"),
            form.outsidePlungeDistance,
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
        _qty_commit(obj, "RampAngle", self.form.rampAngle)
        _qty_commit(obj, "HelicalRampDiameter", self.form.helicalRampDiameter)
        _qty_commit(obj, "MinimumRampDiameter", self.form.minimumRampDiameter)
        _qty_commit(obj, "MaxRampStepdown", self.form.maxRampStepdown)
        _qty_commit(obj, "RampClearanceHeight", self.form.rampClearanceHeight)
        _qty_commit(obj, "OutsidePlungeDistance", self.form.outsidePlungeDistance)
        if obj.KeepToolDown != self.form.keepToolDown.isChecked():
            obj.KeepToolDown = self.form.keepToolDown.isChecked()
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
        _qty_set(self.form.rampClearanceHeight, obj.RampClearanceHeight.Value)
        _qty_set(self.form.outsidePlungeDistance, obj.OutsidePlungeDistance.Value)
        self.form.keepToolDown.setChecked(obj.KeepToolDown)
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

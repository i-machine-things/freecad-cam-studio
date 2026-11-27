"""Pieces every CAM Studio operation dialog shares.

FreeCAD's task panel stacks its pages as collapsible bars (Base Geometry, Extensions, Depths,
Heights, Operation). Fusion splits the same dialog into tabs (Tool, Multi-axis, Geometry,
Heights, Passes, Linking). Every CAM Studio op keeps FreeCAD's bars and lines them up with
Fusion's tabs:

    Tool, Base Geometry, Extensions, Heights, Passes, Linking

- `ToolBarPage` is the Tool bar (tool, Feed & Speed, coolant) and the one op page the
  upstream TaskPanel knows about. An op's page subclasses it, names the op (`opTitle`) and
  supplies its own Passes and Linking bars (`makeBars`); `attachBars` adds them to the panel
  and puts every bar in the order above.
- `HeightsBar` folds FreeCAD's Heights and Depths pages into Fusion's one Heights bar.
- `StepoverRow` is the "[distance] = [%] of tool Ø" row for FreeCAD's whole-percent StepOver.

Multi-axis is left out until it has fields. No .ui resource files: the forms are built in
Python so CAM Studio owns the layout, not just the data wiring.
"""

import math

import FreeCAD
import FreeCADGui as Gui
from PySide import QtWidgets

import Path.Base.Gui.Util as PathGuiUtil
import Path.Op.Gui.Base as PathOpGui
import PathScripts.PathUtils as PathUtils

import widgets.tool_picker as ToolPicker
from widgets.collapsible import CollapsibleSection

translate = FreeCAD.Qt.translate


# -- Widget helpers ------------------------------------------------------------------------


def quantity_spinbox(unit="mm"):
    # Gui::QuantitySpinBox, created via UiLoader, only exposes QAbstractSpinBox's base
    # methods through the Python binding -- setValue()/value()/setDecimals() etc. aren't
    # reachable directly. Use the generic Qt property interface instead ("rawValue" is the
    # widget's internal-unit numeric value; "unit" sets its display unit).
    widget = Gui.UiLoader().createWidget("Gui::QuantitySpinBox")
    widget.setProperty("unit", unit)
    return widget


def qty_get(widget):
    return widget.property("rawValue")


def qty_set(widget, value):
    widget.setProperty("rawValue", value)
    # Remember what the widget itself reports right after loading. It rounds to its display
    # precision in the user's unit schema (3 mm reads back as 2.999994 under an inch
    # schema), so "differs from the property" is not the same as "the user edited it".
    widget.setProperty("camStudioLoaded", widget.property("rawValue"))


def qty_commit(obj, prop, widget):
    """Write the widget's value to obj.<prop> only if the user actually changed the widget
    since it was loaded. Comparing against the property instead would rewrite every
    quantity on the page with its display-rounded form whenever any one field changed."""
    value = widget.property("rawValue")
    if value == widget.property("camStudioLoaded"):
        return
    setattr(obj, prop, value)
    widget.setProperty("camStudioLoaded", value)


def feed_display_unit():
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


def length_display_unit():
    """(unit label, mm per display unit, decimals) for small lengths such as feed per tooth,
    following the user's unit schema."""
    lengthUnit = FreeCAD.Units.Quantity(1.0, FreeCAD.Units.Length).getUserPreferred()[2]
    if lengthUnit in ("in", "ft", "thou", "yd", "mi"):
        return "in", 25.4, 4
    return "mm", 1.0, 3


def rate_box(suffix, decimals, maximum=1e7):
    box = QtWidgets.QDoubleSpinBox()
    box.setRange(0, maximum)
    box.setDecimals(decimals)
    box.setSuffix(" " + suffix)
    return box


def form_layout():
    """A QFormLayout that wraps long labels above their field: the task panel is narrow by
    default, and long labels would otherwise force the form wider than it and clip the
    fields behind a horizontal scroll bar."""
    layout = QtWidgets.QFormLayout()
    layout.setRowWrapPolicy(QtWidgets.QFormLayout.WrapLongRows)
    return layout


def tool_diameter(obj):
    tc = getattr(obj, "ToolController", None)
    try:
        return float(tc.Tool.Diameter.Value)
    except Exception:
        return 0.0


class BarPage(PathOpGui.TaskPanelPage):
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


# -- Tool bar ------------------------------------------------------------------------------

# (op property, form attribute, label) for each per-op feed, in Fusion's Tool-tab order. The
# bar shows the ones the op has (its Proxy.FEEDS, ops/feeds.py).
FEED_ROWS = (
    ("CuttingFeedrate", "cuttingFeedrate", "Cutting Feedrate"),
    ("LeadInFeedrate", "leadInFeedrate", "Lead-In Feedrate"),
    ("LeadOutFeedrate", "leadOutFeedrate", "Lead-Out Feedrate"),
    ("RampFeedrate", "rampFeedrate", "Ramp Feedrate"),
    ("PlungeFeedrate", "plungeFeedrate", "Plunge Feedrate"),
)


class ToolBarPage(PathOpGui.TaskPanelPage):
    """Tool bar, and the entry point the upstream TaskPanel knows about. Adds the op's own
    bars to the panel and orders all bars like Fusion's tabs (see attachBars).

    Subclasses provide `opTitle()` (the dialog heading), `ICON`, and `makeBars(obj)`: the
    bars after Heights, the first of them with an `addDepthRows(depthsForm)` method that
    takes FreeCAD's stepdown fields (they sit under Passes in Fusion)."""

    ICON = ":/icons/CAM_Pocket.svg"

    def opTitle(self):
        raise NotImplementedError

    def makeBars(self, obj):
        return []

    def getTitle(self, obj):
        # The TaskPanel asks for the title twice: once for the panel heading, then -- after
        # renaming this page "Operation" -- for this page's own bar.
        if getattr(self, "title", None) == "Operation":
            return translate("CamStudio", "Tool")
        return self.opTitle()

    def _opFeeds(self):
        proxy = getattr(self.obj, "Proxy", None)
        feeds = getattr(proxy, "FEEDS", None)
        if feeds is None:
            feeds = [prop for prop, _attr, _label in FEED_ROWS]
        return [row for row in FEED_ROWS if row[0] in feeds and hasattr(self.obj, row[0])]

    def getForm(self):
        form = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(form)

        tool_group = CollapsibleSection(translate("CamStudio", "Tool"))
        tool_layout = QtWidgets.QFormLayout()
        form.toolController = QtWidgets.QComboBox()
        form.selectToolButton = QtWidgets.QPushButton(translate("CamStudio", "Select..."))
        tool_row = QtWidgets.QHBoxLayout()
        tool_row.addWidget(form.toolController, 1)
        tool_row.addWidget(form.selectToolButton)
        form.coolantController = QtWidgets.QComboBox()
        tool_layout.addRow(translate("CamStudio", "Tool"), tool_row)
        tool_group.setContentLayout(tool_layout)
        layout.addWidget(tool_group)
        form.selectToolButton.clicked.connect(self._onSelectTool)

        # Feed & Speed, per operation (Fusion's Tool tab). Values live on the op (see
        # ops/feeds.py loadFeedsFromTool); picking another tool reloads them from it.
        # Surface Speed, Feed per Tooth and Plunge Feed per Revolution are derived: editing
        # one recalculates its partner field instead of being stored.
        feedUnit, form.feedScale, feedDecimals = feed_display_unit()
        lenUnit, form.lenScale, lenDecimals = length_display_unit()
        imperial = lenUnit == "in"
        form.surfaceUnit = "ft/min" if imperial else "m/min"
        form.surfaceScale = 304.8 if imperial else 1000.0  # mm/min per display unit
        fs_group = CollapsibleSection(translate("CamStudio", "Feed && Speed"))
        fs_layout = form_layout()
        form.spindleSpeed = rate_box("rpm", 0, 200000)
        form.surfaceSpeed = rate_box(form.surfaceUnit, 2)
        form.rampSpindleSpeed = rate_box("rpm", 0, 200000)
        self.feedRows = self._opFeeds()
        for _prop, attr, _label in self.feedRows:
            setattr(form, attr, rate_box(feedUnit, feedDecimals))
        form.feedPerTooth = rate_box(lenUnit, lenDecimals, 1000)
        form.plungeFeedPerRev = rate_box(lenUnit, lenDecimals, 1000)
        form.chipThinning = QtWidgets.QCheckBox(translate("CamStudio", "Chip Thinning"))
        form.chipThinning.setToolTip(
            translate(
                "CamStudio",
                "With a stepover under half the tool diameter, chips come out thinner than the "
                "feed per tooth. This raises the cutting feed to bring them back to the "
                "chipload. Engagement is higher in corners and on the first, full-width cut.",
            )
        )
        form.chipThinningInfo = QtWidgets.QLabel()
        form.chipThinningInfo.setWordWrap(True)
        feeds = {prop: (attr, label) for prop, attr, label in self.feedRows}
        rows = [
            ("Spindle Speed", form.spindleSpeed),
            ("Surface Speed", form.surfaceSpeed),
            ("Ramp Spindle Speed", form.rampSpindleSpeed),
        ]
        if "CuttingFeedrate" in feeds:
            rows += [
                ("Cutting Feedrate", form.cuttingFeedrate),
                ("Feed per Tooth", form.feedPerTooth),
                (None, form.chipThinning),
                (None, form.chipThinningInfo),
            ]
        for prop in ("LeadInFeedrate", "LeadOutFeedrate", "RampFeedrate", "PlungeFeedrate"):
            if prop in feeds:
                attr, label = feeds[prop]
                rows.append((label, getattr(form, attr)))
        if "PlungeFeedrate" in feeds:
            rows.append(("Plunge Feed per Revolution", form.plungeFeedPerRev))
        rows.append(("Coolant", form.coolantController))
        for label, widget in rows:
            if label is None:
                fs_layout.addRow(widget)
            else:
                fs_layout.addRow(translate("CamStudio", label), widget)
        # Re-apply the defaults for the current tool and stock material (Fusion fills an
        # operation from the tool preset the same way when the tool is picked).
        form.resetFeeds = QtWidgets.QPushButton(translate("CamStudio", "Reset to Defaults"))
        form.resetFeeds.setToolTip(
            translate(
                "CamStudio",
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
        if "CuttingFeedrate" in feeds:
            form.cuttingFeedrate.editingFinished.connect(self._refreshDerived)
            form.feedPerTooth.editingFinished.connect(self._onFeedPerToothEdited)
        if "PlungeFeedrate" in feeds:
            form.plungeFeedrate.editingFinished.connect(self._refreshDerived)
            form.plungeFeedPerRev.editingFinished.connect(self._onPlungePerRevEdited)
        form.surfaceSpeed.editingFinished.connect(self._onSurfaceSpeedEdited)

        layout.addStretch(1)
        return form

    def initPage(self, obj):
        self.setIcon(self.ICON)
        self.attachBars(obj)

    def attachBars(self, obj):
        """Add the op's bars to the panel and put the bars in Fusion's tab order. Runs while
        the upstream TaskPanel is initializing its pages; this page is the last one it built,
        so every page already in the list has been initialized. The new pages are
        initialized here directly (and ignore a second initPage), so this works whether or
        not the upstream loop goes on to visit them."""
        parent = self.parent
        pages = getattr(parent, "featurePages", None)
        if pages is None or getattr(self, "bars", None):
            return
        self.bars = self.makeBars(obj)
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
            if self.bars and hasattr(self.bars[0], "addDepthRows"):
                self.bars[0].addDepthRows(depths.form)
            upstream.append(heightsBar)
        else:
            upstream += [p for p in (heights, depths) if p is not None]
        pages[:] = [self] + upstream + self.bars

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
        return [(prop, getattr(self.form, attr)) for prop, attr, _label in self.feedRows]

    def _hasFeed(self, prop):
        return any(p == prop for p, _attr, _label in self.feedRows)

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
        # display precision -- see qty_commit).
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
        f.surfaceSpeed.setValue(math.pi * diameter * rpm / f.surfaceScale)
        if self._hasFeed("CuttingFeedrate"):
            cutting = f.cuttingFeedrate.value() * f.feedScale * 60.0  # mm/min
            f.feedPerTooth.setValue(
                cutting / (rpm * flutes) / f.lenScale if rpm > 0 and flutes > 0 else 0
            )
            f.feedPerTooth.setEnabled(flutes > 0)
        if self._hasFeed("PlungeFeedrate"):
            plunge = f.plungeFeedrate.value() * f.feedScale * 60.0
            f.plungeFeedPerRev.setValue(plunge / rpm / f.lenScale if rpm > 0 else 0)
        self._refreshChipThinning()

    def _refreshChipThinning(self):
        f = self.form
        obj = self.obj
        on = f.chipThinning.isChecked()
        stepover = float(getattr(obj, "StepOver", 100))
        if not on or not self._hasFeed("CuttingFeedrate"):
            f.chipThinningInfo.setText("")
            f.chipThinningInfo.hide()
            return
        f.chipThinningInfo.show()
        probe = type("Probe", (), {"ChipThinning": True, "StepOver": stepover})()
        factor = obj.Proxy.chipThinningFactor(probe)
        if factor == 1.0:
            f.chipThinningInfo.setText(
                translate(
                    "CamStudio",
                    "No change at %.0f%% stepover (applies under 50%%).",
                )
                % stepover
            )
            return
        effective = f.cuttingFeedrate.value() * factor
        f.chipThinningInfo.setText(
            translate("CamStudio", "At %.0f%% stepover: cutting feed x%.2f = %s %s")
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

    def _onPlungePerRevEdited(self):
        f = self.form
        rpm = f.spindleSpeed.value()
        if rpm > 0:
            mmPerMin = f.plungeFeedPerRev.value() * f.lenScale * rpm
            f.plungeFeedrate.setValue(mmPerMin / 60.0 / f.feedScale)
            f.plungeFeedrate.editingFinished.emit()

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
                "CamStudio",
                "Defaults: tool controller (the setup's stock has no machining material).",
            )
        text = translate("CamStudio", "Defaults: %s, %s tool") % (
            defaults.get("material", "?"),
            defaults.get("toolMaterial", "?"),
        )
        if defaults.get("chipload") is not None:
            text += translate("CamStudio", "; feeds from the tool's chipload.")
        else:
            text += translate(
                "CamStudio",
                "; the tool has no Chipload set, so feeds come from the tool controller.",
            )
        return text

    def getFields(self, obj):
        before = obj.ToolController
        self.updateToolController(obj, self.form.toolController)
        self.updateCoolant(obj, self.form.coolantController)
        if not hasattr(obj, "SpindleSpeed"):
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
        if hasattr(obj, "SpindleSpeed"):
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


# -- Heights bar ---------------------------------------------------------------------------


class HeightsBar(PathOpGui.TaskPanelPage):
    """One Heights bar, as in Fusion, in place of FreeCAD's separate Heights and Depths
    pages. Those pages are still built (and initialized) by the upstream TaskPanel; this
    bar takes their field widgets into its own layout under Fusion's names and forwards
    every page callback to them, so expressions, the "set from selection" buttons and
    value handling stay exactly upstream's.

    Fusion lists Clearance, Retract, Feed, Top and Bottom height. Mapped from what
    FreeCAD's generated G-code actually does (not from the names): the tool rapids down to
    Safe Height and feeds from there, so Safe Height is Fusion's *Feed* Height; between
    passes it retracts to Clearance Height, so without CAM Studio's own RetractHeight there
    is no separate Retract Height; Start and Final Depth are Top and Bottom Height."""

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
        return translate("CamStudio", "Heights")

    def getForm(self):
        h, d = self.heightsPage.form, self.depthsPage.form
        # Retract Height is CAM Studio's own property (ops/pocket.py), bound with the same
        # expression-aware helper FreeCAD's height fields use.
        self.retractField = quantity_spinbox()
        self.retract = None
        if hasattr(self.obj, "RetractHeight"):
            self.retract = PathGuiUtil.QuantitySpinBox(self.retractField, self.obj, "RetractHeight")
        clearanceTip = (
            translate("CamStudio", "Height for rapid moves clear of everything")
            if self.retract is not None
            else translate(
                "CamStudio",
                "Height for rapid moves clear of everything. The tool also retracts to it "
                "between passes (FreeCAD has no separate retract height)",
            )
        )

        form = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(form)
        section = CollapsibleSection(translate("CamStudio", "Heights"))
        rows = form_layout()
        for label, tip, field, button in (
            (translate("CamStudio", "Clearance Height"), clearanceTip, h.clearanceHeight, None),
            (translate("CamStudio", "Retract Height"),
             translate("CamStudio", "Height the tool retracts to between passes. "
                       "Kept between Feed Height and Clearance Height"),
             self.retractField if self.retract is not None else None, None),
            (translate("CamStudio", "Feed Height"),
             translate("CamStudio", "The tool rapids down to this height, then "
                       "feeds from here into the cut (FreeCAD: Safe Height)"),
             h.safeHeight, None),
            (translate("CamStudio", "Top Height"),
             translate("CamStudio", "Top of the cut (FreeCAD: Start Depth)"),
             d.startDepth, d.startDepthSet),
            (translate("CamStudio", "Bottom Height"),
             translate("CamStudio", "Bottom of the cut (FreeCAD: Final Depth)"),
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


# -- Stepover row --------------------------------------------------------------------------


class StepoverRow:
    """One setting shown two ways on one row: "[distance] = [%] of tool Ø". Fusion gives a
    stepover as a distance; FreeCAD stores StepOver as a whole percent of the tool diameter,
    so the distance is converted (and snaps to 1%). Both boxes are editable and kept in
    step. The widgets go on `form` as `maxStepover` and `stepOverPercent`."""

    def __init__(self, form):
        form.maxStepover = quantity_spinbox()
        form.stepOverPercent = QtWidgets.QSpinBox()
        form.stepOverPercent.setRange(1, 100)
        form.stepOverPercent.setSuffix(" %")
        form.stepOverPercent.setToolTip(
            translate("CamStudio", "The same stepover as a percent of the tool diameter. Edit either box.")
        )
        self.distance = form.maxStepover
        self.percent = form.stepOverPercent
        self.layout = QtWidgets.QHBoxLayout()
        self.layout.addWidget(self.distance, 3)
        self.layout.addWidget(QtWidgets.QLabel("="))
        self.layout.addWidget(self.percent, 2)
        self.layout.addWidget(QtWidgets.QLabel(translate("CamStudio", "of tool Ø")))

    def show(self, obj):
        d = tool_diameter(obj)
        qty_set(self.distance, obj.StepOver / 100.0 * d if d > 0 else 0.0)
        self.distance.setEnabled(d > 0)
        self.percent.blockSignals(True)
        self.percent.setValue(obj.StepOver)
        self.percent.blockSignals(False)
        self.percent.setProperty("camStudioLoaded", obj.StepOver)

    def commit(self, obj):
        """FreeCAD's whole-percent StepOver from whichever of the two linked fields the
        user changed (percent wins if both did), then show both in step again."""
        percent = None
        if self.percent.value() != self.percent.property("camStudioLoaded"):
            percent = self.percent.value()
        elif self.distance.property("rawValue") != self.distance.property("camStudioLoaded"):
            d = tool_diameter(obj)
            if d > 0:
                percent = int(min(100, max(1, round(self.distance.property("rawValue") / d * 100.0))))
        if percent is None:
            return
        if obj.StepOver != percent:
            obj.StepOver = percent
        self.show(obj)  # snap the distance to what the percent really gives

    def signals(self):
        return [self.distance.editingFinished, self.percent.editingFinished]

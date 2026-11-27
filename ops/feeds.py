"""Per-operation Feed & Speed, shared by CAM Studio's operations.

Fusion keeps speeds and feeds on each operation (its Tool tab), not only on the tool. FreeCAD
keeps them on the tool controller. `FeedAndSpeed` is a mixin for a CAM Studio op proxy (a
subclass of an upstream `Path.Op` class): it adds the op's own Feed & Speed properties, fills
them from the tool and the setup's stock material (cs_materials/library.py), and makes the
upstream toolpath generator use them:

- `opExecute` swaps the tool controller's feeds (Base.execute has just read them into
  `self.horizFeed` / `self.vertFeed`) for the op's own before upstream generates moves.
- `applySpindleSpeed` sets the op's spindle speed at its start when it differs from the tool
  controller's, and restores the controller's at its end.

Which feeds an op uses is up to the op: `FEEDS` lists the speed properties it has (the Tool
bar shows the same list -- pages/common.py).
"""

import math

import Path
from PySide.QtCore import QT_TRANSLATE_NOOP

# (property, tooltip) for every per-op feed a CAM Studio op can have, in Fusion's Tool-tab order.
ALL_FEEDS = (
    ("CuttingFeedrate", "Feedrate for cutting moves"),
    ("LeadInFeedrate", "Feedrate for the Lead-In move"),
    ("LeadOutFeedrate", "Feedrate for the Lead-Out move"),
    ("RampFeedrate", "Feedrate while ramping (helix)"),
    ("PlungeFeedrate", "Feedrate for straight plunges"),
)


class FeedAndSpeed:
    """Mixin: list it before the upstream op class (`class Op(FeedAndSpeed, Upstream)`)."""

    # The speed properties this op has. Subclasses narrow it to the feeds they apply.
    FEEDS = tuple(name for name, _doc in ALL_FEEDS)

    def initFeedProperties(self, obj):
        """Add the Feed & Speed properties (also on restore, for older documents). Seeds them
        from the tool when any were missing and the op already has a tool."""
        added = False
        docs = dict(ALL_FEEDS)
        for name, ptype, doc in (
            ("SpindleSpeed", "App::PropertyFloat", "Spindle speed (rpm) for this operation"),
            ("RampSpindleSpeed", "App::PropertyFloat", "Spindle speed (rpm) while ramping"),
        ) + tuple((name, "App::PropertySpeed", docs[name]) for name in self.FEEDS):
            if not hasattr(obj, name):
                obj.addProperty(ptype, name, "Feed & Speed", QT_TRANSLATE_NOOP("App::Property", doc))
                added = True
        if not hasattr(obj, "ChipThinning"):
            # Separate from the feeds above: adding it to an older document must not count as
            # "feeds missing" and re-seed feeds the user already set.
            obj.addProperty(
                "App::PropertyBool",
                "ChipThinning",
                "Feed & Speed",
                QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Raise the cutting feed when the stepover is under half the tool diameter, "
                    "so the actual chip thickness stays at the chipload",
                ),
            )
            obj.ChipThinning = False
        if added and getattr(obj, "ToolController", None) is not None:
            # Restoring a document made before these existed: start from its tool.
            self.loadFeedsFromTool(obj)

    def loadFeedsFromTool(self, obj):
        """Fill this op's own Feed & Speed from its defaults: the setup's stock material
        when it has machining data (cs_materials/library.py: spindle speed from the
        material's surface speed for this tool's material and diameter; feeds from the
        tool's chipload), otherwise the tool controller's values. Fusion fills an operation
        from the tool's preset for the material the same way.

        Whatever the material can't supply (e.g. no chipload known) stays at the tool
        controller's value."""
        tc = getattr(obj, "ToolController", None)
        if tc is None:
            return
        rpm, horiz, vert = tc.SpindleSpeed, tc.HorizFeed.Value, tc.VertFeed.Value
        defaults = self.materialDefaults(obj)
        if defaults is not None:
            rpm = defaults["rpm"]
            if "cutting" in defaults:
                horiz = defaults["cutting"] / 60.0
                vert = defaults["plunge"] / 60.0
        obj.SpindleSpeed = round(rpm)
        obj.RampSpindleSpeed = round(rpm)
        for name in self.FEEDS:
            # Ramp and plunge are vertical feeds; cutting and the leads horizontal.
            setattr(obj, name, vert if name in ("RampFeedrate", "PlungeFeedrate") else horiz)

    loadDefaultFeeds = loadFeedsFromTool

    def materialDefaults(self, obj):
        """cs_materials.library.defaultFeedsFor this op's tool in its setup's stock material
        (FreeCAD's Job Stock material), or None if the stock has no machining data."""
        import PathScripts.PathUtils as PathUtils
        from cs_materials import library

        job = PathUtils.findParentJob(obj)
        tc = getattr(obj, "ToolController", None)
        if job is None or tc is None:
            return None
        return library.defaultFeedsFor(job, tc.Tool)

    @staticmethod
    def chipThinningFactor(obj):
        """Radial chip thinning: with a radial engagement (stepover) ae under half the tool
        diameter D, a chip is thinner than the feed per tooth by
            RCTF = sqrt(1 - (1 - 2*ae/D)^2),
        so the cutting feed is divided by RCTF to keep the real chip thickness at the
        chipload. 1.0 when off or ae >= D/2. ae is the op's StepOver (% of D); note the
        engagement is higher than that in corners and on the first, full-width cut."""
        if not getattr(obj, "ChipThinning", False):
            return 1.0
        ratio = max(0.0, min(1.0, float(getattr(obj, "StepOver", 100)) / 100.0))
        if ratio >= 0.5 or ratio <= 0:
            return 1.0
        return 1.0 / math.sqrt(1.0 - (1.0 - 2.0 * ratio) ** 2)

    def opExecute(self, obj, *args, **kwargs):
        # Base.execute has just read the tool controller's feeds into self.horizFeed /
        # self.vertFeed; replace them with this op's own before the toolpath is generated,
        # so every move upstream emits carries the op's feeds.
        if hasattr(obj, "CuttingFeedrate"):
            self.horizFeed = obj.CuttingFeedrate.Value * self.chipThinningFactor(obj)
            self.vertFeed = obj.PlungeFeedrate.Value
        return super().opExecute(obj, *args, **kwargs)

    def spindleCommand(self, rpm):
        """M3/M4 S<rpm> in the tool's own direction (or M5 for 0), the same form FreeCAD's
        tool change emits. None for a tool that doesn't rotate."""
        direction = self.tool.Proxy.get_spindle_direction().value if self.tool else None
        if direction not in ("M3", "M4"):
            return None
        if rpm <= 0:
            return Path.Command("M5")
        return Path.Command(direction, {"S": rpm})

    def applySpindleSpeed(self, obj):
        """Per-operation spindle speed. FreeCAD sets the spindle once, at the tool change,
        from the tool controller. When this op's speed differs, set it at the op's start
        and put the controller's speed back at its end, so a following op on the same tool
        still runs at the speed its own tool change implies."""
        tcSpeed = obj.ToolController.SpindleSpeed
        if abs(obj.SpindleSpeed - tcSpeed) < 1e-9:
            return
        start = self.spindleCommand(obj.SpindleSpeed)
        restore = self.spindleCommand(tcSpeed)
        if start is None:
            return
        cmds = list(obj.Path.Commands)
        # After the op's leading comment lines, before any motion -- unless the op already
        # opens by setting the spindle (e.g. a ramp at the Ramp Spindle Speed), which would
        # override it straight away.
        i = 0
        while i < len(cmds) and cmds[i].Name.startswith("("):
            i += 1
        if i >= len(cmds) or cmds[i].Name not in ("M3", "M4", "M5"):
            cmds.insert(i, start)
        if restore is not None:
            cmds.append(restore)
        obj.Path = Path.Path(cmds)

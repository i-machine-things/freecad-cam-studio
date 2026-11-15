"""CAM Studio's own Pocket operation Proxy.

Subclasses Path.Op.PocketShape.ObjectPocket (never patches it) to add
two Fusion 2D Pocket options (docs/spec/02-2d-milling-operations.md)
that FreeCAD's stock PocketShape operation has no property/behavior for
at all:

1. "Axial Stock to Leave" -- radial stock-to-leave already exists
   upstream as `ExtraOffset`; this adds the missing Z-axis half of the
   pair by hooking `_customDepthParams`, an officially documented
   extension point in Path.Op.Area.ObjectOp.
2. "Ramp" entry (Fusion's Linking tab): FreeCAD's area-clearing engine
   has no ramp/helix-entry support at all (confirmed by reading
   Path.Op.Area.py -- its one `leadIn` reference is an unrelated
   hardcoded internal value). Implemented here as a post-process step:
   let the normal, documented pipeline build the correct straight-plunge
   toolpath first (`super().execute(obj)` -- Path.Op.Base.execute's own
   docstring says "do not overwrite!", so we never replace its body,
   only wrap it), then replace the *first* straight vertical plunge with
   a helix descent, generated as directly-sampled G1 segments (explicit
   parametric circle-while-descending math, not Part.makeHelix +
   Path.Geom.cmdsForEdge -- that combination's edge-direction/reversal
   semantics produced a genuinely backwards, garbled path in testing;
   direct sampling is simpler to get right and to verify by inspection).

   V1 scope, stated plainly rather than overclaimed: only the operation's
   very first plunge (entry into un-machined stock) is ramped. Later
   retract/re-plunge cycles within the same pass (e.g. between
   concentric offset rings) are usually re-entering already-cleared air,
   not solid material, and are deliberately left as straight plunges for
   now -- per-level/per-region ramping is a tracked follow-up, see
   docs/ROADMAP.md.
"""

import math

import FreeCAD
from PySide.QtCore import QT_TRANSLATE_NOOP

import Path
import Path.Op.Base as PathOp
import Path.Op.PocketBase as PathPocketBase
import Path.Op.PocketShape as PathPocketShape


class ObjectPocket(PathPocketShape.ObjectPocket):
    def areaOpFeatures(self, obj):
        # PathPocketShape.ObjectPocket.areaOpFeatures calls super(self.__class__, self) --
        # with self.__class__ being OUR subclass, that resolves to the same bound method on
        # every recursive call (self never changes), causing infinite recursion two levels
        # deep. Call PocketBase's implementation directly instead of going through
        # PocketShape's broken super() chain. Not a core patch -- just not inheriting a
        # buggy one-liner.
        return PathPocketBase.ObjectPocket.areaOpFeatures(self, obj) | PathOp.FeatureLocations

    def initPocketOp(self, obj):
        super().initPocketOp(obj)
        if not hasattr(obj, "AxialStockToLeave"):
            obj.addProperty(
                "App::PropertyDistance",
                "AxialStockToLeave",
                "Pocket",
                QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Material left on the pocket floor (Z axis) for a later finishing pass",
                ),
            )
            obj.AxialStockToLeave = 0
        if not hasattr(obj, "RampType"):
            obj.addProperty(
                "App::PropertyEnumeration",
                "RampType",
                "Pocket",
                QT_TRANSLATE_NOOP(
                    "App::Property", "How the tool enters the material for the first plunge"
                ),
            )
            obj.RampType = ["Plunge", "Helix"]
            obj.RampType = "Plunge"
        if not hasattr(obj, "RampAngle"):
            obj.addProperty(
                "App::PropertyAngle",
                "RampAngle",
                "Pocket",
                QT_TRANSLATE_NOOP("App::Property", "Helix ramp descent angle"),
            )
            obj.RampAngle = 2.0
        if not hasattr(obj, "HelicalRampDiameter"):
            obj.addProperty(
                "App::PropertyDistance",
                "HelicalRampDiameter",
                "Pocket",
                QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Target diameter of the helix ramp entry. 0 = auto (1.5x tool diameter)",
                ),
            )
            obj.HelicalRampDiameter = 0
        if not hasattr(obj, "MinimumRampDiameter"):
            obj.addProperty(
                "App::PropertyDistance",
                "MinimumRampDiameter",
                "Pocket",
                QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Smallest acceptable helix ramp diameter -- reduce HelicalRampDiameter "
                    "toward this for pockets too small to fit the default",
                ),
            )
            obj.MinimumRampDiameter = 0
        if not hasattr(obj, "MaxRampStepdown"):
            obj.addProperty(
                "App::PropertyDistance",
                "MaxRampStepdown",
                "Pocket",
                QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Maximum descent per helix revolution. 0 = unconstrained (RampAngle alone "
                    "determines it)",
                ),
            )
            obj.MaxRampStepdown = 0
        if not hasattr(obj, "FinishingPasses"):
            obj.addProperty(
                "App::PropertyInteger",
                "FinishingPasses",
                "Pocket",
                QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Extra wall-finishing passes stepping down from the roughing Stock to "
                    "Leave to the true wall. 0 = off",
                ),
            )
            obj.FinishingPasses = 0
        if not hasattr(obj, "FinishFeedrate"):
            obj.addProperty(
                "App::PropertySpeed",
                "FinishFeedrate",
                "Pocket",
                QT_TRANSLATE_NOOP(
                    "App::Property", "Feedrate for finishing passes. 0 = same as cutting feed"
                ),
            )
            obj.FinishFeedrate = 0

    def _customDepthParams(self, obj, strDep, finDep):
        axial = getattr(obj, "AxialStockToLeave", None)
        adjustedFinalDepth = finDep + (axial.Value if axial else 0.0)
        return super()._customDepthParams(obj, strDep, adjustedFinalDepth)

    def areaOpShapes(self, obj):
        # _customDepthParams (above) only adjusts the Z-level *iteration list* used to slice
        # the removal shape into passes -- PocketShape.areaOpShapes itself reads
        # obj.FinalDepth.Value directly to build that removal shape's actual geometry
        # (translate/extrude), completely independent of _customDepthParams. Without this,
        # AxialStockToLeave would adjust the depth-stepping metadata but never actually change
        # the real cut depth -- caught by checking the generated toolpath's Z values, not just
        # that _customDepthParams returned the right number.
        #
        # FinalDepth is normally expression-driven (bound to OpFinalDepth), but a direct
        # assignment still works and is safely overwritten back by the expression on the next
        # real recompute -- verified empirically. Restore it immediately after this synchronous
        # call regardless, so nothing outside this method ever observes the adjusted value.
        axial = getattr(obj, "AxialStockToLeave", None)
        if not axial or axial.Value == 0:
            return super().areaOpShapes(obj)
        original = obj.FinalDepth.Value
        obj.FinalDepth = original + axial.Value
        try:
            return super().areaOpShapes(obj)
        finally:
            obj.FinalDepth = original

    def execute(self, obj):
        # Path.Op.Base.execute's own docstring says "do not overwrite!" -- let it build the
        # correct, normal (straight-plunge) toolpath first, then post-process the result.
        result = super().execute(obj)

        finishingPasses = int(getattr(obj, "FinishingPasses", 0))
        if finishingPasses > 0 and obj.ExtraOffset.Value != 0:
            self._appendFinishingPasses(obj, finishingPasses)

        if getattr(obj, "RampType", "Plunge") == "Helix":
            self._applyHelixRampEntry(obj)
        return result

    def _appendFinishingPasses(self, obj, count):
        """Fusion's "Finishing Passes": extra wall-cleanup passes stepping the radial Stock
        to Leave down from its roughing value to 0 (the true wall), using the side of the
        tool. V1 scope: linear stepdown, optional single shared finish feedrate override.
        Not yet covered -- tracked in docs/ROADMAP.md: "Leads on all Finishing Passes",
        "Finishing Overlap", "Repeat Finishing Pass", and a distinct per-pass Stepover (this
        reuses the roughing StepOver for each finishing pass's own internal geometry, which
        doesn't matter much since each finishing pass is a single near-wall ring).

        Implementation: re-run the exact same, already-correct execute() pipeline once per
        pass with ExtraOffset temporarily stepped down -- not a new toolpath algorithm --
        and concatenate the resulting commands. obj.ExtraOffset is restored to its original
        (roughing) value before returning, the same restore-after pattern areaOpShapes uses
        for AxialStockToLeave.
        """
        roughingCommands = list(obj.Path.Commands)
        originalOffset = obj.ExtraOffset.Value
        finishFeed = getattr(obj, "FinishFeedrate", None)
        finishFeedValue = finishFeed.Value if finishFeed else 0.0

        allCommands = list(roughingCommands)
        try:
            for i in range(1, count + 1):
                obj.ExtraOffset = originalOffset * (1 - i / count)
                super().execute(obj)
                passCommands = list(obj.Path.Commands)
                if finishFeedValue > 0:
                    passCommands = [self._withFeedOverride(c, finishFeedValue) for c in passCommands]
                allCommands += passCommands
        finally:
            obj.ExtraOffset = originalOffset

        obj.Path = Path.Path(allCommands)
        obj.CycleTime = PathOp.getCycleTimeEstimate(obj)
        self.job.Proxy.getCycleTime()

    def _withFeedOverride(self, cmd, feed):
        if cmd.Name not in ("G1", "G01", "G2", "G02", "G3", "G03"):
            return cmd
        params = dict(cmd.Parameters)
        params["F"] = feed
        return Path.Command(cmd.Name, params)

    def _applyHelixRampEntry(self, obj):
        if not obj.Path or not obj.Path.Commands:
            return
        cmds = obj.Path.Commands
        found = self._findFirstPlunge(cmds)
        if found is None:
            return
        plungeIdx, start, end = found

        radius = self._helixRampRadius(obj)
        rampCmds = self._buildHelixRampCommands(
            start, end, radius, obj.RampAngle.Value, obj.MaxRampStepdown.Value
        )
        if not rampCmds:
            return

        newCmds = list(cmds[:plungeIdx]) + rampCmds + list(cmds[plungeIdx + 1 :])
        obj.Path = Path.Path(newCmds)
        # The cycle-time estimate was already computed by super().execute(obj) against the
        # shorter straight-plunge path -- recompute it now that the path is longer, and
        # refresh the Job-level total the same way the base execute() does.
        obj.CycleTime = PathOp.getCycleTimeEstimate(obj)
        self.job.Proxy.getCycleTime()

    def _helixRampRadius(self, obj):
        """Resolve the actual helix radius from HelicalRampDiameter/MinimumRampDiameter.

        SAFETY CAVEAT (flagged in PR #1 review, tracked in docs/ROADMAP.md): this value is
        NOT checked against the pocket's actual boundary or islands -- we don't have that
        geometry at this post-process stage (see module docstring). On a small pocket, a
        too-large helix can swing the cutter into a wall. This is a user-adjustable value a
        human must size sensibly for their geometry, not an automatically pocket-aware or
        safety-verified one. Real fix (rejecting Helix when nothing fits) needs the pocket's
        2D shape available here, which it currently isn't."""
        target = obj.HelicalRampDiameter.Value
        if target <= 0:
            target = self.tool.Diameter.Value * 1.5
        minimum = obj.MinimumRampDiameter.Value
        if minimum > 0:
            target = max(target, minimum)
        return target / 2.0

    def _findFirstPlunge(self, cmds):
        """Return (index, start, end) for the first straight vertical plunge (G1, same X/Y
        as the resolved modal position, Z strictly decreasing), or None if not found.

        FreeCAD omits X/Y/Z from a command when it doesn't change from the previous one
        (modal G-code) -- e.g. a retract is often just `G0 {"Z": ...}` with no X/Y at all.
        `start`/`end` are resolved from the running last-known position, not read directly
        off the matched commands' own (possibly incomplete) Parameters."""
        lastX = lastY = lastZ = None
        for i, cmd in enumerate(cmds):
            p = cmd.Parameters
            x = p.get("X", lastX)
            y = p.get("Y", lastY)
            z = p.get("Z", lastZ)
            if (
                cmd.Name in ("G1", "G01")
                and lastX is not None
                and x is not None
                and y is not None
                and z is not None
                and abs(x - lastX) < 1e-6
                and abs(y - lastY) < 1e-6
                and z < lastZ - 1e-6
            ):
                return i, FreeCAD.Vector(lastX, lastY, lastZ), FreeCAD.Vector(x, y, z)
            lastX, lastY, lastZ = x, y, z
        return None

    def _buildHelixRampCommands(self, start, end, radius, rampAngleDeg, maxStepdown=0.0):
        """Build a helix descending from `start` to `end` (same X/Y, start.z > end.z) as
        directly-sampled G1 segments, plus a short closing move back to `end`'s exact X/Y
        so the rest of the already-generated toolpath still connects correctly.

        The helix circles a center point offset from the entry point by `radius`, so the
        entry point itself sits exactly on the circle at angle 0 -- the tool starts cutting
        from right where the original straight plunge was, just descending on a spiral
        instead of straight down.

        `maxStepdown`, if positive, caps the descent per revolution (Fusion's "Maximum Ramp
        Stepdown" -- constrains tool load during full-width ramping cuts) by using more,
        shallower revolutions instead of what RampAngle alone would produce.
        """
        height = start.z - end.z
        if height <= 0 or radius <= 0:
            return None
        rampAngle = math.radians(max(0.1, min(89.0, rampAngleDeg)))
        pitch = (2 * math.pi * radius) * math.tan(rampAngle)
        if pitch <= 0:
            return None
        if maxStepdown > 0:
            pitch = min(pitch, maxStepdown)
        totalAngle = (height / pitch) * 2 * math.pi

        center = FreeCAD.Vector(start.x - radius, start.y, 0)
        segmentsPerTurn = 36  # 10-degree steps
        numSegments = max(4, round(totalAngle / (2 * math.pi) * segmentsPerTurn))

        cmds = []
        for i in range(1, numSegments + 1):
            t = i / numSegments
            angle = t * totalAngle
            x = center.x + radius * math.cos(angle)
            y = center.y + radius * math.sin(angle)
            z = start.z - t * height
            cmds.append(Path.Command("G1", {"X": x, "Y": y, "Z": z, "F": self.vertFeed}))

        last = cmds[-1].Parameters
        if abs(last["X"] - end.x) > 1e-4 or abs(last["Y"] - end.y) > 1e-4:
            cmds.append(Path.Command("G1", {"X": end.x, "Y": end.y, "Z": end.z}))
        return cmds


def Create(name, obj=None, parentJob=None):
    """Create(name) ... creates and returns a CAM Studio Pocket operation."""
    if obj is None:
        obj = FreeCAD.ActiveDocument.addObject("Path::FeaturePython", name)
    obj.Proxy = ObjectPocket(obj, name, parentJob)
    return obj

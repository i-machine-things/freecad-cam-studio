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
3. "Lead-In"/"Lead-Out" (also Fusion's Linking tab, Linear type only):
   a separate feature from ramping -- it shifts the plunge's own XY
   target backward off the true path by the lead distance, then adds a
   horizontal approach move at cutting feed into the true start (mirror
   at the tail for lead-out), so the tool is already moving in the cut
   direction before it reaches full engagement. Mutually exclusive with
   RampType=Helix for now (see execute()). See _applyLeadInOut's
   docstring for the full V1 scope statement.
"""

import math

import FreeCAD
import Part
from PySide.QtCore import QT_TRANSLATE_NOOP

import Path
import Path.Op.Base as PathOp
import Path.Op.PocketBase as PathPocketBase
import Path.Op.PocketShape as PathPocketShape


class ObjectPocket(PathPocketShape.ObjectPocket):
    # Hard ceilings on helix ramp generation regardless of requested RampAngle/MaxRampStepdown
    # -- see _buildHelixRampCommands. MAX_RAMP_REVOLUTIONS bounds the actual spiral geometry
    # (the thing that matters physically); MAX_RAMP_SEGMENTS is a secondary sample-count safety
    # net that should rarely bind once revolutions are already bounded. 50 revolutions is
    # already far more than any real single-entry ramp needs.
    MAX_RAMP_REVOLUTIONS = 50
    MAX_RAMP_SEGMENTS = 2000

    # Slack (mm) allowed when checking an added entry/exit move's swept cutter area against
    # the pocket -- see _sweptAreaFits. The stock toolpath itself legitimately runs the
    # cutter tangent to the walls, so an exact-radius check would reject on numerical noise.
    FIT_TOLERANCE = 0.01
    # Directions (radians, from the plunge point toward the helix center) tried in order
    # when placing a helix ramp. pi first: the original fixed placement, so a helix that
    # already fit keeps exactly the same output.
    HELIX_CENTER_DIRECTIONS = tuple(
        math.pi * k / 4.0 for k in (4, 0, 2, 6, 3, 5, 1, 7)
    )

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
        if not hasattr(obj, "UseLeadInOut"):
            obj.addProperty(
                "App::PropertyBool",
                "UseLeadInOut",
                "Pocket",
                QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Enable Lead-In/Lead-Out moves (Linear type only -- see "
                    "docs/ROADMAP.md for the arc/radius type). Ignored when Ramp Type is "
                    "Helix.",
                ),
            )
            obj.UseLeadInOut = False
        if not hasattr(obj, "LeadInDistance"):
            obj.addProperty(
                "App::PropertyDistance",
                "LeadInDistance",
                "Pocket",
                QT_TRANSLATE_NOOP("App::Property", "Linear Lead-In distance"),
            )
            obj.LeadInDistance = 0
        if not hasattr(obj, "SameAsLeadIn"):
            obj.addProperty(
                "App::PropertyBool",
                "SameAsLeadIn",
                "Pocket",
                QT_TRANSLATE_NOOP("App::Property", "Use the Lead-In distance for Lead-Out too"),
            )
            obj.SameAsLeadIn = True
        if not hasattr(obj, "LeadOutDistance"):
            obj.addProperty(
                "App::PropertyDistance",
                "LeadOutDistance",
                "Pocket",
                QT_TRANSLATE_NOOP(
                    "App::Property", "Linear Lead-Out distance (ignored if Same as Lead-In)"
                ),
            )
            obj.LeadOutDistance = 0

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
        # Base.execute returns early *without* assigning obj.Path (missing/zero tool
        # controller, invalid base/stock) or with a placeholder path (inactive op). In all of
        # those cases it never reaches `self.commandlist = []`, so obj.Path is not a fresh
        # toolpath and must not be post-processed -- re-running the lead/ramp steps on the
        # previous, already post-processed path would shift and re-insert moves again on
        # every recompute (CodeRabbit, PR #1).
        self.commandlist = None
        result = super().execute(obj)
        if self.commandlist is None:
            return result

        finishingPasses = int(getattr(obj, "FinishingPasses", 0))
        if finishingPasses > 0 and obj.ExtraOffset.Value != 0:
            self._appendFinishingPasses(obj, finishingPasses)

        rampType = getattr(obj, "RampType", "Plunge")
        if rampType == "Helix":
            self._applyHelixRampEntry(obj)
        elif getattr(obj, "UseLeadInOut", False):
            # Mutually exclusive with Helix for now -- see _applyLeadInOut's docstring.
            self._applyLeadInOut(obj)
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

        KNOWN INEFFICIENCY (flagged in PR #1 review, "Heavy lift" -- correctly deferred, not a
        correctness bug): each pass reruns the *entire* clearing pattern at its new offset, not
        just the remaining wall band. On a large pocket this means repeated full-area travel at
        finish feed for every pass instead of a single boundary-only profile pass per step. The
        output is correct, just slower than an ideal implementation that computed just the
        remaining wall band/boundary profile directly -- tracked in docs/ROADMAP.md as a real
        follow-up, not something to silently leave undocumented.
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

    @staticmethod
    def _withFeed(params, feed):
        """Add F to `params` only when the tool controller actually has a feed set. The
        stock generator omits F entirely for an unset (0) feed; emitting an explicit F0 on
        just our added moves would be inconsistent with their neighbors and is a hard
        error or a stall on some controllers."""
        if feed and feed > 0:
            params["F"] = feed
        return params

    def _applyHelixRampEntry(self, obj):
        if not obj.Path or not obj.Path.Commands:
            return
        cmds = obj.Path.Commands
        found = self._findFirstPlunge(cmds)
        if found is None:
            return
        plungeIdx, start, end = found

        placement = self._fitHelixRamp(obj, end)
        if placement is None:
            Path.Log.warning(
                "%s: no helix ramp between the Helical Ramp Diameter and the Minimum Ramp "
                "Diameter fits inside the pocket at the entry point -- keeping the straight "
                "plunge. Reduce the ramp diameters or use a smaller tool.\n" % obj.Label
            )
            return
        radius, centerAngle = placement
        rampCmds = self._buildHelixRampCommands(
            start, end, radius, obj.RampAngle.Value, obj.MaxRampStepdown.Value, centerAngle
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

    def _helixRampDiameters(self, obj):
        """Candidate helix diameters, largest (preferred) first: HelicalRampDiameter (0 =
        auto, 1.5x tool diameter), then -- only if MinimumRampDiameter is set and smaller --
        evenly stepped down to MinimumRampDiameter. A minimum larger than the target raises
        the target to it, as before."""
        target = obj.HelicalRampDiameter.Value
        if target <= 0:
            target = self.tool.Diameter.Value * 1.5
        minimum = obj.MinimumRampDiameter.Value
        if minimum >= target:
            return [minimum]
        if minimum <= 0:
            return [target]
        steps = 4
        return [target - (target - minimum) * i / steps for i in range(steps + 1)]

    def _fitHelixRamp(self, obj, entry):
        """Return (radius, centerAngle) for the first helix that fits inside the pocket at
        `entry` (the plunge's landing point), or None if none does.

        Pocket-geometry-aware (closes the PR #1 review finding that an unchecked helix can
        swing the cutter into a wall or island on a small pocket): the disc the cutter
        sweeps -- helix radius + tool radius + radial Stock to Leave, around the helix
        center -- must lie inside the pocket's removal solid. Tries each candidate diameter
        (largest first) in each of HELIX_CENTER_DIRECTIONS around the entry point. Checking
        the full disc rather than the annulus actually swept is deliberately conservative:
        it also refuses to spiral around an island smaller than the helix's inner bore."""
        clearance = self.tool.Diameter.Value / 2.0 + obj.ExtraOffset.Value
        for diameter in self._helixRampDiameters(obj):
            radius = diameter / 2.0
            if radius <= 0:
                continue
            for centerAngle in self.HELIX_CENTER_DIRECTIONS:
                center = (
                    entry.x + radius * math.cos(centerAngle),
                    entry.y + radius * math.sin(centerAngle),
                )
                if self._sweptAreaFits([center], radius + clearance, entry.z):
                    return radius, centerAngle
        return None

    def _sweptAreaFits(self, points, radius, z):
        """True if a disc of `radius` swept along the straight XY segments joining `points`
        (a single point = just the disc) stays inside one of the pocket's removal solids
        at height `z`.

        The removal solids are the ones PocketShape.areaOpShapes built for this very
        execute() (upstream keeps them on `self.removalshapes`): the exact volume the
        operation is allowed to cut, with walls as its sides and islands as holes through
        it. A thin slab of the swept area is cut against each solid; anything left over is
        cutter outside the pocket. `radius` must already include any radial Stock to Leave.
        Returns False (does not fit) when there is nothing to check against -- an unverified
        move is treated as unsafe, not waved through."""
        radius = max(radius - self.FIT_TOLERANCE, self.FIT_TOLERANCE)
        for tup in getattr(self, "removalshapes", None) or []:
            solid, isHole = tup[0], tup[1]
            if isHole or solid.isNull():
                continue
            bb = solid.BoundBox
            height = min(0.1, bb.ZLength / 2.0)
            if height <= 0:
                continue
            z0 = max(bb.ZMin, min(z, bb.ZMax - height))
            parts = self._sweptSlabParts(points, radius, z0, height)
            if all(part.cut(solid).Volume <= part.Volume * 1e-6 for part in parts):
                return True
        return False

    def _sweptSlabParts(self, points, radius, z0, height):
        """The swept area as simple solids (a cylinder per point, a box per segment) whose
        union is the sweep -- the union fits iff every part does, so no fuse is needed."""
        up = FreeCAD.Vector(0, 0, height)
        parts = [
            Part.makeCylinder(radius, height, FreeCAD.Vector(x, y, z0)) for x, y in points
        ]
        for (ax, ay), (bx, by) in zip(points, points[1:]):
            length = math.hypot(bx - ax, by - ay)
            if length < 1e-6:
                continue
            nx, ny = -(by - ay) / length * radius, (bx - ax) / length * radius
            corners = [
                FreeCAD.Vector(ax + nx, ay + ny, z0),
                FreeCAD.Vector(bx + nx, by + ny, z0),
                FreeCAD.Vector(bx - nx, by - ny, z0),
                FreeCAD.Vector(ax - nx, ay - ny, z0),
            ]
            parts.append(Part.Face(Part.makePolygon(corners + corners[:1])).extrude(up))
        return parts

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

    def _buildHelixRampCommands(
        self, start, end, radius, rampAngleDeg, maxStepdown=0.0, centerAngle=math.pi
    ):
        """Build a helix descending from `start` to `end` (same X/Y, start.z > end.z) as
        directly-sampled G1 segments, plus a short closing move back to `end`'s exact X/Y
        so the rest of the already-generated toolpath still connects correctly.

        The helix circles a center point offset from the entry point by `radius` in the
        `centerAngle` direction (chosen by _fitHelixRamp so the helix stays inside the
        pocket; default pi = toward -X), so the entry point itself sits exactly on the
        circle -- the tool starts cutting from right where the original straight plunge
        was, just descending on a spiral instead of straight down.

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

        # MaxRampStepdown has no lower bound on the property itself -- a tiny value (e.g.
        # 0.00001mm against a 10mm descent) would otherwise demand an astronomically large
        # totalAngle (millions of radians). CodeRabbit correctly flagged that capping only
        # numSegments below while leaving that huge totalAngle unchanged doesn't just make a
        # coarser helix -- each remaining sample's `angle = t * totalAngle` then jumps by
        # thousands of radians, producing a degenerate, effectively-random-looking zigzag
        # instead of a spiral. Clamp the revolution count itself (the physical quantity that
        # actually matters) before deriving numSegments from it, so the geometry stays a
        # well-formed spiral -- just steeper (more descent per turn) than requested -- at any
        # input. This also protects the same-shaped case of an extremely shallow RampAngle
        # over a deep profile, not just an extreme MaxRampStepdown.
        maxTotalAngle = self.MAX_RAMP_REVOLUTIONS * 2 * math.pi
        if totalAngle > maxTotalAngle:
            totalAngle = maxTotalAngle

        center = FreeCAD.Vector(
            start.x + radius * math.cos(centerAngle), start.y + radius * math.sin(centerAngle), 0
        )
        # Angular position of the entry point on the circle, as seen from the center.
        entryAngle = centerAngle + math.pi
        segmentsPerTurn = 36  # 10-degree steps
        numSegments = max(4, round(totalAngle / (2 * math.pi) * segmentsPerTurn))
        # Secondary safety net -- should rarely bind now that totalAngle itself is bounded
        # above, but keeps the same hard ceiling in place regardless.
        numSegments = min(numSegments, self.MAX_RAMP_SEGMENTS)

        cmds = []
        for i in range(1, numSegments + 1):
            t = i / numSegments
            angle = entryAngle + t * totalAngle
            x = center.x + radius * math.cos(angle)
            y = center.y + radius * math.sin(angle)
            z = start.z - t * height
            cmds.append(Path.Command("G1", self._withFeed({"X": x, "Y": y, "Z": z}, self.vertFeed)))

        last = cmds[-1].Parameters
        if abs(last["X"] - end.x) > 1e-4 or abs(last["Y"] - end.y) > 1e-4:
            cmds.append(Path.Command("G1", {"X": end.x, "Y": end.y, "Z": end.z}))
        return cmds

    def _applyLeadInOut(self, obj):
        """Fusion's Linking tab Lead-In/Lead-Out -- Linear type only (V1 scope; the arc/
        radius type -- Horizontal Lead Radius, Sweep Angle -- is a tracked follow-up, see
        docs/ROADMAP.md).

        Design note (why this isn't a simple post-insertion like the ramp/finishing-pass
        work above): a correct lead-in doesn't just add a move *after* the plunge lands on
        the true path start -- it moves the plunge's own XY target backward, off the true
        path, by the lead distance along the first cut move's own direction, then adds a
        horizontal approach move (at cutting feed) from that shifted point into the true
        start. That way the tool is already moving in the cut direction, at cutting feed,
        by the time it reaches the real path, instead of plunging directly into full
        engagement at a single point. Lead-out mirrors this at the tail: extend past the
        true end point along the last cut move's own direction, at cutting feed, before
        the final retract.

        V1 scope, stated plainly (same honesty as the Helix ramp above):
        - Only the operation's single first plunge / single final cutting move are
          treated -- same single-entry-point scope as the Helix ramp, not per-level or
          per-region.
        - Only a straight (G1) first/last cutting move is supported; if the first move
          after the plunge (or the last move before the final retract) is an arc (G2/G3),
          this is skipped rather than guessing a tangent direction.
        - Pocket-geometry-aware by rejection, not by adaptation: each lead's swept cutter
          area (tool radius + the radial Stock to Leave in force for that move) is checked
          against the pocket's walls and islands (_sweptAreaFits). A lead that does not
          fit is left out entirely, with a warning -- it is not shortened or re-aimed.
        """
        cmds = list(obj.Path.Commands)
        leadIn = max(0.0, obj.LeadInDistance.Value)
        sameAsLeadIn = bool(getattr(obj, "SameAsLeadIn", True))
        leadOut = leadIn if sameAsLeadIn else max(0.0, obj.LeadOutDistance.Value)

        toolRadius = self.tool.Diameter.Value / 2.0
        stockToLeave = obj.ExtraOffset.Value
        # The first plunge always belongs to the roughing pass. The last cutting move
        # belongs to the final finishing pass when finishing passes ran (see execute()),
        # and that pass cuts at the true wall -- no radial stock left.
        finished = int(getattr(obj, "FinishingPasses", 0)) > 0 and stockToLeave != 0
        leadInClearance = toolRadius + stockToLeave
        leadOutClearance = toolRadius + (0.0 if finished else stockToLeave)

        changed = False
        if leadIn > 0:
            newCmds = self._insertLeadIn(cmds, leadIn, leadInClearance)
            if newCmds is not None:
                cmds = newCmds
                changed = True
            else:
                self._warnLeadSkipped(obj, "Lead-In")
        if leadOut > 0:
            newCmds = self._insertLeadOut(cmds, leadOut, leadOutClearance)
            if newCmds is not None:
                cmds = newCmds
                changed = True
            else:
                self._warnLeadSkipped(obj, "Lead-Out")

        if changed:
            obj.Path = Path.Path(cmds)
            obj.CycleTime = PathOp.getCycleTimeEstimate(obj)
            self.job.Proxy.getCycleTime()

    def _warnLeadSkipped(self, obj, which):
        Path.Log.warning(
            "%s: %s left out -- it does not fit inside the pocket at that distance, or the "
            "adjacent move is not a straight cut it can be aligned to.\n" % (obj.Label, which)
        )

    def _insertLeadIn(self, cmds, leadIn, clearance):
        """Return `cmds` with a linear lead-in of length `leadIn` added at the first
        plunge, or None if it can't be added safely. `clearance` is the radius the cutter
        must keep clear around its center (tool radius + radial stock to leave)."""
        found = self._findFirstPlunge(cmds)
        if found is None:
            return None
        plungeIdx, start, end = found
        nextIdx = plungeIdx + 1
        if nextIdx >= len(cmds):
            return None
        nextCmd = cmds[nextIdx]
        if nextCmd.Name not in ("G1", "G01"):
            return None
        p = nextCmd.Parameters
        qx, qy = p.get("X", end.x), p.get("Y", end.y)
        dx, dy = qx - end.x, qy - end.y
        length = math.hypot(dx, dy)
        if length < 1e-6:
            return None
        dx, dy = dx / length, dy / length
        approachX, approachY = end.x - dx * leadIn, end.y - dy * leadIn
        if not self._sweptAreaFits([(approachX, approachY), (end.x, end.y)], clearance, end.z):
            return None

        # The tool has to be over the approach point *before* it starts descending, so every
        # rapid that positions it over the old plunge point has to move with it -- not just
        # the command right before the plunge. Stock output is e.g. `G0 X Y` (at clearance)
        # then `G0 X Y Z<safe>` then the plunge; a post-processed or hand-built path may
        # instead omit modal X/Y on the descent (`G0 X Y`, `G0 Z<safe>`). Walk back over the
        # whole run of rapids ending on the plunge point and retarget each one that carries
        # X/Y; Z-only ones need no change. Stop at the first move that goes anywhere else.
        posIdxs = []
        for i in range(plungeIdx - 1, -1, -1):
            cmd = cmds[i]
            if cmd.Name not in ("G0", "G00"):
                break
            params = cmd.Parameters
            if "X" not in params and "Y" not in params:
                continue
            if (
                abs(params.get("X", start.x) - start.x) > 1e-6
                or abs(params.get("Y", start.y) - start.y) > 1e-6
            ):
                break
            posIdxs.append(i)
        # Nothing to retarget means the tool reaches the plunge point some other way (e.g. a
        # feed move) -- not a layout this was designed or verified for, so decline instead
        # of leaving a diagonal descent.
        if not posIdxs:
            return None

        newCmds = list(cmds)
        for i in posIdxs:
            newCmds[i] = Path.Command(
                cmds[i].Name, dict(cmds[i].Parameters, X=approachX, Y=approachY)
            )
        # Shift the plunge's own target XY to the approach point, so the plunge itself
        # stays a straight vertical descent there instead of a diagonal move.
        plungeCmd = newCmds[plungeIdx]
        newCmds[plungeIdx] = Path.Command(
            plungeCmd.Name, dict(plungeCmd.Parameters, X=approachX, Y=approachY)
        )
        leadInMove = Path.Command(
            "G1", self._withFeed({"X": end.x, "Y": end.y, "Z": end.z}, self.horizFeed)
        )
        newCmds.insert(plungeIdx + 1, leadInMove)
        return newCmds

    def _insertLeadOut(self, cmds, leadOut, clearance):
        """Mirror of _insertLeadIn at the tail: extend past the true end point of the
        last cutting move, along that move's own direction, before the final retract.
        Returns None if it can't be added safely (see _insertLeadIn)."""
        lastCutIdx = None
        for i in range(len(cmds) - 1, -1, -1):
            if cmds[i].Name in ("G1", "G01", "G2", "G02", "G3", "G03"):
                lastCutIdx = i
                break
        if lastCutIdx is None or lastCutIdx == 0:
            return None
        lastCut = cmds[lastCutIdx]
        if lastCut.Name not in ("G1", "G01"):
            return None

        lastX = lastY = lastZ = None
        for cmd in cmds[:lastCutIdx]:
            p = cmd.Parameters
            lastX = p.get("X", lastX)
            lastY = p.get("Y", lastY)
            lastZ = p.get("Z", lastZ)
        p = lastCut.Parameters
        endX, endY, endZ = p.get("X", lastX), p.get("Y", lastY), p.get("Z", lastZ)
        if lastX is None or endX is None or lastY is None or endY is None:
            return None
        dx, dy = endX - lastX, endY - lastY
        length = math.hypot(dx, dy)
        if length < 1e-6:
            return None
        dx, dy = dx / length, dy / length
        exitX, exitY = endX + dx * leadOut, endY + dy * leadOut
        if endZ is None or not self._sweptAreaFits(
            [(endX, endY), (exitX, exitY)], clearance, endZ
        ):
            return None

        leadOutMove = Path.Command(
            "G1", self._withFeed({"X": exitX, "Y": exitY, "Z": endZ}, self.horizFeed)
        )
        return cmds[: lastCutIdx + 1] + [leadOutMove] + cmds[lastCutIdx + 1 :]


def Create(name, obj=None, parentJob=None):
    """Create(name) ... creates and returns a CAM Studio Pocket operation."""
    if obj is None:
        obj = FreeCAD.ActiveDocument.addObject("Path::FeaturePython", name)
    obj.Proxy = ObjectPocket(obj, name, parentJob)
    return obj

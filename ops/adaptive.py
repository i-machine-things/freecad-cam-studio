"""CAM Studio's 2D Adaptive Roughing operation proxy.

Subclasses FreeCAD's own Adaptive operation (`Path.Op.Adaptive.PathAdaptive`, never patched):
its geometry gathering, libarea's adaptive solver and its G-code generation all run unchanged.
CAM Studio adds what 2D Offset Roughing already has and FreeCAD's Adaptive can take without
changing its toolpath:

- per-operation Feed & Speed (ops/feeds.py), with Ramp Feedrate / Ramp Spindle Speed applied
  to the helix entries upstream generates;
- Operation Type pinned to Clearing: this is a roughing operation. FreeCAD's Profiling mode
  is a contour, which belongs to a contour operation.

Everything else (Heights, Linking, ramp types, leads, Retract Height...) is FreeCAD's adaptive
behavior for now; see the parity map in docs/ROADMAP.md.
"""

import FreeCAD
import Path
import Path.Op.Adaptive as PathAdaptive

from ops.feeds import FeedAndSpeed


class ObjectAdaptive(FeedAndSpeed, PathAdaptive.PathAdaptive):
    # Upstream's adaptive has no lead moves, so no Lead-In / Lead-Out feeds.
    FEEDS = ("CuttingFeedrate", "RampFeedrate", "PlungeFeedrate")

    # Comment lines upstream's GenerateGCode writes around each helix entry: the helix runs
    # from the first to the second.
    HELIX_START = "(Helix to depth"
    HELIX_END = "(Adaptive - depth"

    def initOperation(self, obj):
        super().initOperation(obj)
        self._initCamStudio(obj)

    def opOnDocumentRestored(self, obj):
        super().opOnDocumentRestored(obj)
        self._initCamStudio(obj)

    def _initCamStudio(self, obj):
        self.initFeedProperties(obj)
        if hasattr(obj, "OperationType"):
            if obj.OperationType != "Clearing":
                obj.OperationType = "Clearing"
            obj.setEditorMode("OperationType", 1)  # read-only

    def opSetDefaultValues(self, obj, job):
        super().opSetDefaultValues(obj, job)
        obj.OperationType = "Clearing"

    def execute(self, obj):
        # Same guard as ops/pocket.py: Base.execute returns early without a fresh toolpath in
        # several cases; only post-process a path this execute actually produced.
        self.commandlist = None
        result = super().execute(obj)
        if self.commandlist is None:
            return result
        if hasattr(obj, "RampFeedrate"):
            self.applyRampFeedAndSpeed(obj)
        if hasattr(obj, "SpindleSpeed"):
            self.applySpindleSpeed(obj)
        return result

    def applyRampFeedAndSpeed(self, obj):
        """Upstream feeds its helix entries at the vertical feed (the op's Plunge Feedrate,
        see FeedAndSpeed.opExecute). Give the helix's feed-down moves the Ramp Feedrate, and
        run the descent at the Ramp Spindle Speed when it differs: switched on at the helix,
        back to the op's speed at the first horizontal cutting move (upstream follows each
        descent with a spiral-out and a circle at depth, at cutting feed)."""
        plunge = self.vertFeed
        cutting = self.horizFeed
        ramp = obj.RampFeedrate.Value
        rampRpm = getattr(obj, "RampSpindleSpeed", obj.SpindleSpeed)
        switch = rampRpm > 0 and abs(rampRpm - obj.SpindleSpeed) > 1e-9
        toRamp = self.spindleCommand(rampRpm) if switch else None
        toCut = self.spindleCommand(obj.SpindleSpeed) if switch else None
        out = []
        inHelix = False
        atRampSpeed = False

        def backToCutting():
            nonlocal atRampSpeed
            if atRampSpeed:
                out.append(toCut)
                atRampSpeed = False

        for cmd in obj.Path.Commands:
            if cmd.Name.startswith(self.HELIX_START):
                inHelix = True
                out.append(cmd)
                if toRamp is not None and toCut is not None:
                    out.append(toRamp)
                    atRampSpeed = True
                continue
            if cmd.Name.startswith(self.HELIX_END):
                inHelix = False
                backToCutting()
            feed = cmd.Parameters.get("F")
            if inHelix and feed is not None:
                if abs(feed - plunge) < 1e-9:
                    params = dict(cmd.Parameters)
                    params["F"] = ramp
                    cmd = Path.Command(cmd.Name, params)
                elif abs(feed - cutting) < 1e-9:
                    backToCutting()
            out.append(cmd)
        backToCutting()
        obj.Path = Path.Path(out)


def Create(name, obj=None, parentJob=None):
    """Create(name) ... creates and returns a CAM Studio 2D Adaptive Roughing operation."""
    if obj is None:
        obj = FreeCAD.ActiveDocument.addObject("Path::FeaturePython", name)
    obj.Proxy = ObjectAdaptive(obj, name, parentJob)
    obj.Proxy.loadFeedsFromTool(obj)
    return obj

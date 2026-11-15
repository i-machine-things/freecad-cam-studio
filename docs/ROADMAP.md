# Roadmap

Full breadth (2.5D milling, 3D, turning, simulation) is the target. Phased so there's a working,
checkable result at the end of each phase rather than one long build with nothing usable until
the end.

## Parity standard: "100%" means every Fusion option exists here

Per-operation UI/UX must be fully done — every option Fusion 360 exposes for that operation has a
working CAM Studio equivalent — before moving to the next operation. Where FreeCAD's stock
`Path.Op.*` class has no property/behavior for a Fusion option, that's not a gap to document and
skip: it's a feature to build. The sanctioned way to build it: subclass the upstream Proxy class
in `ops/<name>.py` (never patch `Path/Op/*.py` in place) and hook its *documented* extension
points — e.g. `initPocketOp` to add a property, `_customDepthParams` to adjust computed depths.
`ops/pocket.py`'s `AxialStockToLeave` is the first example of this pattern (see below). A gap only
stays a documented gap, not a built feature, when it's genuinely out of scope for this layer (e.g.
Autodesk's specific patented toolpath algorithm internals — see Non-goals).

## Phase 1 — 2.5D milling foundation (current)
Confirmed against FreeCAD's own upstream source (see [ARCHITECTURE.md](ARCHITECTURE.md)): the
data/execution layer already exists (`Path.Main.Job.ObjectJob`, `Path.Op.MillFace/Pocket/Profile/
Adaptive/Drilling`). Builds as a new Gui layer wherever FreeCAD's existing properties/behavior
already cover a Fusion option; where they don't (see parity standard above), adds small, targeted
subclasses in `ops/` rather than a whole new toolpath engine.
- [ ] Finish the behavior spec: Face, Pocket, Contour, Adaptive Clearing, Drilling, Setup/Stock/WCS
- [x] Map each spec'd operation onto FreeCAD's existing CAM-module operation classes (done —
      see ARCHITECTURE.md's class list)
- [x] Spike: how an external addon registers a replacement `TaskPanel` for an existing op's
      edit/double-click behavior (resolved — see ARCHITECTURE.md's "Resolved" section: per-instance
      `ViewObject.Proxy`/`CommandResources`, no core patch needed)
- [x] First working command: `CamStudio_CreateJob` ("New Setup") — creates a real FreeCAD CAM Job
      via our own toolbar entry, reusing `Path.Main.Gui.Job.Create` and stock CAM's own Job
      ViewProvider unmodified (Job-level editing isn't part of this project's scope, only
      operation TaskPanels are)
- [x] First operation command: `CamStudio_Pocket` — creates the same `PocketShape.ObjectPocket`
      object stock CAM's "Pocket Shape" command creates, via our own toolbar entry/icon
- [x] CAM Studio's own Pocket edit dialog (`pages/pocket.py`) — built from scratch (no FreeCAD
      `.ui` resource reused), grouped and labeled to match Fusion's 2D Pocket dialog terminology
      ("Tool" / "Passes" / "Other Options", "Pocket Pattern", "Cutting Direction", "Stepover")
      instead of FreeCAD's own layout. Shared Heights/Depths/Geometry pages are still the generic
      FreeCAD ones (their terminology already closely matches Fusion's Heights tab, so no gap to
      close there)
- [x] Pocket: Radial + Axial Stock to Leave (`ops/pocket.py`'s `ObjectPocket` subclass) — stock
      CAM's `PocketShape` only has one (`ExtraOffset`, radial). Added `AxialStockToLeave` as a real
      new property wired into `_customDepthParams` (an officially documented extension point),
      verified to actually shift the computed toolpath depth, not just hold a UI value
- [x] Pocket: ramp entry, Helix type (Fusion's Linking tab) — `PocketShape` had **no properties or
      toolpath support for this at all** (confirmed by reading `Path.Op.Area.py`). Added
      `RampType`/`RampAngle` to `ops/pocket.py`; `execute()` wraps the base class's (never
      overwrites it — its own docstring says "do not overwrite!") and post-processes the first
      straight plunge into a directly-sampled spiral descent. Verified: monotonic Z descent,
      correct feed-rate propagation from the real tool controller, correct landing position.
      **V1 scope, stated plainly**: only the operation's very first plunge is ramped. **Correction
      from Autodesk's authoritative reference page** (not a forum post this time): Fusion actually
      has **seven** Ramp Type options, not five — Plunge, Plunge Outside Stock, Zig-Zag, Profile,
      Smooth Profile, Predrill, Helix. Only Helix is built. Added (next commit) `HelicalRampDiameter`
      / `MinimumRampDiameter` (user-adjustable now, default 1.5x tool diameter) and
      `MaxRampStepdown`, but **these are not pocket-geometry-aware** — CodeRabbit correctly flagged
      (PR #1) that a helix sized without checking the actual pocket boundary/islands can swing the
      cutter into a wall on a small pocket. Real fix needs the pocket's 2D shape at the
      post-process stage (not available there today) to check the swept area against walls/islands
      and reject Helix if nothing fits — a "Heavy lift," correctly deferred, not silently skipped;
      until then this is a user-adjustable-but-unchecked value, documented as such in the code.
      Still missing: **Ramp Clearance Height**, **Ramp Taper Angle** (conical helix, distinct from
      Ramping Angle), and per-level/per-region ramping (every plunge, not just the first).
- [x] Tool selection: Fusion's "Select..." tool-library browser, added alongside the existing
      inline combo (`widgets/tool_picker.py`, cross-cutting — any operation page can use it, used
      first by Pocket). Reuses FreeCAD's own existing `Path.Tool.toolbit.ui.selector.ToolBitSelector`
      dialog and `Path.Tool.Controller.Create` factory (the same building blocks stock CAM's own
      Job-creation dialog uses) rather than building a tool-library browser from scratch. Verified
      via a real button click driving the actual modal dialog, not just the underlying logic.
- [ ] Contour/Profile: cutter compensation ("Compensation Type" — Off / In Computer / In Control /
      Wear / Inverse Wear, per [Autodesk's reference](https://help.autodesk.com/cloudhelp/ENU/Fusion-CAM/files/GUID89C78618-20FD-4A82-BFB4-BC66AFE417DD.htm)).
      Confirmed this lives on **2D Contour's** Passes tab specifically, not 2D Pocket's — tracked
      against the future Contour/Profile operation, not Pocket. FreeCAD's `Path.Op.Profile` already
      has a partial related property ("Make True, if using Cutter Radius Compensation") to build
      from — likely a smaller gap than ramps were, but not yet verified against the 4-mode richness
      Fusion exposes (In Control/Wear/Inverse Wear all emit G41/G42, which is a post-processor-level
      concern too, not just the toolpath object)
- [ ] Pocket Tool tab: inline Speeds & Feeds editing. Fusion's full field list (confirmed via
      [Autodesk's reference](https://help.autodesk.com/cloudhelp/ENU/Fusion-CAM/files/GUID67DC60DE-EE42-4BC4-B50D-B28D938D146E.htm)):
      Spindle Speed, Surface Speed, Ramp Spindle Speed, Cutting Feedrate, Feed per Tooth,
      Lead-In/Lead-Out/Transition/Ramp/Plunge Feedrates, Feed per Revolution — all editable inline
      on the operation. CAM Studio currently requires leaving the op dialog to edit the separate
      ToolController object for any of this. Flagged directly by Allan from his own Fusion install
- [ ] Pocket Geometry tab: large gap vs. the shared FreeCAD Base Geometry page we currently reuse.
      Confirmed via Autodesk's reference: Closed/Open/Standing-Boss machining modes (not one
      generic selection), Extension Method (Tangent/Closest boundary/Parallel) for closing open
      pockets, Stock Contours (bound the cut area by stock/sketch/edges, not just the raw
      selection), per-contour clickable cut-direction arrows, Rest Machining sub-parameters
      (simulated previous Tool Diameter + Corner Radius, not just our on/off toggle), and a full
      **Tool Orientation** system (Setup WCS / Model / explicit axis selection / named coordinate
      system, each with its own Origin option) letting one operation cut at an angle to the
      Setup's WCS — this last one is a substantial feature on its own, not a quick field add
- [ ] Pocket Passes tab: a full **finishing-pass subsystem** Fusion exposes that we don't have at
      all — enable toggle, Number of Finishing Passes, per-pass Stepover, "Leads on all Finishing
      Passes," Finish Feedrate, Repeat Finishing Pass, Finishing Overlap. Also missing: Minimum
      Cutting Radius (corner blending), Both Ways (alternating climb/conventional with its own
      Optimal-Load/Feedrate), Use Morphed Spiral Machining, Allow Stepover Cusps, Use Even
      Stepdowns, Order by Depth, Order by Step, Preserve Order, general Smoothing + Smoothing
      Deviation, and a **Feed Optimization** corner-slowdown subsystem (Maximum Directional
      Change, Reduced Feed Radius/Distance/Feedrate, Only Inner Corners)
- [ ] Pocket Passes tab: **negative Stock to Leave** (radial and axial) for electrode/spark-gap
      machining — Fusion explicitly supports negative values here; not yet verified whether our
      `ExtraOffset`/`AxialStockToLeave` properties and the underlying area-clearing call tolerate
      negative input correctly or would silently misbehave
- [ ] Pocket Linking tab: **Lead-In/Lead-Out is a separate feature from ramping**, easy to conflate
      with the ramp work already done — it's the approach/retract arc or line around the cut path
      itself (Horizontal/Vertical Lead Radius, Sweep Angle, Linear Lead Distance, Perpendicular,
      "Same as Lead-In"), not the plunge-entry strategy. Also missing: High Feedrate Mode (several
      rapid-vs-feed-move output strategies) + High Feedrate, Allow Rapid Retract, Safe Distance,
      Maximum Stay-Down Distance (we have the `KeepToolDown` toggle but not this limit), Lift
      Height
- [ ] Pocket Heights tab: FreeCAD's shared Heights+Depths pages give Clearance/Safe/Start/Final;
      Fusion's Clearance/Retract/Feed/Top/Bottom reads as having a distinct "Feed height" concept
      that may not map 1:1 — needs verification, not an assumed match
- [ ] Pocket Passes tab: Chip Thinning (feed-rate compensation when radial engagement/stepover is
      low, to maintain target chip load). Flagged directly by Allan from his own Fusion install —
      not independently confirmed as a named toggle via public-source research (general technique
      is well documented, e.g. Autodesk's "Constant Cutter Forces" blog post, but the exact current
      Fusion UI label wasn't found), so verify the exact field/behavior against the real dialog
      before implementing rather than guessing at a checkbox name
- [x] All CAM Studio dialogs: collapsible sections matching Fusion's accordion-style
      disclosure-triangle groups (`widgets/collapsible.py`'s `CollapsibleSection`, cross-cutting —
      used by every operation page, not just Pocket, same as `widgets/tool_picker.py`). Verified
      both expanded and collapsed states render and reflow correctly via a real toggle-button
      click, not just construction
- [ ] Build the Setup → Operations tree UI (PySide/Qt) matching the workflow sequence from the spec
- [ ] Parameter dialogs for the remaining Phase 1 operations (Face, Contour, Adaptive, Drilling),
      each held to the same 100%-parity standard as Pocket above
- [ ] Check: run the same part through this workbench and FreeCAD's stock CAM workbench, confirm
      both read/edit the same document objects correctly, then compare resulting toolpath
      shape/step sequence against the spec's description (not against Fusion's binary output)

## Phase 2 — 3D operations
Parallel, Scallop, and other surface-finishing strategies. Spec and implement once Phase 1's UI
scaffolding exists, since these mostly add new operation types to the same tree/dialog structure.

## Phase 3 — Turning
Separate workflow (lathe setup, OD/ID turning, facing, grooving, threading) — FreeCAD's Path
workbench has some turning support already; spec against that plus public Fusion turning docs.

## Phase 4 — Simulation
Toolpath playback/verification view. Likely the largest net-new engineering effort since it's not
just a UI layer over existing Path operations.

## Non-goals
- Literal pixel-identical UI, copied icons/strings, or Autodesk asset reuse — see
  [CLEAN-ROOM.md](CLEAN-ROOM.md).
- Matching Autodesk's specific internal toolpath algorithms where those may be patented (adaptive
  clearing and similar) — implement against published machining literature and FreeCAD's existing
  algorithms instead.

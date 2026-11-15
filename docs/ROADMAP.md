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
      CAM's `PocketShape` only has one (`ExtraOffset`, radial). Added `AxialStockToLeave`, wired
      into `_customDepthParams` (an officially documented extension point) **and** `areaOpShapes`
      (not documented, but necessary — `_customDepthParams` only adjusts the Z-level iteration
      list; `PocketShape.areaOpShapes` reads `obj.FinalDepth.Value` directly to build the actual
      removal-shape geometry, independent of that list). The first version only touched
      `_customDepthParams` and was verified only against that function's own return value, not
      the real generated toolpath — it silently did nothing to the actual cut depth. Caught during
      later work on a different feature by checking real `Path.Commands` Z values end-to-end, not
      by trusting the earlier "verified" claim. Fixed by having `areaOpShapes` temporarily set
      `obj.FinalDepth` to the adjusted value for that one synchronous call, then restore it (safe
      even though `FinalDepth` is normally expression-driven — verified empirically that a direct
      assignment doesn't break the expression, which simply reasserts on the next real recompute).
      Confirmed via real toolpath Z inspection that both positive and negative values produce the
      correct cut depth; electrode-specific negative-value edge cases are a separate, still-open
      item below ("negative Stock to Leave").
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
      `MaxRampStepdown`. **Now pocket-geometry-aware** (CodeRabbit flagged on PR #1 that an unchecked
      helix can swing the cutter into a wall on a small pocket; first deferred on the belief that
      the pocket shape wasn't available at the post-process stage — it is: upstream leaves this
      execute's removal solids on `self.removalshapes`). `_fitHelixRamp` checks the disc the
      cutter sweeps (helix radius + tool radius + radial Stock to Leave) against those solids —
      walls are their sides, islands are holes through them — trying each diameter from
      `HelicalRampDiameter` stepped down to `MinimumRampDiameter`, in 8 directions around the
      entry point (the original fixed direction first, so a helix that already fit is unchanged).
      If nothing fits, the straight plunge is kept and a warning is logged. Verified on real
      `Path.Commands` against an independent 2D distance-to-wall/island check, with the pre-fix
      code as a negative control.
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
- [x] Pocket Passes tab: **finishing passes** (Number of Finishing Passes + Finish Feedrate).
      `ops/pocket.py`'s `_appendFinishingPasses` re-runs the same already-correct `execute()`
      pipeline once per pass with `ExtraOffset` linearly stepped down to 0 (the true wall), then
      concatenates the resulting commands and overrides their feed if `FinishFeedrate` is set —
      not a new toolpath algorithm, reuse of the proven one. `FinishFeedrate`'s UI field uses a
      plain `QDoubleSpinBox` with explicit mm/min conversion (see CODING_NOTES.md — the natural
      `Gui::QuantitySpinBox` approach silently displays mm/s instead, a real 60x unit-confusion
      risk for a feed rate, not merely cosmetic). Verified end-to-end: command count scales
      correctly, finish feed only applies to the appended finishing commands, `ExtraOffset`
      restored correctly, UI round-trips mm/min correctly. **Known inefficiency (PR #1 review,
      "Heavy lift," correctly deferred — not a correctness bug)**: each finishing pass reruns the
      *entire* clearing pattern at its new offset instead of generating just the remaining wall
      band/boundary profile, so a large pocket repeats full-area travel at finish feed per pass
      rather than one efficient boundary-only pass per step. Output is correct, just slower than
      an ideal implementation. **Not yet built**: per-pass Stepover,
      "Leads on all Finishing Passes," Repeat Finishing Pass, Finishing Overlap. Also missing: Minimum
      Cutting Radius (corner blending), Both Ways (alternating climb/conventional with its own
      Optimal-Load/Feedrate), Use Morphed Spiral Machining, Allow Stepover Cusps, Use Even
      Stepdowns, Order by Depth, Order by Step, Preserve Order, general Smoothing + Smoothing
      Deviation, and a **Feed Optimization** corner-slowdown subsystem (Maximum Directional
      Change, Reduced Feed Radius/Distance/Feedrate, Only Inner Corners)
- [x] Pocket Passes tab: **negative Stock to Leave** (radial and axial) for electrode/spark-gap
      machining — Fusion explicitly supports negative values here. Verified what the depth-fix
      work above checked: negative `ExtraOffset` and `AxialStockToLeave` both recompute without
      error and produce the correct, expected Z depth in real `Path.Commands` (e.g. `-0.5` axial
      correctly cuts to 9.5mm against a 10mm default). **Not verified**: electrode-specific edge
      cases Autodesk's own reference calls out (e.g. a negative radial value must stay less than
      the tool radius; with a ball/radius cutter, negative axial has its own corner-radius-based
      limit) — no input validation/clamping exists for these yet, so an extreme negative value
      could still produce a nonsensical or unsafe toolpath without any warning
- [x] Pocket Linking tab: **Lead-In/Lead-Out**, Linear type only. Built per the design note from
      scoping this (preserved below) rather than a quick post-insertion: `ops/pocket.py`'s
      `_insertLeadIn`/`_insertLeadOut` shift the plunge's own XY target backward (lead-in) or
      extend past the final cutting point forward (lead-out) along that move's own direction,
      then add a straight horizontal approach/exit move at cutting feed (`self.horizFeed`) —
      resolving direction from the real adjacent command, with FreeCAD's modal X/Y/Z omission
      handled the same way `_findFirstPlunge` already does. Verified against real generated
      `Path.Commands`: a 3mm Lead-In correctly shifted the plunge+positioning move by exactly
      3mm along the true first-cut direction and inserted one matching approach move; a 2mm
      Lead-Out (independent `LeadOutDistance`, `SameAsLeadIn=False`) correctly extended the final
      cut point by exactly 2mm along the last cut's own direction; command-count delta matched
      exactly (+2, one insert per end) against the same op with `UseLeadInOut=False`. UI
      enable/disable verified via real screenshots in both states, including the mutual-exclusion
      rule below.
      **Design note preserved from scoping (now implemented as described)**: a correct
      implementation isn't "insert an extra segment after the plunge lands" — the plunge itself
      needs to target a shifted *approach point* (offset backward along the first cut segment's
      direction by the lead distance), with the lead-in move then carrying the tool from that
      approach point into the real path at cutting feed. Treating it as a simple post-insertion
      (like the ramp/finishing-pass pattern) would have been an under-verified, potentially wrong
      toolpath — hence the extra design step before building it.
      **V1 scope, stated plainly**: only the operation's single first plunge / single final
      cutting move are treated (same single-entry-point scope as the Helix ramp, not per-level or
      per-region); only a straight (G1) first/last move is supported — an arc (G2/G3) there is
      skipped rather than guessing a tangent direction; **mutually exclusive with `RampType=Helix`**
      for now (combining a shifted entry point with a spiral descent needs more design than this
      pass did) — verified via screenshot that the checkbox visibly disables when Helix is
      selected. **Pocket-geometry-aware by rejection** (PR #1 review): each lead's swept cutter
      area — tool radius plus the radial Stock to Leave in force for that move (roughing stock for
      the lead-in; none for a lead-out that follows finishing passes) — is checked against the
      same removal solids as the Helix ramp, and a lead that doesn't fit is left out with a
      warning rather than shortened or re-aimed. On an Offset-pattern pocket this means the
      lead-out is normally rejected: the last cut runs along a wall into a corner, so there is
      nowhere straight ahead to exit — a tangential/arc exit needs the arc Lead type below.
      Also fixed in the same review: every rapid positioning the tool over the old plunge point is
      retargeted to the approach point (not only the command right before the plunge), so no
      descent is diagonal, including when a Z-only rapid precedes the plunge; and nothing is
      post-processed when the base `execute()` bails out early without producing a new path.
      Still missing: the arc/radius Lead type
      (Horizontal Lead Radius, Sweep Angle, Perpendicular), High Feedrate Mode (several
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

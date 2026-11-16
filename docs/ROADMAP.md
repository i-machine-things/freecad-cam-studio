# Roadmap

## Endgame

**1:1 or better usability versus Fusion 360 CAM, using the same or a closely similar workflow** —
a user who knows Fusion CAM should be able to sit down with this workbench and get a part
machined with equal or less friction: same mental model (Setup → Stock/WCS → Operations →
Simulate → Post), equivalent or better efficiency (clicks, dialogs, time-to-first-toolpath), and
no missing capability that forces a trip back to Fusion.

**What "1:1" means here, and what it doesn't** (see [CLEAN-ROOM.md](CLEAN-ROOM.md) for the full
reasoning): it means workflow and usability parity — the *sequence of steps*, the *mental model*,
the *terminology a Fusion user already knows* carrying over directly. It does not mean a literal
pixel-identical UI, copied icons/strings, or reproducing Autodesk's specific internal toolpath
algorithms. Usability parity and literal cloning are different goals; we're targeting the first.

**Where "better" is realistic, not just aspirational** — things open-source + FreeCAD-native can
win on, worth actually building toward rather than just claiming:
- No cloud round-trip for CAM calculation — local compute, no subscription-tier toolpath limits.
- Fully scriptable (FreeCAD is Python-native end to end) — macro-driven setups, batch posting,
  parametric CAM tied directly to model parameters without export/re-import.
- No telemetry, works fully offline, no seat/subscription lock on whether you can open your own
  files.
- Faster iteration on tool library / post-processor customization, since it's just editable
  Python/JSON on disk, not a cloud-synced proprietary format.

## How we'll know we're there (usability checkpoints)

Each phase below ends with a usability checkpoint, not just a feature checklist. Since I (the
agent doing the implementation work) don't have a Fusion 360 license or a GUI to drive
interactively, these checkpoints need Allan doing the actual side-by-side comparison on his own
licensed Fusion 360 copy — timing the same part through both tools, noting where this workbench
takes more clicks/dialogs/confusion than Fusion, and where it's already better. That feedback is
what Phase N+1's priorities should actually be drawn from, not just the spec docs in isolation.

## Phase 0 — Foundation (done)
- [x] Clean-room provenance, scope, and legal posture documented (CLEAN-ROOM.md)
- [x] Architecture decision: addon on top of FreeCAD's existing CAM module, not a fork or new
      toolpath engine (ARCHITECTURE.md)
- [x] Installable-addon skeleton: `package.xml`, `InitGui.py`, icon, install docs (INSTALL.md)
- [x] TaskPanel edit-dispatch spike — confirmed no core patch needed (see PR #2 /
      ARCHITECTURE.md's "Resolved" section)

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

## Phase 1 — 2.5D milling: minimum viable workflow parity
The closest match to FreeCAD CAM's existing capability, so this phase proves the whole approach
(addon-over-existing-objects) end to end on a real, usable slice before expanding scope.
- [ ] Finish the behavior spec: Face, Pocket, Contour, Adaptive Clearing, Drilling (Drilling's
      parameter tabs are still an open research item — `docs/spec/02-2d-milling-operations.md`)
- [ ] Tool library creation/edit UX — not yet spec'd at all (flagged open question since
      `01-workflow-overview.md`); this blocks a usable Job even with only one operation type done
- [ ] Setup creation flow: stock definition, WCS, model reference — matching the spec's standard
      sequence
- [ ] Setup → Operations tree UI (PySide/Qt), including Folders for grouping operations
- [ ] `Command` + `TaskPanelOpPage` implementations for Face, Pocket, Contour, Adaptive, Drilling
      — each creates the existing `Path.Op.*` object, backed by our own task-panel pages per the
      resolved dispatch mechanism (no new property schema, no core patch)
- [ ] Shared cross-cutting parameter components used by multiple ops: lead-in/lead-out, ramp/helix
      entry, tabs, stock-to-leave — build once, reuse across the Phase 1 operation set
- [ ] Post-processor selection UX (reuses FreeCAD's existing post-processor list; this phase is
      UX only — the post-processor *library breadth* gap vs. Fusion is tracked separately below)
- **Usability checkpoint**: Allan machines the same simple part (e.g. a pocketed plate with a
  couple of drilled holes) through both this workbench and real Fusion CAM, and reports friction
  points. Don't start Phase 2 until this checkpoint happens at least once.

## Phase 1 progress — detailed log
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
      / `MinimumRampDiameter` (user-adjustable now; default 1 x tool diameter -- was 1.5x, changed at Allan's request) and
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
      Still missing: **Ramp Taper Angle** (conical helix, distinct from Ramping Angle). **Every
      plunge now ramps** (Allan): each is fitted on its own; Ramp Clearance Height counts from the
      previous cut level; a ring starting in a corner can't fit a helix and keeps its plunge.
- [x] Tool selection: Fusion's "Select..." tool-library browser, added alongside the existing
      inline combo (`widgets/tool_picker.py`, cross-cutting — any operation page can use it, used
      first by Pocket). Reuses FreeCAD's own existing `Path.Tool.toolbit.ui.selector.ToolBitSelector`
      dialog and `Path.Tool.Controller.Create` factory (the same building blocks stock CAM's own
      Job-creation dialog uses) rather than building a tool-library browser from scratch. Verified
      via a real button click driving the actual modal dialog, not just the underlying logic.
- [ ] Contour/Profile: cutter compensation ("Compensation Type" — Off / In Computer / In Control /
      Wear / Inverse Wear, per [Autodesk's reference](https://help.autodesk.com/cloudhelp/ENU/Fusion-CAM/files/GUID89C78618-20FD-4A82-BFB4-BC66AFE417DD.htm)).
      Lives on 2D Contour's Passes tab, **and also on the pocket's Finishing Passes section**
      (Allan's screenshots, 2026-11-15; this corrects an earlier note saying Contour only). FreeCAD's `Path.Op.Profile` already
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
- [x] Pocket Linking tab: **Lead-In/Lead-Out** (linear first, arc type added after — see the end
      of this entry). Built per the design note from
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
      skipped rather than guessing a tangent direction; ~~mutually exclusive with `RampType=Helix`~~
      (lifted later — leads and Helix now combine, see the parity map)
      for now (combining a shifted entry point with a spiral descent needs more design than this
      pass did) — verified via screenshot that the checkboxes visibly disable when Helix is
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
      **Arc type, added next** (field list and behavior from
      [Autodesk's 2D Pocket reference](https://help.autodesk.com/cloudhelp/ENU/Fusion-CAM/files/GUID67DC60DE-EE42-4BC4-B50D-B28D938D146E.htm),
      described in our own words): each lead is now an arc tangent to the cut (Horizontal Lead
      Radius + Sweep Angle; radius 0 = none, which is exactly the original linear lead) with an
      optional straight leg outside it (Linear Lead Distance), tangent to the arc or — with
      Perpendicular — square to it, on the arc-center side. Lead-In and Lead-Out have separate
      enables (`UseLeadIn`/`UseLeadOut`; the old combined `UseLeadInOut` is migrated on restore),
      and Same as Lead-In reuses all four lead-in values. Arcs are emitted as true G2/G3 with
      I/J. The arc is tried on both sides of the cut — the open side for the current Cutting
      Direction first — and the same fit check picks one or rejects the lead. Verified on real
      `Path.Commands`: radii consistent, arc tangent to the cut at the attach point, FreeCAD's
      own `Path.Geom.edgeForCmd` reads the expected arc length, plunge sits at the lead's outer
      end with no diagonal descent, save/reopen recomputes to the identical path.
      **Known limit, found while testing**: stock Offset-pattern output ends its last ring *in a
      corner* (the ring starts and ends on a vertex), where the cutter is tangent to two walls —
      no tangent exit of any shape fits there, so Lead-Out is rejected on a square-cornered
      Offset pocket. Making it usable needs the ring's start/end moved to mid-wall (or a small
      overlap past the start), which is toolpath-ordering work, not lead geometry — tracked here.
      Lead-In is unaffected (the first plunge is mid-pocket).
      Still missing: **Vertical Lead-In/Lead-Out Radius** (an arc in the vertical plane easing
      the descent onto the path), a separate Lead-In/Lead-Out feedrate (part of the Speeds &
      Feeds item above), leads on every pass/region rather than only the first entry and last
      exit, "Leads on all Finishing Passes", default lead sizes derived from the tool diameter
      (ours default to 0 = nothing until set — Fusion's actual defaults need confirming from
      Allan's install), High Feedrate Mode (several rapid-vs-feed-move output strategies) + High
      Feedrate, Allow Rapid Retract, Safe Distance, Maximum Stay-Down Distance (we have the
      `KeepToolDown` toggle but not this limit), Lift Height
- [ ] Pocket Heights tab: FreeCAD's shared Heights+Depths pages give Clearance/Safe/Start/Final;
      Fusion's Clearance/Retract/Feed/Top/Bottom reads as having a distinct "Feed height" concept
      that may not map 1:1 — needs verification, not an assumed match
- [x] Chip Thinning (Allan confirmed the behavior, 2026-11-15): a **checkbox on the toolpath's
      Tool bar** (Feed & Speed), not Passes. With stepover ae < D/2 the cutting feed is divided by
      RCTF = sqrt(1 - (1 - 2*ae/D)^2) so real chip thickness stays at the chipload; plunge, ramp
      and lead feeds are unchanged. The bar shows the factor and effective feed, updating when
      the stepover changes on the Passes bar. Known limit: engagement is higher than the
      stepover in corners and on the first full-width cut, where the raised feed still applies.
      The label "Chip Thinning" is ours; Fusion's exact label is still unconfirmed.
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

## Pocket parity map (from Allan's Fusion screenshots, 2026-11-15)

Field-by-field map of Fusion's pocket dialog, taken from Allan's own screenshots of his licensed
Fusion install (same trust level as observing the live app; field names only, nothing copied).
**Have** = built and verified. **Partial** = exists but differs from Fusion in a way that matters.
**Missing** = not built. This is the checklist for the per-operation completeness gate.

**Naming (confirmed by Allan, 2026-11-15):** current Fusion calls this operation **"2D Offset
Roughing"**; it is the renamed 2D Pocket, not a separate operation. Our command and dialog title use
the new name. Internal names (`ops/pocket.py`, `CamStudio_Pocket`, the upstream "Pocket Shape" op
type) stay as they are.

### Tool tab
| Fusion field | Status | Notes |
|---|---|---|
| Tool + Select... | Have | Combo + `widgets/tool_picker.py` |
| Edit... (tool) | Missing | Edit the selected tool in place |
| Feed & Speed: Preset | Missing | Fusion's per-tool presets (one per material: surface speed + chipload); the right place for material-specific chiploads. Today defaults come from the stock material's surface speed + the tool's single Chipload |
| Spindle Speed, Surface Speed, Ramp Spindle Speed | Have | **Per operation** (Allan's call: industry standard). Op emits `M3/M4 S` at its start when it differs from the tool controller and restores the controller's speed at its end; Ramp Spindle Speed switches only around the helix. Surface Speed is derived (edit it to set rpm) |
| Cutting Feedrate, Feed per Tooth | Have | Per operation, fed into upstream generation via `opExecute`. Feed per Tooth derived from the tool's flutes |
| Lead-In / Lead-Out / Ramp / Plunge Feedrate | Have | Per operation, each applied to its own moves |
| Transition Feedrate | Missing | For stay-down links; we can't tell links from cuts in FreeCAD's output yet (same blocker as Maximum Stay-Down Distance) |
| Plunge Feed per Revolution | Have | Derived (edit it to set Plunge Feedrate) |
| Coolant | Have | |

### Multi-axis tab (tool orientation)
| Fusion field | Status | Notes |
|---|---|---|
| Machining Type (3 choices, icons only) | Missing | 3-axis is the first; the other two need confirming |
| Tool Orientation (opt-in section) | Missing | Dropdown, e.g. "Z axis/plane & X axis" |
| Z Axis / X Axis select, Flip Z / Flip X | Missing | |
| Align to View, Accessibility Analysis | Missing | |
| Turn, Tilt (deg) | Missing | |
| Origin (e.g. Setup WCS origin) | Missing | |

### Geometry tab
| Fusion field | Status | Notes |
|---|---|---|
| Pocket Selections (with selection-mode buttons) | Partial | FreeCAD's shared Base Geometry page; no Fusion-style selection modes |
| Rest Machining (opt-in section): Tool Diameter, Corner Radius | Partial | We have an on/off checkbox on the Passes group. FreeCAD's `UseRestMachining` uses earlier ops' cleared area; Fusion's version here takes a previous tool's size. Different behavior, and it belongs on this tab |
| Stock Contours (opt-in section): Stock Selections | Missing | |

### Heights tab
Five heights, each with a **From** reference (e.g. Retract height, Stock top, Top height,
Selected contour(s)) and an **Offset**.
| Fusion field | Status | Notes |
|---|---|---|
| Clearance Height | Partial | FreeCAD ClearanceHeight, on the Heights bar; no From/Offset pair. FreeCAD also retracts to it between passes |
| Retract Height | Have | `RetractHeight` (CAM Studio). FreeCAD's generator retracts to Clearance between passes; between the first and last cut those retracts and travel moves now go to Retract Height instead. Defaults to the expression `ClearanceHeight` (= FreeCAD's behavior). Clamped between Feed Height/stock top and Clearance |
| Feed Height | Have | FreeCAD SafeHeight: verified in generated G-code that the tool rapids to Safe Height and feeds from there (not from Start Depth). Labeled Feed Height |
| Top Height | Partial | FreeCAD StartDepth |
| Bottom Height | Partial | FreeCAD FinalDepth |

### Passes tab
| Fusion field | Status | Notes |
|---|---|---|
| Tolerance | Missing | |
| Sideways Compensation | Have | Left/Right, backed by FreeCAD CutMode; with an M3 spindle Left = climb, Right = conventional, a reversed spindle swaps them. FreeCAD fixes the loop direction regardless of which way rings progress, so outside-in clearing came out backward (Allan caught it); `areaOpPathParams` now flips the direction for outside-in. Verified on real toolpaths: plain and island pockets, both clearing orders, both modes really cut as labelled |
| Clearing Order (CAM Studio) | Have | Inside out / Outside in toggle on the Passes bar, backed by FreeCAD's StartAt (Center / Edge). Not in Allan's Fusion screenshots; added at his request |
| Minimum Cutting Radius | Missing | |
| Preserve Order, Both Ways | Missing | |
| Maximum Stepover | Have | Distance, as in Fusion, and the same value as a percent on the same row ("Maximum Stepover: [distance] = [%] of tool Ø"), both editable and linked. Stored as FreeCAD's whole-percent StepOver, so the distance snaps to 1% of tool diameter. Follows the tool on tool change |
| Use Morphed Spiral Machining, Allow Stepover Cusps | Missing | |
| Smoothing Deviation | Missing | |
| **Multiple Depths** (opt-in section) | Have | Section on the Passes bar with its own on/off (off = one pass at the bottom). Levels computed by `ops/pocket.py` `depthLevels` and handed to upstream's `depth_params` via its `user_depths` argument |
| - Maximum Roughing Stepdown | Partial | = StepDown |
| - Finishing Stepdowns (count), Finishing Stepdown | Have | Count is CAM Studio's; size is FreeCAD's Finish Depth. Older ops with a Finish Depth get a count of 1, keeping their toolpath |
| - Wall Taper Angle | Missing | |
| - Use Even Stepdowns | Have | On by default, as in Fusion: roughing levels evenly spaced at or under the max stepdown (FreeCAD's own stepping is full steps plus a thinner last one) |
| - Finish Only at Final Depth, Rough Final | Missing | Tied to how finishing passes run per level; ours rerun the whole pattern (see finishing passes) |
| - Order by Depth, Order by Step | Missing | Last two rows of the section (`pocket-passes4.png`) |
| **Finishing Passes** (opt-in section) | Partial | |
| - Compensation Type (e.g. In computer) | Missing | **Corrects the earlier note** that this is Contour-only: it is on the pocket's Finishing Passes too |
| - Number of Finishing Passes, Finish Feedrate | Have | |
| - Stepover | Missing | Ours reuses the roughing stepover |
| - Leads on all Finishing Passes, Repeat Finishing Pass, Finishing Overlap | Missing | |
| **Stock to Leave** (opt-in section): Radial, Axial | Have | Ours is always on, not an opt-in section |
| **Smoothing** (opt-in) | Missing | |
| **Feed Optimization** (opt-in): Maximum Directional Change, Reduced Feed Radius, Reduced Feed Distance, Reduced Feedrate, Only Inner Corners | Missing | |

### Linking tab
| Fusion field | Status | Notes |
|---|---|---|
| High Feedrate Mode (e.g. Preserve rapid moves) | Missing | |
| Allow Rapid Retract, Safe Distance | Missing | |
| Keep Tool Down | Have | FreeCAD `KeepToolDown`, on the Linking bar. Stays down for links up to one tool diameter (upstream's fixed limit) |
| Maximum Stay-Down Distance | Missing | Upstream's link distance is the right hook, but its links are straight and unchecked. Fusion's 2 in default would let one cut through an island or plough through uncut stock. Needs each link checked against walls/islands *and* the area cleared so far before the limit can be raised |
| Lift Height | Missing | |
| Lead-In (Entry), Horizontal Lead-In Radius, Lead-In Sweep Angle, Linear Lead-In Distance, Perpendicular | Have | |
| Vertical Lead-In Radius | Missing | |
| Lead-Out (Exit), Same as Lead-In | Have | Fusion lists only these two with Same as Lead-In ticked |
| Ramp Type | Partial | Plunge, **Plunge Outside Stock**, Helix of 7 |
| - Plunge Outside Stock | Have | At every depth level, each separate area (boss top / pocket region) is entered by plunging just outside its outline -- **Plunge Distance**, tool center from the edge, default 1.25 x tool diameter (Allan) -- then feeding in sideways. Plunge and feed are checked against the finished part. Areas enclosed by the part (recessed pockets) keep a normal plunge, with a warning. Assumes the space beside the area is clear of stock (CAM Studio can't see leftover stock, only the part) |
| Ramping Angle, Maximum Ramp Stepdown, Helical Ramp Diameter, Minimum Ramp Diameter | Have | |
| Ramp Clearance Height | Have | `RampClearanceHeight`, default 0.100 in as in the capture. The tool rapids down to this far above the stock top (or Start Depth, if higher), then ramps from there instead of spiralling down from Safe Height at plunge feed |
| Ramp Radial Clearance | Missing | Not in any earlier list |
| Positions: Predrill Positions, Preferred Lead-In Positions, Exit Positions | Missing | Point selections |

### Dialog layout (built 2026-11-15)
FreeCAD's stacked task-panel bars, lined up with Fusion's tabs:
**Tool → Base Geometry → Extensions → Heights → Passes → Linking**. Multi-axis is left out until
it has fields. FreeCAD's separate Heights and Depths pages are folded into one **Heights** bar
(Clearance, Retract (new), Feed = Safe Height, Top = Start Depth, Bottom = Final Depth) that reuses their
expression-aware fields; Step Down and Finish Step Down moved to **Passes → Multiple Depths** as
Maximum Roughing Stepdown and Finishing Stepdown. Linking holds Leads & Transitions, then Ramp. **Pocket Pattern and Zig-Zag Angle were
removed** (Allan: "offset means offset"); the op pins `ClearingPattern` to Offset, read-only, also on
restore.

### Behavior differences the screenshots show
- **Leads and Helix ramp work together in Fusion** (both on in the same capture). **Built**: the
  lead-in moves the entry point out to the lead's outer end, the helix descends there (its own fit
  check runs at that point), and the lead carries the tool into the cut at full depth. The helix
  now makes whole revolutions so it bottoms out on its own entry point, instead of finishing
  part-way round and cutting straight across the circle at full depth.
- **Default values seen in the capture** (no tool was selected, so these may be fallbacks rather
  than tool-derived): lead radii 0.025 in, sweep 90 deg, linear lead 0.025 in, Lead-In and Lead-Out
  both on; ramp angle 2 deg, max ramp stepdown 0.025 in, ramp clearance height 0.100 in, helical
  ramp diameter 0.237 in, minimum 0.125 in; stepover 0.150 in, roughing stepdown 0.025 in; Keep Tool
  Down on, max stay-down 2.00 in; feed optimization 25 deg / 0.013 in / 0.050 in / 10 in/min.
  Ours default leads to 0 (off).
- **Opt-in sections**: Multiple Depths, Finishing Passes, Stock to Leave, Smoothing, Feed
  Optimization, Rest Machining, Stock Contours and Tool Orientation each have a checkbox on the
  section header. Our `CollapsibleSection` has no header checkbox yet.
- **Tab layout**: Fusion uses six tabs (Tool, Multi-axis, Geometry, Heights, Passes, Linking). Ours
  is one page of collapsible groups beside FreeCAD's shared pages.
- **Not in Fusion's dialog**: our Minimize travel, Use outline, Use custom start point. These are
  FreeCAD options. Keep them, under Other Options. (Pocket Pattern and Zig-Zag Angle: removed.)
- **Chip Thinning** isn't visible in any of these captures. Still blocked on Allan.

## Stock material and default feeds & speeds (built 2026-11-15)
Built on **FreeCAD's own material system** (Allan: "I don't want to reinvent the wheel"; an
earlier CAM Studio-only library and Setup dialog were replaced).
- **Material** = the Job's `Stock.ShapeMaterial`, where stock CAM keeps it, picked in FreeCAD's
  Job Edit via CAM Studio's labelled **Material: <name> [Change...]** row (replaces the
  unlabelled material button). FreeCAD's Machinability model gives HSS/carbide surface speeds.
- **Chipload** = the tool bit's own Chipload field. A per-material chipload table (as a CAM
  Studio material model) was built and then **removed**: the tool's chipload always won, and a
  table per material keyed only by diameter can't distinguish tools of the same size. The
  proper home for material-specific chiploads is Fusion's per-tool **Preset** (see Tool tab
  row "Feed & Speed: Preset").
- **Defaults**: rpm = 1000*Vc/(pi*D) (no spindle cap); cutting (and leads) = fz*flutes*rpm;
  plunge (and ramp) = fz*rpm; without a tool chipload, feeds stay at the tool controller's.
  Applied when an op is created or its tool changes, and on demand with **Reset to Defaults**.
- Menu **Add Feeds & Speeds Materials** writes the FeedsAndSpeeds addon's 15 materials (CC-BY,
  credited) into FreeCAD's User library on request.

## Simulate / Inspect / Post Process / Check (2026-11-15)
FreeCAD CAM's own commands, reused unmodified on a **CAM Studio Actions** toolbar and the CAM
Studio menu: CAM Simulator (`CAM_SimulatorGL`), Inspect Toolpath (`CAM_Inspect`, also on
right-click of a Job/op), Post Process (`CAM_Post`), Sanity Check (`CAM_Sanity`). Registered by
calling FreeCAD CAM's own guarded `Path.GuiInit.Startup()`. Verified: posting a CAM Studio pocket
through FreeCAD's linuxcnc and grbl posts keeps per-op spindle changes (`M3 S12000` ... back to the
tool's `M3 S10000`) and emits the arc leads as `G3 ... I J`. Not built: a Fusion-style NC
Program / post dialog of our own.

## Phase 2 — Simulation / toolpath verification
Moved ahead of 3D/turning versus the original draft of this roadmap: "simulate before you trust
the toolpath" is core to how Fusion CAM actually gets used day to day, so usability parity is
incomplete without it even if the operation set is still small. Likely the largest net-new
engineering effort so far, since it's not a thin UI layer over an existing FreeCAD object the way
Phase 1's operations are.
- [ ] Toolpath playback view (stock removal simulation, not just drawing the tool centerline path)
- [ ] Scrub/step controls, collision/gouge flagging if feasible
- **Usability checkpoint**: same side-by-side comparison as Phase 1, specifically on "trust the
  toolpath before posting" — this is the moment Fusion users lean on simulation most.

## Phase 3 — 3D surfacing operations
Parallel, Scallop, and other surface-finishing strategies, once Phase 1's UI scaffolding
(tree, shared parameter components, task-panel framework) already exists to extend rather than
rebuild.
- [ ] Spec pass: 3D operation behavior from public Fusion docs (not yet researched — Phase 1/2's
      spec docs only cover 2.5D)
- [ ] Map onto FreeCAD's existing `Path.Op.Surface`/`PlanarSurface`/`RotarySurface`/`Waterline`
- [ ] `Command` + `TaskPanelOpPage` implementations

## Phase 4 — Turning
Separate workflow (lathe setup, OD/ID turning, facing, grooving, threading). FreeCAD's CAM module
has some turning support already — scope it against public Fusion turning docs once Phase 1-3 are
stable, so this doesn't fork attention away from proving out the core milling workflow first.
- [ ] Spec pass: Fusion turning workflow from public docs
- [ ] Map onto FreeCAD's existing turning-related `Path.Op.*` classes
- [ ] `Command` + `TaskPanelOpPage` implementations

## Phase 5 — Usability-parity push
Not a new-features phase — a deliberate pass at closing whatever gap the Phase 1-4 usability
checkpoints actually surfaced, plus the functionality gaps already known going in:
- [ ] Post-processor library breadth (FreeCAD relies on community posts; Fusion ships a large
      bundled library — real functionality gap, not just a UX-matching exercise, flagged since
      `01-workflow-overview.md`)
- [ ] Terminology/keyboard-shortcut parity pass informed by the accumulated checkpoint feedback
- [ ] Performance: toolpath calculation speed, UI responsiveness on large models — "better than
      Fusion" only holds if this is actually fast, not just locally-run
- [ ] Whatever the Phase 1-4 checkpoints flagged as "this is why I'd still open Fusion instead"

## Cross-cutting, ongoing throughout
- **Clean-room discipline**: every spec addition cites its public sources per CLEAN-ROOM.md,
  every phase.
- **File compatibility**: periodically confirm documents still open correctly in both this
  workbench and vanilla FreeCAD CAM (ARCHITECTURE.md's compatibility claim needs to keep holding
  as new operation types get added, not just assumed once).
- **Testing**: no automated test suite exists yet — worth standing up once Phase 1 has enough
  surface area to actually test (FreeCAD's own `CAMTests` module is the relevant pattern to
  follow, not something to invent from scratch).

## Non-goals
- Literal pixel-identical UI, copied icons/strings, or Autodesk asset reuse — see
  [CLEAN-ROOM.md](CLEAN-ROOM.md).
- Matching Autodesk's specific internal toolpath algorithms where those may be patented (adaptive
  clearing and similar) — implement against published machining literature and FreeCAD's existing
  algorithms instead.
- Submission to FreeCAD's official Addon catalogue, or an upstream merge — see
  [INSTALL.md](INSTALL.md).

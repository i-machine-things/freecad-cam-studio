# 2.5D milling operations: behavior spec

Sources: Autodesk's official reference pages for
[2D Contour](https://help.autodesk.com/cloudhelp/ENU/Fusion-CAM/files/GUID75B6821B-DE26-4E3B-AF10-4A54131CD9E4.htm)
and [2D Adaptive Clearing](https://help.autodesk.com/cloudhelp/ENU/Fusion-CAM/files/GUIDA73542E9-ED9C-4BD9-A87D-3A0ECA8BEB41.htm),
a Yeti Tool knowledge-base page on [2D Pocket](https://www.yetitool.com/Support/KNOWLEDGE-BASE/software-fusion-360-2d-milling-toolpaths-2d-pocket),
Bantam Tools' ["Three Essential CAM Toolpaths in Fusion 360"](https://bantamtools.com/blog/three-essential-cam-toolpaths-in-fusion-360-btafw),
and a Purdue CAM class handout (Autodesk University PDF). Described in our own words below, not
quoted verbatim. **Drilling's exact parameter tabs were not found in public sources yet — flagged
as an open item, do not guess at FreeCAD's Drilling op's parameters and call it equivalent without
checking.**

## 2D Face

Purpose: flatten the top of stock to a known reference height. Typically the first operation in a
setup, run before anything else references a clean top face.
- Geometry input: **no selection is required by default** — it uses the stock defined in the
  setup. An edge or sketch can optionally be selected to limit the faced area to less than the
  full stock top.
- For larger stock removal than a simple skim, Adaptive Clearing is used instead of Face.
- **FreeCAD mapping**: `Path Face` operation — same purpose, direct equivalent.

## 2D Pocket (Autodesk now calls this "2D Offset Roughing" — renamed from "2D Pocket Clearing")

Purpose: clear material from within a closed boundary down to a depth. Full field list below is
sourced directly from Autodesk's own
[2D Offset Roughing reference](https://help.autodesk.com/cloudhelp/ENU/Fusion-CAM/files/GUID67DC60DE-EE42-4BC4-B50D-B28D938D146E.htm)
page (the authoritative parameter-by-parameter doc, not a tutorial/forum source like the rest of
this file) — described in our own words, not quoted verbatim. This supersedes the thinner draft
this section used to have; CAM Studio's current implementation (see `ops/pocket.py`,
`pages/pocket.py`) covers only a subset, tracked field-by-field against this list in
`docs/ROADMAP.md`. The five-tab structure (Tool/Geometry/Heights/Passes/Linking) and the Tool
tab's Select.../Coolant/Feed & Speed layout are independently corroborated by a screenshot of
Allan's own Fusion install (2D Adaptive operation — the same dialog chrome is shared across 2D
strategies, not Pocket-specific).

**Tool tab**: Coolant, plus a full Feed & Speed section (Spindle Speed, Surface Speed, Ramp
Spindle Speed, Cutting Feedrate, Feed per Tooth, Lead-In/Lead-Out/Transition/Ramp/Plunge
Feedrates, Feed per Revolution) editable *inline on the operation*, not only on a separate Tool
Controller object.

**Geometry tab**: Face/Edge/Sketch selection, with three distinct *machining modes* (Closed
Pocket / Open Pocket / Standing Boss) rather than one generic selection. Open-pocket selections
need an **Extension Method** (Tangent / Closest boundary / Parallel) to close the boundary against
the stock. **Stock Contours** (+ its own boundary selection) lets the cut area be bounded by the
Setup's stock box, a sketch, or model edges instead of just the raw selection. Per-contour **cut
direction arrows** are individually clickable. **Rest Machining** here has its own sub-parameters
(simulated previous Tool Diameter + Corner Radius), separate from the simple on/off we have.
**Tool Orientation** is a full secondary coordinate-system control (Setup WCS / Model / explicit
axis selection / named coordinate system, each with its own Origin option) — lets one operation
cut at an angle to the Setup's main WCS.

**Heights tab**: Clearance / Retract / Feed / Top / Bottom height. FreeCAD's shared Heights+Depths
pages give us Clearance/Safe/Start/Final — close, but "Retract" and "Feed" height read as
*distinct* concepts here, not confirmed 1:1 with FreeCAD's Safe/Start; needs verification, not an
assumed match.

**Passes tab** (the largest tab by far): Tolerance (spline linearization), **Sideways
Compensation** (Climb/Conventional — this is our existing `CutMode`), **Minimum Cutting Radius**
(forces a blend in sharp internal corners instead of a zero-radius toolpath), a full **finishing
pass subsystem** (enable + Number of Passes + per-pass Stepover + "Leads on all Finishing Passes"
+ Finish Feedrate + Repeat Finishing Pass + Finishing Overlap), **Preserve Order**, **Both Ways**
(climb+conventional alternating, with its own Optimal-Load/Feedrate for the "other way" pass),
Maximum Stepover (= our `StepOver`), **Use Morphed Spiral Machining** (a named alternate toolpath
style), **Allow Stepover Cusps**, **Smoothing Deviation**, Multiple Depths + Maximum Stepdown
(= our `StepDown`), **Finishing Stepdowns** (separate Z-stepdown count/size for finish passes),
**Wall Taper Angle** (machine a sloped wall with a 2.5D strategy instead of needing 3D — this is
the "tapered walls" item the old draft of this section already flagged as unresolved), **Use Even
Stepdowns**, **Order by Depth**, **Order by Step**, Stock to Leave (radial/axial — we have this,
**but Fusion explicitly supports *negative* stock-to-leave for electrode/spark-gap machining**,
not yet verified against our `ExtraOffset`/`AxialStockToLeave`), general **Smoothing** (G-code
arc-fitting/size reduction, distinct from Smoothing Deviation above), and a **Feed Optimization**
corner-slowdown subsystem (Maximum Directional Change, Reduced Feed Radius/Distance/Feedrate,
Only Inner Corners).

**Linking tab**: **High Feedrate Mode** (several rapid-vs-feed-move output strategies) + High
Feedrate, Allow Rapid Retract, Safe Distance, **Keep Tool Down** (we have `KeepToolDown` already)
+ Maximum Stay-Down Distance, Lift Height, a full **Lead-In/Lead-Out** arc/line subsystem
(Horizontal/Vertical Lead Radius, Sweep Angle, Linear Lead Distance, Perpendicular, "Same as
Lead-In") that is *distinct from ramping* (approach/retract arcs around the cut, not the
plunge-entry strategy), and **Ramp Type with seven options**: Plunge Outside Stock, Zig-Zag,
Predrill, Profile, Plunge, Smooth Profile, Helix (our earlier forum-sourced research only found
five of these — this reference page is the authoritative count) — plus Ramping Angle (= our
`RampAngle`), **Ramp Taper Angle** (conical helix, distinct from Ramping Angle), **Maximum Ramp
Stepdown**, **Ramp Clearance Height**, and critically **Helical Ramp Diameter + Minimum Ramp
Diameter** — the exact "does the helix fit in this pocket" parameter pair our V1 Helix
implementation hardcoded (as tool radius) instead of exposing, and Predrill/Entry Positions for
the Predrill ramp type.

- **FreeCAD mapping**: `Path.Op.PocketShape` (2.5D) — base clearing concept matches; the vast
  majority of the above has no FreeCAD property at all and is tracked as real feature work in
  `docs/ROADMAP.md`, not assumed equivalent.

## 2D Contour

Purpose: machine along a profile — usually a finishing pass, but can take multiple roughing cuts
too (not finishing-only).
- Tabs (small uncut bridges holding the part to stock) are a named option here, set under a
  Heights/Passes-style section of the dialog — relevant for thin stock (plastic/wood) that would
  otherwise flex or fly loose once fully cut free. A commonly cited rule of thumb: ~4 tabs per
  part is usually enough, though this is a community heuristic, not an Autodesk spec value.
- **FreeCAD mapping**: `Path Profile` operation. Tab support needs to be checked against FreeCAD's
  current Profile op (open item for Phase 1).

## 2D Adaptive Clearing

Purpose: roughing strategy that clears bulk material while avoiding sharp direction changes and
full-width conventional cuts — keeps consistent tool engagement to protect tool life and allow
higher feed rates.
- Per Autodesk's own reference, the dialog's tabs mostly overlap with 2D Pocket's. **Correction**:
  separate axial/radial stock-to-leave is *not* Adaptive-specific — Fusion's own Pocket reference
  documents both controls too, so this is a shared control across both operations, not a
  distinguishing one. The real Adaptive-specific control on that fourth tab is **Optimal Load**
  (maximum tool engagement/stepover limit for the adaptive strategy — not chip load, a distinct
  quantity) — that's the one worth calling out
  as the meaningful difference from Pocket.
- **Patent note**: this is the strategy name most associated with Autodesk's adaptive-clearing
  patents. Per [CLEAN-ROOM.md](../CLEAN-ROOM.md), implement against published trochoidal/adaptive
  milling literature and FreeCAD's own existing adaptive-clearing-style path (if any) rather than
  trying to reproduce Autodesk's specific internal method — this spec should describe *what the
  user sets and what the toolpath looks like*, not the internal path-generation algorithm.
- **FreeCAD mapping**: not yet confirmed whether FreeCAD's Path workbench has a direct adaptive-
  clearing equivalent today — open item, check before Phase 1 implementation starts.

## Drilling

Not yet researched in public sources — placeholder. FreeCAD has a `Path Drilling` operation;
Fusion's Drilling parameter tabs (peck depths, dwell, retract behavior, etc.) need a follow-up
research pass before mapping it.

## Cross-cutting items not yet covered
- Lead-in/lead-out and ramp/helix entry options — referenced in passing above (pocket pre-drill,
  adaptive's avoidance of sharp turns) but not spec'd as their own parameter set yet.
- Stock-to-leave as a general concept — confirmed shared by Pocket and Adaptive; check whether
  Contour/Drilling expose the same control.
- Tool library UI — out of scope for this file, tracked as an open question in
  `01-workflow-overview.md`.

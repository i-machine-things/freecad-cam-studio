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

## 2D Pocket

Purpose: clear material from within a closed boundary down to a depth.
- Geometry input: can come from sketch edges, solid-model edges, or a selected solid face —
  three distinct input modes, not just "pick a sketch."
- Options include tapered walls, a pre-drill entry position (for plunging into a pilot hole
  rather than ramping/helixing in blind), and separate axial/radial stock-to-leave — the same
  stock-to-leave controls Adaptive Clearing also exposes (see that section's correction below).
- **FreeCAD mapping**: `Path Pocket` (2.5D) operations — base concept matches; taper-wall and
  pre-drill-entry-position options need to be checked against what FreeCAD's pocket op currently
  exposes (not yet verified — Phase 1 task).

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
  (target tool engagement/chip load for the adaptive strategy) — that's the one worth calling out
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

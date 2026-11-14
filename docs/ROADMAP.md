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

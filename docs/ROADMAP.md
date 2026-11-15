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
      **V1 scope, stated plainly**: only the operation's very first plunge is ramped (later
      retract/re-plunge cycles within the same pass are usually re-entering already-cleared air,
      not solid material) and only "Helix" is implemented — Fusion also has Plunge (already the
      default/no-op case), Zigzag, Zig, and Profile ramp types, not yet built. Per-level/per-region
      ramping and the remaining ramp types are tracked follow-ups, not silently dropped scope.
- [ ] Tool selection: Fusion's "Select..." tool-library browser vs. our current inline combo of
      tool controllers already on the Job. Cross-cutting (every operation's Tool tab needs it) —
      build once as shared infrastructure, used first by Pocket
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

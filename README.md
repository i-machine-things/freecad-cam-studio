# FreeCAD CAM Studio

An **addon workbench for FreeCAD** that adds a Fusion-360-CAM-style workflow/UX on top of
FreeCAD's existing CAM module — not a new toolpath engine, not a FreeCAD fork. It creates and
edits the exact same `Path::FeaturePython` objects (Job, Pocket, Adaptive, Profile, Drilling, ...)
that FreeCAD's own CAM workbench uses, so files stay compatible both ways; only the Gui layer
(task panels, the Setup/Operations tree, dialog organization) is new. See
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for how that's grounded in FreeCAD's actual source.

Built **clean-room**: no Autodesk code, binaries, or assets were read, decompiled, or disassembled
to make this. Behavior is derived only from Autodesk's own public documentation, tutorials, and
screenshots. See [docs/CLEAN-ROOM.md](docs/CLEAN-ROOM.md) for the full provenance statement and
[docs/ROADMAP.md](docs/ROADMAP.md) for the phased plan.

## Install

Not on FreeCAD's official Addon catalogue — by design, see [docs/INSTALL.md](docs/INSTALL.md).
Install directly from this repo via Addon Manager's custom-repository option, or clone into your
FreeCAD `Mod` directory.

## Status

Early scaffolding. No working code yet — currently in the **Study** phase: building a
behavior/workflow spec for Fusion 360 CAM from public sources, to implement against.

- [docs/spec/01-workflow-overview.md](docs/spec/01-workflow-overview.md) — Manufacture workspace
  structure and the Setup → Operations → Simulate → Post workflow.
- [docs/spec/02-2d-milling-operations.md](docs/spec/02-2d-milling-operations.md) — 2.5D milling
  operation behavior (Face, Pocket, Contour, Adaptive Clearing, Drilling) and how each maps onto
  FreeCAD's existing Path operations.

## Scope

Full breadth is the goal — 2.5D milling, 3D, turning, and simulation — sequenced in phases
(see the roadmap). 2.5D milling is the first implementation target since it's the closest match
to FreeCAD's existing `Path` workbench capability today.

## Not affiliated with Autodesk

This project is not affiliated with, endorsed by, or connected to Autodesk, Inc. "Fusion",
"Fusion 360", and related marks are trademarks of Autodesk. This project does not use Autodesk's
icons, artwork, or verbatim UI strings.

# Workflow overview: Fusion 360 CAM

Sources: Autodesk's own CAM intro docs and tutorials ([Getting started: introduction to CAM and
toolpaths](https://autodesk.com/products/fusion-360/blog/getting-started-introduction-to-cam-and-toolpaths),
[Learn Fusion for CAM in 90 Minutes](https://www.autodesk.com/learn/ondemand/course/learn-fusion-360-for-cam-in-90-minutes-2024)),
a UNSW CNC teaching module ([making.unsw.edu.au](https://www.making.unsw.edu.au/learn/cnc-module4/)),
and a Purdue CAM class handout (PDF, Autodesk University). No Fusion binary or source was read —
this describes documented/observed behavior only.

## Where CAM lives

CAM work happens in Fusion's **Manufacture** workspace — a separate workspace from the modeling
environment (Design), switched via the workspace selector. This is a different UI model from
FreeCAD, which switches between separate workbenches (Part Design, Path/CAM, etc.) via a workbench
dropdown — conceptually the same idea (a mode switch), different widget.

## Core hierarchy

```
Job / Document
└── Setup                  (one per stock orientation / machine mounting)
    ├── Stock definition   (box/cylinder, offsets from the model's bounding geometry)
    ├── WCS (work coordinate system) — origin and orientation for this setup
    ├── Model geometry reference (which bodies/faces this setup machines)
    ├── Folder (optional)  — grouping container for related operations
    └── Operation          (one per toolpath: 2D Pocket, 2D Contour, Drilling, ...)
```

A **Setup** is the top-level grouping container — it represents one physical mounting of stock in
the machine. Multiple setups exist when a part needs to be flipped/re-fixtured to machine
different faces. Operations live under a Setup, optionally grouped into Folders.

## Standard sequence

1. **Create a Setup** — pick the WCS orientation and reference the model.
2. **Define stock** — size/shape and offset from the model (e.g. "relative size box" with a
   margin), independent per setup.
3. **Add operations** — each operation picks a strategy (Face, Pocket, Contour, Adaptive,
   Drilling, ...), a tool from the tool library, and strategy-specific parameters (depths,
   stepover, stock-to-leave, tabs, leads/ramps).
4. **Simulate** — play back the toolpath against the stock model to visually verify before
   posting.
5. **Post-process** — generate G-code via a post-processor selected for the target controller.

FreeCAD's Path/CAM workbench already has an equivalent structure (`Job` → `Setup`/stock →
`Operation`), so Phase 1's job is primarily a UI/UX layer matching this sequence and terminology,
not a new underlying data model.

## Open questions for later spec passes
- Exact tool-library UI/workflow (tool creation, holders, presets) — not yet researched.
- Lead-in/lead-out and ramp parameter conventions across operation types — only partially covered
  by the 2D-operations spec (see `02-2d-milling-operations.md`).
- Post-processor selection UI and the breadth of Autodesk's bundled post library (FreeCAD relies
  on community posts — a real functionality gap worth scoping, not just a UX-matching exercise).

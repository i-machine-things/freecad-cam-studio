"""CAM Studio's own operation Proxy subclasses.

Each module here subclasses the matching upstream `Path.Op.*` Proxy class
(never patches it in place) to add properties/behavior Fusion 360 exposes
that the stock FreeCAD operation doesn't -- see docs/ARCHITECTURE.md and
the project's "100% parity" standard in docs/ROADMAP.md. These are still
the exact same Path::FeaturePython object type stock CAM creates; they
just carry a few extra properties and override specific, officially
documented extension hooks (e.g. `initPocketOp`, `_customDepthParams`).
"""

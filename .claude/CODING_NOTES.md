# Coding Best Practices & Reminders

> **Style rule:** Notes must be clear and concise — 300 characters or less each. Group by topic, not by date. Whenever a PR review (CodeRabbit or human) catches a mistake, add or amend a note here right away so it isn't repeated.

## FreeCAD CAM API accuracy

- FreeCAD CAM class names can be misleading by similarity, not just by absence. `Path/Op/Pocket.py`'s `ObjectPocket` is the **3D** Pocket op (`FeatureNoFinalDepth`, final depth not editable) — the 2.5D, shape-based Pocket with editable final depth is `Path/Op/PocketShape.py`. Verify against the actual pinned FreeCAD version's source (`raw.githubusercontent.com/FreeCAD/FreeCAD/<tag>/...`) before citing a class in spec/architecture docs — filename pattern-matching isn't enough.

## Fusion 360 CAM spec accuracy

- When documenting a Fusion operation's parameter as "unique" to it, check the comparable operation's own reference page too. Autodesk often shares controls across dialogs (Pocket and Adaptive Clearing both expose axial/radial stock-to-leave) — don't infer uniqueness from only one op's doc page.

## Cross-platform install paths

- Don't infer an app's per-OS config/data directory from a generic pattern or by analogy to other apps' conventions (e.g. assuming macOS mirrors `~/Library/Preferences/<App>`). Verify from the app's own docs or a runtime call — FreeCAD: `App.getUserAppDataDir()`. A wrong path is a silent no-op install, not an error.

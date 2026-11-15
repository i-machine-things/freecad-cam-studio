# Coding Best Practices & Reminders

> **Style rule:** Notes must be clear and concise — 300 characters or less each. Group by topic, not by date. Whenever a PR review (CodeRabbit or human) catches a mistake, add or amend a note here right away so it isn't repeated.

## FreeCAD CAM API accuracy

- FreeCAD CAM class names can be misleading by similarity, not just by absence. `Path/Op/Pocket.py`'s `ObjectPocket` is the **3D** Pocket op (`FeatureNoFinalDepth`, final depth not editable) — the 2.5D, shape-based Pocket with editable final depth is `Path/Op/PocketShape.py`. Verify against the actual pinned FreeCAD version's source (`raw.githubusercontent.com/FreeCAD/FreeCAD/<tag>/...`) before citing a class in spec/architecture docs — filename pattern-matching isn't enough.

## Fusion 360 CAM spec accuracy

- When documenting a Fusion operation's parameter as "unique" to it, check the comparable operation's own reference page too. Autodesk often shares controls across dialogs (Pocket and Adaptive Clearing both expose axial/radial stock-to-leave) — don't infer uniqueness from only one op's doc page.
- Don't conflate adjacent-but-distinct machining terms when paraphrasing a parameter (e.g. Adaptive's "Optimal Load" is a max engagement/stepover limit, not "chip load" — a different, related quantity). Check Autodesk's own wording, don't substitute a closely-associated synonym.

## Cross-platform install paths

- Don't infer an app's per-OS config/data directory from a generic pattern or by analogy to other apps' conventions (e.g. assuming macOS mirrors `~/Library/Preferences/<App>`). Verify from the app's own docs or a runtime call — FreeCAD: `App.getUserAppDataDir()`. A wrong path is a silent no-op install, not an error.
- `~` does not expand inside double-quoted shell strings. Install docs with a quoted path containing spaces (e.g. macOS `"~/Library/Application Support/..."`) must use `"$HOME/Library/..."` instead, or the literal `~` gets passed through and the clone lands in the wrong place.

## Headless FreeCAD testing (offscreen flatpak)

- `Path.Main.Gui.Job.Create(base, template, openTaskPanel=True)`'s default auto-opens stock CAM's Stock-editing TaskPanel, which hangs indefinitely under `QT_QPA_PLATFORM=offscreen` (no real GL context — "No valid GL context found!" spam, process never returns). Our own commands that call this must pass `openTaskPanel=False` explicitly.
- Any headless test script run via `flatpak run --command=freecad --env=QT_QPA_PLATFORM=offscreen ... script.py` must wrap its whole body in `try/except/finally: os._exit(0)`. An uncaught exception mid-script does not exit the process — FreeCAD reports it and the GUI event loop keeps running forever instead, hanging the test.
- `Path.Op.Gui.Base.CommandResources.name` is not just a display label — `ViewProvider` also uses it as the lookup key into `Path.Op.Gui.Selection`'s per-op-type selection-mode registry (`PathSelection.select(self.OpName)`). A custom `name` raises `KeyError` at edit time. It must stay the exact upstream op-type string (e.g. `"Pocket Shape"`); put CAM Studio's own branding in `menuText`/`toolTip` instead, which have no such constraint.

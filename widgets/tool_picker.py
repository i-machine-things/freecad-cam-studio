"""Shared "pick a tool from the library" helper for every operation's Tool tab.

Fusion's Tool tab has a "Select..." button that opens a tool-library
browser (docs/ROADMAP.md's tracked Tool-selection gap). FreeCAD already
has the equivalent building blocks -- Path.Tool.toolbit.ui.selector's
ToolBitSelector (a library-browsing dialog, the same one stock CAM's own
Job creation dialog uses) and Path.Tool.Controller.Create (wraps a chosen
tool into a per-Job ToolController with feeds/speeds/tool number) -- so
this reuses FreeCAD's own public infrastructure rather than building a
tool-library browser from scratch.
"""

import FreeCAD

import Path.Tool.Controller as PathToolController


def pick_new_tool_controller(job, parent=None, fallback=None):
    """Open the tool-library browser and create+attach a new ToolController for
    `job` from the user's selection. Returns the new ToolController object, or
    None if the user cancelled or selected nothing.

    FreeCAD creates the controller with zero spindle speed and feeds. Seed them from the
    setup's stock material when it has machining data (cs_materials/library.py), else from
    `fallback` (e.g. the operation's current controller), so the new tool doesn't start
    at zero."""
    # Path.Tool.camassets / Path.Tool.toolbit.ui.selector are FreeCAD 1.1+-only modules
    # (absent in 1.0.2). Importing them at module scope would raise ImportError the moment
    # InitGui.py's Initialize() imports this module transitively, breaking the *entire*
    # workbench's toolbar/menu construction on older FreeCAD -- not just tool picking. Keep
    # the import local so only this function fails (with a clear error) on older FreeCAD.
    from Path.Tool.camassets import cam_assets, ensure_assets_initialized
    from Path.Tool.toolbit.ui.selector import ToolBitSelector

    # The built-in tool library is lazily seeded on first use elsewhere in stock CAM (e.g.
    # when its own Job-creation dialog or Tool Library dock is opened) -- can't assume that
    # already happened before our own button is clicked, so ensure it here too.
    ensure_assets_initialized(cam_assets)

    dlg = ToolBitSelector(parent)
    if not dlg.exec_():
        return None
    toolbit = dlg.get_selected_tool()
    if toolbit is None:
        return None

    attached = toolbit.attach_to_doc(doc=FreeCAD.ActiveDocument)
    # job.Proxy.nextToolNumber()/addToolController() (not a manual Tools.Group reassignment)
    # -- addToolController also wires VertRapid/HorizRapid expressions to the Job's
    # SetupSheet, which a plain Group append would silently skip.
    toolNumber = job.Proxy.nextToolNumber()
    tc = PathToolController.Create(name="TC: " + attached.Label, tool=attached, toolNumber=toolNumber)
    _seedFeeds(tc, job, fallback)
    job.Proxy.addToolController(tc)
    return tc


def _seedFeeds(tc, job, fallback):
    if tc.SpindleSpeed > 0 and tc.HorizFeed.Value > 0 and tc.VertFeed.Value > 0:
        return
    try:
        from cs_materials import library

        defaults = library.defaultFeedsFor(job, tc.Tool)
    except Exception:
        defaults = None
    if defaults is not None:
        tc.SpindleSpeed = round(defaults["rpm"])
        if "cutting" in defaults:
            tc.HorizFeed = defaults["cutting"] / 60.0
            tc.VertFeed = defaults["plunge"] / 60.0
    if fallback is not None:
        if tc.SpindleSpeed <= 0:
            tc.SpindleSpeed = fallback.SpindleSpeed
        if tc.HorizFeed.Value <= 0:
            tc.HorizFeed = fallback.HorizFeed.Value
        if tc.VertFeed.Value <= 0:
            tc.VertFeed = fallback.VertFeed.Value

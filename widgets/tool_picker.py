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

from Path.Tool.camassets import cam_assets, ensure_assets_initialized
from Path.Tool.toolbit.ui.selector import ToolBitSelector
import Path.Tool.Controller as PathToolController


def pick_new_tool_controller(job, parent=None):
    """Open the tool-library browser and create+attach a new ToolController for
    `job` from the user's selection. Returns the new ToolController object, or
    None if the user cancelled or selected nothing."""
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
    tc = PathToolController.Create(name="TC: " + attached.Label, tool=attached)
    job.Tools.Group = job.Tools.Group + [tc]
    return tc

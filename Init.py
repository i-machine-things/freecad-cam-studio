"""App-level init for CAM Studio (runs in GUI and console mode).

Nothing to register. An earlier build registered a CAM Studio material model folder with
FreeCAD's material system; that model was dropped, so remove any such setting a previous run
left behind (harmless if left, but no reason to keep it).
"""

import FreeCAD


def _removeOldMaterialModelRegistration():
    modules = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/Material/Resources/Modules")
    if "CamStudio" in modules.GetGroups():
        modules.RemGroup("CamStudio")


try:
    _removeOldMaterialModelRegistration()
except Exception as e:  # never block FreeCAD startup over this
    FreeCAD.Console.PrintWarning("CAM Studio: %s\n" % e)

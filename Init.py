"""App-level init for CAM Studio (runs in GUI and console mode).

Registers CAM Studio's material model folder (cs_materials/Models: the "CAM Studio Chipload"
model) with FreeCAD's material system, the supported way for a module to add material
models. Only the model folder is registered, no material folder: materials themselves stay
in FreeCAD's own libraries so plain FreeCAD / stock CAM still find them -- see
cs_materials/library.py.
"""

import os

import FreeCAD


def _registerMaterialModels():
    # FreeCAD runs this file without __file__; find the add-on through its own package.
    import cs_materials

    here = os.path.dirname(os.path.dirname(os.path.abspath(cs_materials.__file__)))
    group = FreeCAD.ParamGet(
        "User parameter:BaseApp/Preferences/Mod/Material/Resources/Modules/CamStudio"
    )
    group.SetString("ModuleModelDir", os.path.join(here, "cs_materials", "Models"))
    group.SetString("ModuleIcon", os.path.join(here, "Resources", "icons", "workbench.svg"))
    group.SetBool("ModuleReadOnly", True)


try:
    _registerMaterialModels()
except Exception as e:  # never block FreeCAD startup over this
    FreeCAD.Console.PrintWarning("CAM Studio: could not register material models: %s\n" % e)

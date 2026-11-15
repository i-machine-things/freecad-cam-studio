"""CAM Studio's own Pocket operation Proxy.

Subclasses Path.Op.PocketShape.ObjectPocket (never patches it) to add
"Axial Stock to Leave" -- a Fusion 2D Pocket option
(docs/spec/02-2d-milling-operations.md) that FreeCAD's stock PocketShape
operation has no property for at all. Radial stock-to-leave already
exists upstream as `ExtraOffset`; this adds the missing Z-axis half of
the pair by hooking `_customDepthParams`, an officially documented
extension point in Path.Op.Area.ObjectOp (its docstring literally says
subclasses should use it for exactly this kind of per-op depth
customization) -- not a core patch.
"""

import FreeCAD
from PySide.QtCore import QT_TRANSLATE_NOOP

import Path.Op.Base as PathOp
import Path.Op.PocketBase as PathPocketBase
import Path.Op.PocketShape as PathPocketShape


class ObjectPocket(PathPocketShape.ObjectPocket):
    def areaOpFeatures(self, obj):
        # PathPocketShape.ObjectPocket.areaOpFeatures calls super(self.__class__, self) --
        # with self.__class__ being OUR subclass, that resolves to the same bound method on
        # every recursive call (self never changes), causing infinite recursion two levels
        # deep. Call PocketBase's implementation directly instead of going through
        # PocketShape's broken super() chain. Not a core patch -- just not inheriting a
        # buggy one-liner.
        return PathPocketBase.ObjectPocket.areaOpFeatures(self, obj) | PathOp.FeatureLocations

    def initPocketOp(self, obj):
        super().initPocketOp(obj)
        if not hasattr(obj, "AxialStockToLeave"):
            obj.addProperty(
                "App::PropertyDistance",
                "AxialStockToLeave",
                "Pocket",
                QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Material left on the pocket floor (Z axis) for a later finishing pass",
                ),
            )
            obj.AxialStockToLeave = 0

    def _customDepthParams(self, obj, strDep, finDep):
        axial = getattr(obj, "AxialStockToLeave", None)
        adjustedFinalDepth = finDep + (axial.Value if axial else 0.0)
        return super()._customDepthParams(obj, strDep, adjustedFinalDepth)


def Create(name, obj=None, parentJob=None):
    """Create(name) ... creates and returns a CAM Studio Pocket operation."""
    if obj is None:
        obj = FreeCAD.ActiveDocument.addObject("Path::FeaturePython", name)
    obj.Proxy = ObjectPocket(obj, name, parentJob)
    return obj

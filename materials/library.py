"""CAM Studio's stock material library and default feeds & speeds.

A material has a surface speed per tool material (HSS / Carbide, m/min) and, per tool
material, a chipload table: feed per tooth (mm) against tool diameter (mm), linearly
interpolated and held flat past either end. The shipped defaults are `seed.json` (see
ATTRIBUTION.md); the user's edited library lives in FreeCAD's user data folder and, once
it exists, replaces the shipped one entirely.

Defaults for an operation (`defaultFeeds`), from standard machining formulas:
  rpm      = 1000 * surface speed / (pi * diameter)   [no spindle cap -- Allan's choice]
  fz       = the tool's own Chipload if set, else the material's table for that tool
             material at this diameter
  cutting  = fz * flutes * rpm      (lead-in and lead-out use the same)
  plunge   = fz * rpm               (one tooth's worth per revolution; ramp uses the same)
No GUI or document access here, so it can be tested on its own.
"""

import json
import math
import os

TOOL_MATERIALS = ("HSS", "Carbide")
_SEED = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seed.json")


def userLibraryPath():
    import FreeCAD

    return os.path.join(FreeCAD.getUserAppDataDir(), "CamStudio", "materials.json")


def _read(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load(path=None):
    """List of material dicts: the user's library if it exists, else the shipped one."""
    if path is None:
        try:
            path = userLibraryPath()
        except Exception:
            path = None
        if not path or not os.path.exists(path):
            path = _SEED
    return [_normalized(m) for m in _read(path).get("materials", [])]


def save(materials, path=None):
    """Write the whole library to the user's file (never to the shipped seed)."""
    path = path or userLibraryPath()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"version": 1, "materials": [_normalized(m) for m in materials]}, f, indent=2)
    os.replace(tmp, path)


def names(materials=None):
    return [m["name"] for m in (materials if materials is not None else load())]


def find(name, materials=None):
    for m in materials if materials is not None else load():
        if m["name"] == name:
            return m
    return None


def _normalized(m):
    speeds = m.get("surfaceSpeed", {}) or {}
    chip = m.get("chipload", {}) or {}
    return {
        "name": str(m.get("name", "")).strip(),
        "category": str(m.get("category", "")),
        "surfaceSpeed": {t: float(speeds.get(t, 0) or 0) for t in TOOL_MATERIALS},
        "chipload": {
            t: sorted(([float(d), float(fz)] for d, fz in (chip.get(t) or [])), key=lambda p: p[0])
            for t in TOOL_MATERIALS
        },
    }


def toolMaterial(tool):
    """'HSS' or 'Carbide' from a FreeCAD tool bit (anything else counts as HSS, the
    conservative choice: lower surface speed)."""
    value = str(getattr(tool, "Material", "") or "")
    return "Carbide" if value.lower().startswith("carbide") else "HSS"


def chipload(material, toolMat, diameter):
    """Feed per tooth (mm) from the material's table, or None if the table is empty."""
    table = material["chipload"].get(toolMat) or []
    if not table or diameter <= 0:
        return None
    if diameter <= table[0][0]:
        return table[0][1]
    if diameter >= table[-1][0]:
        return table[-1][1]
    for (d0, f0), (d1, f1) in zip(table, table[1:]):
        if d0 <= diameter <= d1:
            return f0 if d1 == d0 else f0 + (f1 - f0) * (diameter - d0) / (d1 - d0)
    return None


def defaultFeeds(material, toolMat, diameter, flutes, toolChipload=0.0):
    """Defaults for an operation, or None if the material/tool can't give a spindle speed.
    Returns a dict: rpm, chipload (mm, or None), and -- only when a chipload is known --
    cutting/plunge feeds in mm/min. `source` says where the chipload came from."""
    vc = material["surfaceSpeed"].get(toolMat, 0.0)
    if vc <= 0 or diameter <= 0:
        return None
    rpm = 1000.0 * vc / (math.pi * diameter)
    fz, source = None, None
    if toolChipload and toolChipload > 0:
        fz, source = toolChipload, "tool"
    else:
        fz = chipload(material, toolMat, diameter)
        source = "material" if fz is not None else None
    result = {"rpm": rpm, "chipload": fz, "source": source, "surfaceSpeed": vc, "toolMaterial": toolMat}
    if fz is not None:
        result["cutting"] = fz * max(1, int(flutes or 1)) * rpm
        result["plunge"] = fz * rpm
    return result

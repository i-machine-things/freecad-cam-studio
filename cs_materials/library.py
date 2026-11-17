"""CAM Studio's default feeds & speeds from FreeCAD's own material system.

The stock material is the one stock CAM already uses: the Job's `Stock.ShapeMaterial`,
picked in FreeCAD's Job Edit (CAM Studio adds a labelled row for it -- pages/setup.py). Its
**Machinability** model gives SurfaceSpeedHSS / SurfaceSpeedCarbide. Chipload comes from the
tool bit's own Chipload field. (Per-material chiploads would belong in Fusion-style per-tool
presets -- see docs/ROADMAP.md -- not in the material.)

Defaults for an operation (`defaultFeeds`), from standard formulas:
  rpm     = 1000 * Vc / (pi * D)        [no spindle cap -- Allan's choice]
  cutting = fz * flutes * rpm           (lead-in / lead-out use the same)
  plunge  = fz * rpm                    (ramp uses the same)
with fz the tool's Chipload; without one, feeds stay at the tool controller's.

`importFeedsAndSpeedsMaterials` adds extra machining materials to FreeCAD's User library.
"""

import math

import FreeCAD

TOOL_MATERIALS = ("HSS", "Carbide")
SAVE_LIBRARY = "User"
SAVE_FOLDER = "CAM Studio"


def _materials():
    import Materials

    return Materials


def machinabilityUUID():
    return _materials().UUIDs().Machinability


def manager():
    return _materials().MaterialManager()


def stockMaterial(job):
    """The Job's stock material if it has machining data (surface speeds), else None."""
    stock = getattr(job, "Stock", None)
    material = getattr(stock, "ShapeMaterial", None) if stock is not None else None
    if material is None or not material.hasPhysicalModel(machinabilityUUID()):
        return None
    return material


def toolMaterial(tool):
    """'HSS' or 'Carbide' from a FreeCAD tool bit; anything else counts as HSS (the
    conservative choice: lower surface speed)."""
    value = str(getattr(tool, "Material", "") or "")
    return "Carbide" if value.lower().startswith("carbide") else "HSS"


def surfaceSpeed(material, toolMat):
    """Surface speed in m/min (0 if the material has none for that tool material)."""
    name = "SurfaceSpeed" + toolMat
    if material is None or not material.hasPhysicalProperty(name):
        return 0.0
    value = material.getPhysicalValue(name)
    if value is None:
        return 0.0
    return FreeCAD.Units.Quantity(value).getValueAs("m/min").Value


def defaultFeeds(vc, diameter, flutes, toolChipload=0.0):
    """rpm, and -- when the tool has a chipload -- cutting and plunge feeds (mm/min), from a
    surface speed (m/min). None if no spindle speed can be worked out."""
    if vc <= 0 or diameter <= 0:
        return None
    rpm = 1000.0 * vc / (math.pi * diameter)
    fz = toolChipload if toolChipload and toolChipload > 0 else None
    result = {"rpm": rpm, "chipload": fz, "surfaceSpeed": vc}
    if fz is not None:
        result["cutting"] = fz * max(1, int(flutes or 1)) * rpm
        result["plunge"] = fz * rpm
    return result


def defaultFeedsFor(job, tool):
    """defaultFeeds for `tool` in `job`'s stock material, or None."""
    material = stockMaterial(job)
    if material is None or tool is None:
        return None
    toolMat = toolMaterial(tool)
    chip = getattr(tool, "Chipload", 0)
    chip = getattr(chip, "Value", chip) or 0.0
    result = defaultFeeds(
        surfaceSpeed(material, toolMat),
        tool.Diameter.Value,
        int(getattr(tool, "Flutes", 0) or 0),
        float(chip),
    )
    if result is not None:
        result["toolMaterial"] = toolMat
        result["material"] = material.Name
    return result


def _libraryDir(name):
    for entry in manager().MaterialLibraries:
        if entry[0] == name:
            return entry[1]
    raise LookupError("FreeCAD material library '%s' not found" % name)


def _safeFileName(name):
    keep = "".join(c if c.isalnum() or c in " ()-_.," else "_" for c in name).strip()
    return keep or "Material"


def importFeedsAndSpeedsMaterials():
    """Write the FeedsAndSpeeds addon's material cards (seed.json: names, categories and
    HSS/carbide surface speeds; CC-BY 3.0, see ATTRIBUTION.md) into FreeCAD's User library
    as standard machining materials, under "CAM Studio/Feeds and Speeds". Files that
    already exist are left alone. Returns (written, skipped) name lists."""
    import json
    import os
    import uuid

    import yaml

    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "seed.json"), encoding="utf-8") as f:
        seed = json.load(f)["materials"]
    folder = os.path.join(_libraryDir(SAVE_LIBRARY), SAVE_FOLDER, "Feeds and Speeds")
    os.makedirs(folder, exist_ok=True)
    written, skipped = [], []
    for m in seed:
        path = os.path.join(folder, _safeFileName(m["name"]) + ".FCMat")
        if os.path.exists(path):
            skipped.append(m["name"])
            continue
        card = {
            "General": {
                "UUID": str(uuid.uuid4()),
                "Author": "Daniel Wood (FreeCAD Feeds and Speeds addon)",
                "License": "CC-BY-3.0",
                "Name": m["name"],
                "Description": "Surface speeds from the FreeCAD Feeds and Speeds addon's "
                "material cards. Imported by CAM Studio.",
            },
            "Models": {
                "Father": {"UUID": "9cdda8b6-b606-4778-8f13-3934d8668e67", "Father": m.get("category", "")},
                "Machinability": {
                    "UUID": machinabilityUUID(),
                    "SurfaceSpeedHSS": "%r m/min" % float(m["surfaceSpeed"]["HSS"]),
                    "SurfaceSpeedCarbide": "%r m/min" % float(m["surfaceSpeed"]["Carbide"]),
                },
            },
        }
        with open(path, "w", encoding="utf-8") as f:
            f.write("---\n# Imported by CAM Studio (FreeCAD material file)\n")
            yaml.safe_dump(card, f, sort_keys=False, allow_unicode=True, default_flow_style=None)
        written.append(m["name"])
    if written:
        manager().refresh()
    return written, skipped

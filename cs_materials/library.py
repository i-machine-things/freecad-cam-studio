"""CAM Studio's feeds & speeds from FreeCAD's own material system.

Materials are FreeCAD materials. The stock material is the one stock CAM already uses:
the Job's `Stock.ShapeMaterial`, picked in FreeCAD's Job Edit (CAM Studio adds a labelled
row for it -- see pages/setup.py). From it we read:

- FreeCAD's **Machinability** model: SurfaceSpeedHSS / SurfaceSpeedCarbide.
- CAM Studio's **CAM Studio Chipload** model (Models/CAMStudio/CamStudioChipload.yml,
  registered with FreeCAD by Init.py): ChiploadHSS / ChiploadCarbide tables of
  [tool diameter, feed per tooth].

Compatibility with plain FreeCAD / stock CAM (verified): a material carrying our model
loads normally without CAM Studio -- its Machinability data intact, our tables just not
shown -- and documents round-trip. That only holds if the material lives in one of
FreeCAD's own libraries, so edits are saved to FreeCAD's "User" library (SAVE_LIBRARY),
never to an add-on folder. FreeCAD's built-in materials are read-only: adding a chipload
table to one saves an inheriting copy in the User library (surface speeds still come from
the original) and the caller switches the stock to that copy.

Defaults for an operation (`defaultFeeds`), from standard formulas:
  rpm     = 1000 * Vc / (pi * D)             [no spindle cap -- Allan's choice]
  fz      = the tool's own Chipload if set, else the material's table at D
  cutting = fz * flutes * rpm    (lead-in / lead-out use the same)
  plunge  = fz * rpm             (ramp uses the same)
"""

import math

import FreeCAD

CHIPLOAD_MODEL = "9c492684-3b61-4aa9-a529-604747cff89d"
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


def chiploadTable(material, toolMat):
    """[[diameter mm, feed per tooth mm], ...] sorted by diameter; [] if none."""
    name = "Chipload" + toolMat
    if material is None or not material.hasPhysicalProperty(name):
        return []
    array = material.getPhysicalValue(name)
    rows = []
    for r in range(getattr(array, "Rows", 0) or 0):
        try:
            d = FreeCAD.Units.Quantity(array.getValue(r, 0)).getValueAs("mm").Value
            fz = FreeCAD.Units.Quantity(array.getValue(r, 1)).getValueAs("mm").Value
        except Exception:
            continue
        if d > 0 and fz > 0:
            rows.append([d, fz])
    return sorted(rows)


def interpolate(table, diameter):
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


def defaultFeeds(vc, table, diameter, flutes, toolChipload=0.0):
    """rpm / chipload / cutting and plunge feeds (mm/min) from a surface speed (m/min) and
    a chipload table, or None if no spindle speed can be worked out."""
    if vc <= 0 or diameter <= 0:
        return None
    rpm = 1000.0 * vc / (math.pi * diameter)
    if toolChipload and toolChipload > 0:
        fz, source = toolChipload, "tool"
    else:
        fz = interpolate(table, diameter)
        source = "material" if fz is not None else None
    result = {"rpm": rpm, "chipload": fz, "source": source, "surfaceSpeed": vc}
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
        chiploadTable(material, toolMat),
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


def _quantityRows(rows):
    return [["%r mm" % float(d), "%r mm" % float(fz)] for d, fz in rows]


def saveChipload(material, tables):
    """Store chipload tables ({"HSS": rows, "Carbide": rows}; rows of [diameter mm,
    feed per tooth mm]) on `material` in FreeCAD's User library, and return the saved
    material -- the one the stock should point at.

    - A material already in the User library is updated in place (same file, same UUID,
      so every document using it sees the change).
    - A read-only one (FreeCAD's built-in materials) gets a new User-library material in
      "CAM Studio/" that *inherits* it -- surface speeds etc. still come from FreeCAD's
      original -- and adds only the chipload tables.

    Written as a standard FreeCAD material file (FreeCAD's Python API can't set table
    values), then FreeCAD's material libraries are refreshed so it loads it the normal way.
    """
    import os
    import uuid

    import yaml

    chip = {"UUID": CHIPLOAD_MODEL}
    for toolMat in TOOL_MATERIALS:
        rows = sorted([float(d), float(fz)] for d, fz in tables.get(toolMat, []) if d > 0 and fz > 0)
        if rows:
            # FreeCAD's 2DArray layout: a one-item list holding the list of rows.
            chip["Chipload" + toolMat] = [_quantityRows(rows)]
    libDir = _libraryDir(SAVE_LIBRARY)
    if getattr(material, "LibraryName", "") != SAVE_LIBRARY:
        # A built-in material: reuse CAM Studio's existing copy of it if there is one, so
        # repeated edits don't pile up "Name 2", "Name 3"... copies.
        existing = existingCopy(material)
        if existing is not None:
            material = existing
    if getattr(material, "LibraryName", "") == SAVE_LIBRARY:
        path = os.path.join(libDir, _libraryPath(material))
        with open(path, encoding="utf-8-sig") as f:
            card = yaml.safe_load(f) or {}
        card.setdefault("Models", {})["CAM Studio Chipload"] = chip
        targetUUID = card.get("General", {}).get("UUID", material.UUID)
    else:
        targetUUID = str(uuid.uuid4())
        card = {
            "General": {
                "UUID": targetUUID,
                "Name": material.Name,
                "Description": "%s with CAM Studio chipload tables. Surface speeds and all "
                "other data are inherited from FreeCAD's material." % material.Name,
            },
            "Inherits": {material.Name: {"UUID": material.UUID}},
            "Models": {"CAM Studio Chipload": chip},
        }
        folder = os.path.join(libDir, SAVE_FOLDER)
        os.makedirs(folder, exist_ok=True)
        base = _safeFileName(material.Name)
        path, n = os.path.join(folder, base + ".FCMat"), 1
        while os.path.exists(path):  # never overwrite an unrelated earlier copy
            n += 1
            path = os.path.join(folder, "%s %d.FCMat" % (base, n))
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("---\n# Written by CAM Studio (FreeCAD material file)\n")
        yaml.safe_dump(card, f, sort_keys=False, allow_unicode=True, default_flow_style=None)
    os.replace(tmp, path)
    mm = manager()
    mm.refresh()
    return mm.getMaterial(targetUUID)


def existingCopy(material):
    """CAM Studio's User-library copy of a built-in material (one that inherits it, in the
    CAM Studio folder), or None."""
    for candidate in manager().Materials.values():
        if (
            getattr(candidate, "LibraryName", "") == SAVE_LIBRARY
            and getattr(candidate, "Parent", "") == material.UUID
            and (getattr(candidate, "Directory", "") or "").strip("/").startswith(SAVE_FOLDER)
        ):
            return candidate
    return None


def _libraryPath(material):
    """Path of an existing library material's own file, relative to its library. FreeCAD
    reports the folder as Directory and the file's stem as Name."""
    directory = (getattr(material, "Directory", "") or "").strip("/")
    name = material.Name + ".FCMat"
    return "%s/%s" % (directory, name) if directory else name


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

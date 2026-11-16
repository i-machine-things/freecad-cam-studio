"""Chipload editor for one FreeCAD material (CAM Studio's "CAM Studio Chipload" model).

Shows the material's surface speeds (read-only here: they are FreeCAD's Machinability data,
edited in FreeCAD's material editor) and edits the feed-per-tooth tables by tool diameter
for HSS and carbide tools, in the user's unit schema. Saving goes through
cs_materials.library.saveChipload (User library; a built-in material gets an inheriting
copy). `saved` is the resulting material, or None if cancelled.
"""

import FreeCAD
from PySide import QtCore, QtWidgets

from cs_materials import library

translate = FreeCAD.Qt.translate


def _units():
    """(speed unit, m/min per unit, length unit, mm per unit, length decimals)."""
    lengthUnit = FreeCAD.Units.Quantity(1.0, FreeCAD.Units.Length).getUserPreferred()[2]
    if lengthUnit in ("in", "ft", "thou", "yd", "mi"):
        return "ft/min", 0.3048, "in", 25.4, 4
    return "m/min", 1.0, "mm", 1.0, 3


class ChiploadDialog(QtWidgets.QDialog):
    def __init__(self, material, parent=None):
        super().__init__(parent)
        self.material = material
        self.saved = None
        self.setWindowTitle(translate("CamStudio_Chipload", "Chipload: %s") % material.Name)
        self.resize(520, 440)
        (self.speedUnit, self.speedScale, self.lenUnit, self.lenScale,
         self.lenDecimals) = _units()

        info = QtWidgets.QFormLayout()
        for toolMat in library.TOOL_MATERIALS:
            vc = library.surfaceSpeed(material, toolMat)
            text = ("%.0f %s" % (vc / self.speedScale, self.speedUnit)) if vc > 0 else "-"
            info.addRow(
                translate("CamStudio_Chipload", "Surface Speed (%s tools)") % toolMat,
                QtWidgets.QLabel(text),
            )
        self.tables = {}
        tabs = QtWidgets.QTabWidget()
        for toolMat in library.TOOL_MATERIALS:
            table = QtWidgets.QTableWidget(0, 2)
            table.setHorizontalHeaderLabels(
                [
                    translate("CamStudio_Chipload", "Tool Diameter (%s)") % self.lenUnit,
                    translate("CamStudio_Chipload", "Feed per Tooth (%s)") % self.lenUnit,
                ]
            )
            table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
            for r, row in enumerate(library.chiploadTable(material, toolMat)):
                table.insertRow(r)
                for c, mm in enumerate(row):
                    item = QtWidgets.QTableWidgetItem(self._fmt(mm))
                    # Keep the exact stored value: saving an untouched cell must not round it.
                    item.setData(QtCore.Qt.UserRole, (item.text(), mm))
                    table.setItem(r, c, item)
            add = QtWidgets.QPushButton(translate("CamStudio_Chipload", "Add Row"))
            remove = QtWidgets.QPushButton(translate("CamStudio_Chipload", "Remove Row"))
            add.clicked.connect(lambda _=False, t=table: t.insertRow(t.rowCount()))
            remove.clicked.connect(
                lambda _=False, t=table: t.removeRow(t.currentRow()) if t.currentRow() >= 0 else None
            )
            page = QtWidgets.QWidget()
            pl = QtWidgets.QVBoxLayout(page)
            pl.addWidget(table, 1)
            buttons = QtWidgets.QHBoxLayout()
            buttons.addWidget(add)
            buttons.addWidget(remove)
            buttons.addStretch(1)
            pl.addLayout(buttons)
            tabs.addTab(page, toolMat)
            self.tables[toolMat] = table

        note = QtWidgets.QLabel(
            translate(
                "CamStudio_Chipload",
                "Interpolated by tool diameter, held flat beyond the first and last rows. A "
                "tool's own Chipload, if set, takes precedence. Saved to FreeCAD's User "
                "material library; FreeCAD's built-in materials get a copy there that "
                "inherits everything else.",
            )
        )
        note.setWordWrap(True)
        self.status = QtWidgets.QLabel("")
        box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel
        )
        box.accepted.connect(self._save)
        box.rejected.connect(self.reject)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(info)
        layout.addWidget(tabs, 1)
        layout.addWidget(note)
        layout.addWidget(self.status)
        layout.addWidget(box)

    def _fmt(self, mm):
        return ("%%.%df" % self.lenDecimals) % (mm / self.lenScale)

    def _value(self, cell):
        text = cell.text().strip() if cell is not None else ""
        original = cell.data(QtCore.Qt.UserRole) if cell is not None else None
        if original and original[0] == text:
            return float(original[1])
        return float(text) * self.lenScale

    def tableValues(self):
        """{"HSS": rows, "Carbide": rows} in mm; raises ValueError naming a bad cell."""
        out = {}
        for toolMat, table in self.tables.items():
            rows = []
            for r in range(table.rowCount()):
                cells = [table.item(r, c) for c in (0, 1)]
                if not any(c is not None and c.text().strip() for c in cells):
                    continue
                try:
                    d, fz = (self._value(c) for c in cells)
                except (ValueError, TypeError):
                    raise ValueError(
                        translate("CamStudio_Chipload", "%s row %d: enter two numbers") % (toolMat, r + 1)
                    )
                if d > 0 and fz > 0:
                    rows.append([d, fz])
            out[toolMat] = rows
        return out

    def _save(self):
        try:
            values = self.tableValues()
            self.saved = library.saveChipload(self.material, values)
        except Exception as e:
            self.status.setText(str(e))
            return
        self.accept()

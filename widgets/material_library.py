"""Material library editor (a modal dialog).

Lists the stock materials from materials/library.py and edits, per material: name,
category, surface speed for HSS and carbide tools, and a chipload table (feed per tooth
against tool diameter) for each tool material. Shows and takes values in the user's unit
schema (ft/min and inches under an imperial schema, m/min and mm otherwise); the library
itself always stores m/min and mm. Saving writes the user's library file, never the
shipped defaults.
"""

import copy

import FreeCAD
from PySide import QtCore, QtWidgets

from materials import library

translate = FreeCAD.Qt.translate


def _units():
    """(speed unit, m/min per unit, length unit, mm per unit, length decimals)."""
    lengthUnit = FreeCAD.Units.Quantity(1.0, FreeCAD.Units.Length).getUserPreferred()[2]
    if lengthUnit in ("in", "ft", "thou", "yd", "mi"):
        return "ft/min", 0.3048, "in", 25.4, 4
    return "m/min", 1.0, "mm", 1.0, 3


class MaterialLibraryDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, select=None):
        super().__init__(parent)
        self.setWindowTitle(translate("CamStudio_Materials", "Material Library"))
        self.resize(760, 520)
        (self.speedUnit, self.speedScale, self.lenUnit, self.lenScale,
         self.lenDecimals) = _units()
        self.materials = copy.deepcopy(library.load())
        self.current = None  # index being edited
        self._loading = False

        # left: list + add/remove
        self.list = QtWidgets.QListWidget()
        add = QtWidgets.QPushButton(translate("CamStudio_Materials", "Add"))
        dup = QtWidgets.QPushButton(translate("CamStudio_Materials", "Duplicate"))
        remove = QtWidgets.QPushButton(translate("CamStudio_Materials", "Remove"))
        add.clicked.connect(self._add)
        dup.clicked.connect(self._duplicate)
        remove.clicked.connect(self._remove)
        left = QtWidgets.QVBoxLayout()
        left.addWidget(self.list, 1)
        buttons = QtWidgets.QHBoxLayout()
        for b in (add, dup, remove):
            buttons.addWidget(b)
        left.addLayout(buttons)

        # right: the selected material
        self.name = QtWidgets.QLineEdit()
        self.category = QtWidgets.QLineEdit()
        self.speed = {}
        form = QtWidgets.QFormLayout()
        form.addRow(translate("CamStudio_Materials", "Name"), self.name)
        form.addRow(translate("CamStudio_Materials", "Category"), self.category)
        for toolMat in library.TOOL_MATERIALS:
            box = QtWidgets.QDoubleSpinBox()
            box.setRange(0, 1e5)
            box.setDecimals(1)
            box.setSuffix(" " + self.speedUnit)
            self.speed[toolMat] = box
            form.addRow(
                translate("CamStudio_Materials", "Surface Speed (%s tools)") % toolMat, box
            )
        self.tables = {}
        tabs = QtWidgets.QTabWidget()
        for toolMat in library.TOOL_MATERIALS:
            table = QtWidgets.QTableWidget(0, 2)
            table.setHorizontalHeaderLabels(
                [
                    translate("CamStudio_Materials", "Tool Diameter (%s)") % self.lenUnit,
                    translate("CamStudio_Materials", "Feed per Tooth (%s)") % self.lenUnit,
                ]
            )
            table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
            addRow = QtWidgets.QPushButton(translate("CamStudio_Materials", "Add Row"))
            delRow = QtWidgets.QPushButton(translate("CamStudio_Materials", "Remove Row"))
            addRow.clicked.connect(lambda _=False, t=table: t.insertRow(t.rowCount()))
            delRow.clicked.connect(
                lambda _=False, t=table: t.removeRow(t.currentRow()) if t.currentRow() >= 0 else None
            )
            page = QtWidgets.QWidget()
            pl = QtWidgets.QVBoxLayout(page)
            pl.addWidget(table, 1)
            rb = QtWidgets.QHBoxLayout()
            rb.addWidget(addRow)
            rb.addWidget(delRow)
            rb.addStretch(1)
            pl.addLayout(rb)
            tabs.addTab(page, translate("CamStudio_Materials", "Chipload: %s") % toolMat)
            self.tables[toolMat] = table
        note = QtWidgets.QLabel(
            translate(
                "CamStudio_Materials",
                "Chipload is interpolated between rows by tool diameter and held flat beyond "
                "the first and last rows. Leave a table empty to keep feeds from the tool "
                "controller (a tool's own Chipload, if set, always wins).",
            )
        )
        note.setWordWrap(True)
        right = QtWidgets.QVBoxLayout()
        right.addLayout(form)
        right.addWidget(tabs, 1)
        right.addWidget(note)
        self.editor = QtWidgets.QWidget()
        self.editor.setLayout(right)

        split = QtWidgets.QHBoxLayout()
        leftW = QtWidgets.QWidget()
        leftW.setLayout(left)
        leftW.setMaximumWidth(320)
        split.addWidget(leftW)
        split.addWidget(self.editor, 1)

        box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel
        )
        box.accepted.connect(self._save)
        box.rejected.connect(self.reject)
        self.status = QtWidgets.QLabel("")
        bottom = QtWidgets.QHBoxLayout()
        bottom.addWidget(self.status, 1)
        bottom.addWidget(box)
        outer = QtWidgets.QVBoxLayout(self)
        outer.addLayout(split, 1)
        outer.addLayout(bottom)

        self.list.currentRowChanged.connect(self._select)
        self._refreshList(select)

    # -- list ------------------------------------------------------------------------
    def _refreshList(self, select=None):
        self._loading = True
        self.list.clear()
        for m in self.materials:
            self.list.addItem(m["name"])
        self._loading = False
        row = 0
        if select is not None:
            for i, m in enumerate(self.materials):
                if m["name"] == select:
                    row = i
        self.current = None
        if self.materials:
            self.list.setCurrentRow(row)
            self._select(row)
        self.editor.setEnabled(bool(self.materials))

    def _select(self, row):
        if self._loading:
            return
        self._store()
        self.current = row if 0 <= row < len(self.materials) else None
        self._show()

    def _uniqueName(self, base):
        taken = {m["name"] for m in self.materials}
        name, n = base, 2
        while name in taken:
            name, n = "%s %d" % (base, n), n + 1
        return name

    def _add(self):
        self._store()
        self.materials.append(
            library._normalized({"name": self._uniqueName(translate("CamStudio_Materials", "New Material"))})
        )
        self._refreshList(self.materials[-1]["name"])

    def _duplicate(self):
        if self.current is None:
            return
        self._store()
        m = copy.deepcopy(self.materials[self.current])
        m["name"] = self._uniqueName(m["name"] + " " + translate("CamStudio_Materials", "copy"))
        self.materials.append(m)
        self._refreshList(m["name"])

    def _remove(self):
        if self.current is None:
            return
        del self.materials[self.current]
        self.current = None
        self._refreshList()

    # -- editor <-> data -------------------------------------------------------------
    def _show(self):
        if self.current is None:
            return
        m = self.materials[self.current]
        self.name.setText(m["name"])
        self.category.setText(m["category"])
        # Values are shown rounded in the user's units. Remember what was shown, and the
        # exact stored value, so saving only rewrites what the user actually edited --
        # otherwise just viewing a material would round its stored numbers.
        for toolMat, box in self.speed.items():
            box.setValue(m["surfaceSpeed"].get(toolMat, 0.0) / self.speedScale)
            box.setProperty("shown", box.value())
            box.setProperty("exact", m["surfaceSpeed"].get(toolMat, 0.0))
        for toolMat, table in self.tables.items():
            rows = m["chipload"].get(toolMat, [])
            table.setRowCount(len(rows))
            for r, row in enumerate(rows):
                for c, mm in enumerate(row):
                    item = QtWidgets.QTableWidgetItem(self._fmt(mm))
                    item.setData(QtCore.Qt.UserRole, (item.text(), mm))
                    table.setItem(r, c, item)

    def _cellValue(self, cell, text):
        """mm value of a chipload cell: the exact stored value if the cell still shows what
        was loaded, else the typed number converted from the user's units."""
        original = cell.data(QtCore.Qt.UserRole) if cell is not None else None
        if original and original[0] == text:
            return float(original[1])
        return float(text) * self.lenScale

    def _fmt(self, mm):
        return ("%%.%df" % self.lenDecimals) % (mm / self.lenScale)

    def _store(self):
        """Copy the editor back into self.materials[self.current]. Returns an error string
        for a table cell that isn't a number, else None."""
        if self.current is None or self.current >= len(self.materials):
            return None
        m = self.materials[self.current]
        m["name"] = self.name.text().strip() or m["name"]
        m["category"] = self.category.text().strip()
        for toolMat, box in self.speed.items():
            if box.value() != box.property("shown"):
                m["surfaceSpeed"][toolMat] = box.value() * self.speedScale
            else:
                m["surfaceSpeed"][toolMat] = box.property("exact")
        error = None
        for toolMat, table in self.tables.items():
            rows = []
            for r in range(table.rowCount()):
                cells = [table.item(r, c) for c in (0, 1)]
                texts = [c.text().strip() if c is not None else "" for c in cells]
                if not any(texts):
                    continue  # blank row
                try:
                    d, fz = (self._cellValue(cell, text) for cell, text in zip(cells, texts))
                except ValueError:
                    error = translate(
                        "CamStudio_Materials", "%s, %s chipload row %d: not a number"
                    ) % (m["name"], toolMat, r + 1)
                    continue
                if d > 0 and fz > 0:
                    rows.append([d, fz])
            m["chipload"][toolMat] = sorted(rows)
        item = self.list.item(self.current)
        if item is not None:
            item.setText(m["name"])
        return error

    def _save(self):
        error = self._store()
        if error:
            self.status.setText(error)
            return
        names = [m["name"] for m in self.materials]
        dupes = sorted({n for n in names if names.count(n) > 1})
        if dupes:
            self.status.setText(
                translate("CamStudio_Materials", "Duplicate names: %s") % ", ".join(dupes)
            )
            return
        library.save(self.materials)
        self.accept()

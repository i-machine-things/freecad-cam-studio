"""A collapsible section widget, matching Fusion's accordion-style dialog
groups (each section has a disclosure triangle and collapses/expands
independently -- confirmed from Autodesk's own help-page screenshot of
the 2D Pocket dialog's Tool tab). CAM Studio's dialogs previously used
plain, always-expanded QGroupBox sections.

This is a generic, widely-used Qt UI pattern (a toggleable header button
plus a hideable content widget) -- not derived from Autodesk's code or
assets in any way, just a standard PySide technique for exactly this kind
of disclosure-triangle section.
"""

from PySide import QtCore, QtWidgets


class CollapsibleSection(QtWidgets.QWidget):
    """A titled section with a disclosure-triangle header that shows/hides
    its content widget. Use `.setContentLayout(layout)` to populate it, the
    same way you'd build a QGroupBox."""

    def __init__(self, title, expanded=True, parent=None):
        super().__init__(parent)

        self._toggle = QtWidgets.QToolButton()
        self._toggle.setStyleSheet("QToolButton { border: none; font-weight: bold; }")
        self._toggle.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self._toggle.setCheckable(True)
        self._toggle.setChecked(expanded)
        self._toggle.setText(title)
        self._toggle.setArrowType(QtCore.Qt.DownArrow if expanded else QtCore.Qt.RightArrow)
        self._toggle.clicked.connect(self._onToggled)

        self._content = QtWidgets.QWidget()
        self._content.setVisible(expanded)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self._toggle)
        layout.addWidget(self._content)

    def _onToggled(self, checked):
        self._content.setVisible(checked)
        self._toggle.setArrowType(QtCore.Qt.DownArrow if checked else QtCore.Qt.RightArrow)

    def setContentLayout(self, contentLayout):
        # discard the placeholder layout QWidget() creates by default, if any
        old = self._content.layout()
        if old is not None:
            QtWidgets.QWidget().setLayout(old)
        self._content.setLayout(contentLayout)

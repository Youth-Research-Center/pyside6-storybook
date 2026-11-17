"""The controls panel: one labelled editor per control, built from the editors in ``gui.editors``."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QFormLayout, QLabel, QVBoxLayout, QWidget

from pyside6_storybook.controls import Control
from pyside6_storybook.gui.chrome import mark_chrome
from pyside6_storybook.gui.editors import ControlEditor, create_editor

NO_CONTROLS_MESSAGE = "No configurable properties for this component."


class ControlsPanel(QWidget):
    """Renders one labelled editor per control and reports the live values.

    Each row is a label, which is its editor's buddy, and the editor. When there are no controls, a short empty-state label is
    shown instead of an empty form.

    Signals:
        valuesChanged: Emitted once per edit with the current values by control name.
    """

    valuesChanged = Signal(dict)

    def __init__(self, controls: Sequence[Control], parent: QWidget | None = None, *, values: Mapping[str, object] | None = None) -> None:
        """Create the panel.

        Args:
            controls: The controls to render.
            parent: The owning widget.
            values: The starting value of each control by name; a control missing from it starts at its default. Each value is
                validated with the control's ``coerce``.

        Raises:
            ValueError: If ``values`` has a name that is not one of the controls, or a value that its control rejects.
            TypeError: If a value in ``values`` has a type its control rejects.
        """
        super().__init__(parent)
        self._controls = tuple(controls)
        self._editors: dict[str, ControlEditor] = {}
        starting = dict(values) if values is not None else {}
        unknown = sorted(set(starting) - {control.name for control in self._controls})
        if unknown:
            raise ValueError(f"values name {', '.join(repr(name) for name in unknown)}, which are not controls of this panel")
        if not self._controls:
            self._build_empty_state()
            return
        form = QFormLayout(self)
        form.setContentsMargins(0, 0, 0, 0)
        for control in self._controls:
            editor = create_editor(control, control.coerce(starting.get(control.name, control.default)), self)
            editor.set_accessible_texts(control.display_label, control.description)
            _share_input_focus_policy(editor)
            editor.valueChanged.connect(self._on_editor_changed)
            label = QLabel(control.display_label, self)
            label.setBuddy(editor)
            if control.description:
                label.setToolTip(control.description)
                editor.setToolTip(control.description)
            form.addRow(label, editor)
            self._editors[control.name] = editor

    def values(self) -> dict[str, object]:
        """Return the current value of every control, keyed by control name, each passed through the control's ``coerce``."""
        return {control.name: control.coerce(self._editors[control.name].value()) for control in self._controls}

    def _on_editor_changed(self, _value: object) -> None:
        self.valuesChanged.emit(self.values())

    def _build_empty_state(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel(NO_CONTROLS_MESSAGE, self)
        mark_chrome(label, "sbkControlsEmptyState")
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        font = label.font()
        font.setItalic(True)
        label.setFont(font)
        label.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        layout.addWidget(label)


def _share_input_focus_policy(editor: ControlEditor) -> None:
    """Give the editor widget the focus policy of its focus proxy, so ``QWidget.setTabOrder`` accepts it as a compound widget.

    A widget with the default ``NoFocus`` policy is ignored by ``setTabOrder``, which would leave the editor's input where it was
    created in the window's focus chain. With the proxy's policy, ``setTabOrder`` moves the editor with its inputs, in their order.
    """
    proxy = editor.focusProxy()
    if proxy is not None:
        editor.setFocusPolicy(proxy.focusPolicy())


__all__ = ["NO_CONTROLS_MESSAGE", "ControlsPanel"]

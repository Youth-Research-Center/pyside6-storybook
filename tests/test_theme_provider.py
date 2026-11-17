import gc
import logging
import weakref
from collections.abc import Iterator

import pytest
import shiboken6
from conftest import show_active
from fake_providers import LeakyProvider, RaisingProvider, StyleSheetProvider
from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QFont, QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QComboBox, QLabel

from pyside6_storybook import BuiltinThemeProvider, StoryContext, StoryRegistry, TextControl, ThemeProvider
from pyside6_storybook import run as exported_run
from pyside6_storybook.app import run
from pyside6_storybook.gui.error_panel import ErrorPanel
from pyside6_storybook.gui.window import GalleryWindow

pytestmark = pytest.mark.usefixtures("restore_window_activation")


@pytest.fixture(autouse=True)
def _delete_closed_windows() -> Iterator[None]:
    """Delete the windows qtbot closed, as the event loop would, before the next test changes the application style sheet.

    Without it, closed windows from many tests stay pending deletion across several style sheet changes, and Qt can crash in
    ``setStyleSheet`` once they are deleted (#80; ``pyside6_storybook.polishing`` covers the case a running gallery hits).
    """
    yield
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


class _MissingMethod:
    def theme_names(self) -> tuple[str, ...]:
        return ("A",)


def _window(qtbot, registry: StoryRegistry, provider: ThemeProvider) -> GalleryWindow:
    window = GalleryWindow(registry, provider)
    qtbot.addWidget(window)
    return window


def _switch(window: GalleryWindow) -> QComboBox:
    switch = window.findChild(QComboBox, "themeSwitch")
    assert switch is not None
    return switch


@pytest.fixture
def paper(qapp: QApplication, restore_application_look: None):
    provider = StyleSheetProvider()
    provider.activate(qapp)
    try:
        yield provider
    finally:
        provider.deactivate()


@pytest.fixture
def recording_registry() -> tuple[StoryRegistry, list[str]]:
    themes: list[str] = []
    stories = StoryRegistry()

    @stories.story("Display/Label", controls=[TextControl("text", "Hi")])
    def label(ctx: StoryContext) -> QLabel:
        themes.append(ctx.theme)
        return QLabel(f"{ctx.theme} {ctx.args['text']}")

    return stories, themes


def test_the_protocol_accepts_both_providers_and_rejects_a_missing_method() -> None:
    assert isinstance(BuiltinThemeProvider(), ThemeProvider)
    assert isinstance(StyleSheetProvider(), ThemeProvider)
    assert not isinstance(_MissingMethod(), ThemeProvider)


def test_run_is_exported_from_the_package() -> None:
    assert exported_run is run


def test_activation_applies_the_current_theme(qapp: QApplication, paper: StyleSheetProvider) -> None:
    assert qapp.styleSheet() == "QLabel { color: #222222; }"
    assert qapp.palette().window().color().name() == "#fdf6e3"
    assert qapp.font().pointSize() == 10


def test_the_switch_lists_the_providers_themes_and_switching_follows_it(qtbot, recording_registry, paper: StyleSheetProvider, qapp) -> None:
    registry, seen = recording_registry
    window = _window(qtbot, registry, paper)
    switch = _switch(window)
    assert [switch.itemText(i) for i in range(switch.count())] == ["Paper", "Ink"]
    assert switch.currentText() == "Paper"
    assert seen == ["Paper"]

    switch.setCurrentIndex(1)

    assert paper.calls == ["Ink"]
    assert seen == ["Paper", "Ink"]
    assert qapp.palette().window().color().name() == "#101418"
    preview = window.current_preview_widget()
    assert isinstance(preview, QLabel)
    assert preview.text() == "Ink Hi"


def test_ctrl_t_switches_through_the_provider_and_wraps(qtbot, recording_registry, paper: StyleSheetProvider) -> None:
    registry, seen = recording_registry
    window = _window(qtbot, registry, paper)
    show_active(qtbot, window)

    QTest.keyClick(window, Qt.Key.Key_T, Qt.KeyboardModifier.ControlModifier)
    assert paper.current_theme() == "Ink"
    assert _switch(window).currentText() == "Ink"
    QTest.keyClick(window, Qt.Key.Key_T, Qt.KeyboardModifier.ControlModifier)
    assert paper.current_theme() == "Paper"
    assert _switch(window).currentText() == "Paper"
    assert seen == ["Paper", "Ink", "Paper"]


def test_a_provider_initiated_change_updates_the_switch_and_rerenders(qtbot, recording_registry, paper: StyleSheetProvider) -> None:
    registry, seen = recording_registry
    window = _window(qtbot, registry, paper)

    paper.current = "Ink"
    paper.simulate_external_change()

    assert _switch(window).currentText() == "Ink"
    assert seen == ["Paper", "Ink"]
    assert paper.calls == []


def test_an_unknown_theme_raises_without_calling_the_provider(qtbot, recording_registry, paper: StyleSheetProvider) -> None:
    registry, seen = recording_registry
    window = _window(qtbot, registry, paper)
    first = window.current_preview_widget()
    with pytest.raises(ValueError, match="Sepia"):
        window.set_theme("Sepia")
    assert paper.calls == []
    assert window.current_preview_widget() is first
    assert seen == ["Paper"]


def test_deactivate_restores_everything_including_the_font(qapp: QApplication, restore_application_look: None) -> None:
    palette, style_sheet, font = QPalette(qapp.palette()), qapp.styleSheet(), QFont(qapp.font())
    provider = StyleSheetProvider()
    provider.activate(qapp)
    assert qapp.font() != font
    provider.deactivate()
    assert qapp.palette() == palette
    assert qapp.styleSheet() == style_sheet
    assert qapp.font() == font


def test_the_builtin_provider_restores_the_font_and_clears_its_callbacks(qapp: QApplication, restore_application_look: None) -> None:
    font = QFont(qapp.font())
    provider = BuiltinThemeProvider()
    calls: list[str] = []
    provider.on_changed(lambda: calls.append("changed"))
    provider.activate(qapp)
    qapp.setFont(QFont("Courier", 17))
    provider.set_theme("Dark")
    assert calls == ["changed"]

    provider.deactivate()
    provider.set_theme("Light")

    assert calls == ["changed"]
    assert qapp.font() == font


def test_the_callbacks_are_cleared_on_deactivate_and_a_dead_windows_callback_is_harmless(
    qapp: QApplication, restore_application_look: None, recording_registry
) -> None:
    registry, seen = recording_registry
    provider = StyleSheetProvider()
    provider.activate(qapp)
    window = GalleryWindow(registry, provider)
    shiboken6.delete(window)
    assert not shiboken6.isValid(window)

    provider.set_theme("Ink")

    assert seen == ["Paper"]
    provider.deactivate()
    provider.simulate_external_change()
    assert seen == ["Paper"]


def test_run_warns_about_a_property_the_provider_did_not_restore(
    qapp: QApplication, restore_application_look: None, registry: StoryRegistry, caplog: pytest.LogCaptureFixture
) -> None:
    font = QFont(qapp.font())
    QTimer.singleShot(0, qapp.quit)
    with caplog.at_level(logging.WARNING, logger="pyside6_storybook.app"):
        assert run(registry, argv=[], theme_provider=LeakyProvider()) == 0
    warnings = [record.getMessage() for record in caplog.records if record.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "LeakyProvider" in warnings[0]
    assert "font" in warnings[0]
    assert "palette" not in warnings[0]
    assert "style sheet" not in warnings[0]
    assert qapp.font() != font


def test_run_does_not_warn_about_a_provider_that_restores_everything(
    qapp: QApplication, restore_application_look: None, registry: StoryRegistry, caplog: pytest.LogCaptureFixture
) -> None:
    QTimer.singleShot(0, qapp.quit)
    with caplog.at_level(logging.WARNING, logger="pyside6_storybook.app"):
        assert run(registry, argv=[], theme_provider=StyleSheetProvider(), theme="Ink") == 0
    assert [record for record in caplog.records if record.levelno >= logging.WARNING] == []


def test_run_rejects_an_unknown_theme_and_lists_the_names(qapp: QApplication, restore_application_look: None, registry: StoryRegistry) -> None:
    provider = StyleSheetProvider()
    with pytest.raises(ValueError, match="Sepia.*Paper.*Ink"):
        run(registry, argv=[], theme="Sepia", theme_provider=provider)
    assert provider.calls == []


def test_a_raising_provider_shows_the_error_panel_and_the_window_stays_usable(
    qtbot, registry: StoryRegistry, qapp: QApplication, restore_application_look: None, caplog: pytest.LogCaptureFixture
) -> None:
    provider = RaisingProvider()
    provider.activate(qapp)
    try:
        window = _window(qtbot, registry, provider)
        with caplog.at_level(logging.ERROR, logger="GalleryWindow"):
            window.set_theme("Ink")

        panel = window.findChild(ErrorPanel)
        assert panel is not None
        assert "Theme provider failed: RuntimeError: boom" in _texts(panel)
        assert any(record.exc_info for record in caplog.records)
        assert _switch(window).currentText() == "Paper"

        assert window.select_story("Display/Label")
        assert isinstance(window.current_preview_widget(), QLabel)
    finally:
        provider.deactivate()


def _texts(panel: ErrorPanel) -> list[str]:
    return [label.text() for label in panel.findChildren(QLabel)]


def test_the_provider_does_not_keep_the_window_alive(qapp: QApplication, restore_application_look: None, registry: StoryRegistry) -> None:
    provider = StyleSheetProvider()
    provider.activate(qapp)
    try:
        window = GalleryWindow(registry, provider)
        reference = weakref.ref(window)
        window.deleteLater()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        del window
        gc.collect()
        assert reference() is None
        provider.set_theme("Ink")
    finally:
        provider.deactivate()

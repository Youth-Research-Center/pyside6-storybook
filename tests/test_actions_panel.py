import gc
import weakref

import pytest
import shiboken6
from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QAccessible, QAccessibleEvent, QHideEvent
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QSlider, QTabWidget, QWidget

from pyside6_storybook import StoryContext, StoryRegistry, load_stories
from pyside6_storybook.cli import EXAMPLES_MODULE
from pyside6_storybook.gui.actions_panel import ANNOUNCE_INTERVAL_MS, MAX_ARGUMENT_CHARS, MAX_ENTRIES, ActionsPanel, format_arguments
from pyside6_storybook.gui.window import GalleryWindow
from pyside6_storybook.registry.rendering import render_story
from pyside6_storybook.themes import BuiltinThemeProvider


@pytest.fixture
def announcements(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """The text of every accessibility announcement the panels send."""
    sent: list[str] = []

    def update(event: QAccessibleEvent) -> None:
        if event.type() == QAccessible.Event.Announcement:
            sent.append(event.__class__.__name__)

    monkeypatch.setattr(QAccessible, "updateAccessibility", update)
    return sent


def _panel(qtbot) -> ActionsPanel:
    panel = ActionsPanel()
    qtbot.addWidget(panel)
    return panel


def test_an_action_shows_time_name_and_arguments_newest_first(qtbot) -> None:
    panel = _panel(qtbot)

    panel.record("first", (1,))
    panel.record("second", ("a", None))
    panel.record("third", ())

    rows = panel.rows()
    assert [(name, arguments) for _time, name, arguments in rows] == [("third", ""), ("second", "'a', None"), ("first", "1")]
    assert all(len(time) == len("12:34:56.789") and time[2] == ":" and time[8] == "." for time, _name, _arguments in rows)
    assert panel.status_text() == "3 actions logged"


def test_the_status_is_singular_for_one_action_and_counts_zero(qtbot) -> None:
    panel = _panel(qtbot)
    assert panel.status_text() == "0 actions logged"

    panel.record("only", ())

    assert panel.status_text() == "1 action logged"


def test_long_arguments_are_truncated_to_the_limit() -> None:
    text = format_arguments(tuple("x" * 1000 for _ in range(10)))

    assert len(text) <= MAX_ARGUMENT_CHARS
    assert text.endswith("…")
    assert len(format_arguments(("x" * 1000, list(range(1000))))) < MAX_ARGUMENT_CHARS
    assert "xxxx...xxxx" in format_arguments(("x" * 1000,))
    assert format_arguments((5,)) == "5"
    assert format_arguments(()) == ""


def test_a_long_argument_is_truncated_in_the_panel(qtbot) -> None:
    panel = _panel(qtbot)

    panel.record("big", ("y" * 5000,))

    assert len(panel.rows()[0][2]) <= MAX_ARGUMENT_CHARS


def test_only_the_newest_entries_are_kept(qtbot) -> None:
    panel = _panel(qtbot)

    for number in range(MAX_ENTRIES + 20):
        panel.record("tick", (number,))

    assert panel.count() == MAX_ENTRIES
    rows = panel.rows()
    assert rows[0][2] == str(MAX_ENTRIES + 19)
    assert rows[-1][2] == "20"


def test_clear_removes_every_entry_and_updates_the_count(qtbot) -> None:
    panel = _panel(qtbot)
    panel.record("a", ())
    panel.record("b", ())
    button = panel.findChild(QPushButton, "sbkActionsClear")
    assert button is not None

    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)

    assert panel.count() == 0
    assert panel.status_text() == "0 actions logged"
    assert not button.icon().isNull()
    assert button.text() == "Clear"
    assert button.accessibleName()


def test_a_sink_of_an_older_generation_is_ignored(qtbot) -> None:
    panel = _panel(qtbot)
    old = panel.new_sink()
    current = panel.new_sink()

    old.record("stale", ())
    current.record("fresh", ())

    assert [name for _time, name, _arguments in panel.rows()] == ["fresh"]
    panel.invalidate()
    current.record("after invalidate", ())
    assert panel.count() == 1


def test_a_burst_of_actions_is_announced_once(qtbot, announcements: list[str]) -> None:
    panel = _panel(qtbot)

    for _ in range(10):
        panel.record("tick", ())
    qtbot.waitUntil(lambda: len(announcements) == 1, timeout=ANNOUNCE_INTERVAL_MS * 6)
    qtbot.wait(ANNOUNCE_INTERVAL_MS * 2)

    assert announcements == ["QAccessibleAnnouncementEvent"]
    panel.record("later", ())
    qtbot.waitUntil(lambda: len(announcements) == 2, timeout=ANNOUNCE_INTERVAL_MS * 6)


def test_the_announcement_is_polite_and_carries_the_count(qtbot, monkeypatch: pytest.MonkeyPatch) -> None:
    events = []
    monkeypatch.setattr(QAccessible, "updateAccessibility", events.append)
    panel = _panel(qtbot)

    panel.record("a", ())
    panel.record("b", ())
    qtbot.waitUntil(lambda: len(events) == 1, timeout=ANNOUNCE_INTERVAL_MS * 6)

    assert events[0].politeness() == QAccessible.AnnouncementPoliteness.Polite
    assert events[0].message() == "2 actions logged"


def test_the_slot_and_what_it_captured_are_freed_with_the_preview_widget(qtbot, qapp: QApplication) -> None:
    class Sink:
        def record(self, name: str, args: tuple[object, ...]) -> None:
            pass

    sink = Sink()
    ref = weakref.ref(sink)
    button = QPushButton()
    StoryContext(args={}, actions=sink).log_signal(button.clicked)
    del sink
    gc.collect()
    assert ref() is not None

    button.deleteLater()
    del button
    qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    gc.collect()

    assert ref() is None


def _logging_registry() -> StoryRegistry:
    stories = StoryRegistry()

    @stories.story("Logging/Button")
    def button(ctx: StoryContext) -> QWidget:
        widget = QPushButton("go")
        ctx.log_signal(widget.clicked)
        return widget

    @stories.story("Logging/Slider")
    def slider(ctx: StoryContext) -> QWidget:
        widget = QSlider(Qt.Orientation.Horizontal)
        ctx.log_signal(widget.valueChanged)
        return widget

    @stories.story("Logging/Label", controls=[])
    def label(ctx: StoryContext) -> QWidget:
        return QLabel("plain")

    return stories


def _window(qtbot, stories: StoryRegistry, themes: BuiltinThemeProvider) -> tuple[GalleryWindow, ActionsPanel]:
    window = GalleryWindow(stories, themes)
    qtbot.addWidget(window)
    panel = window.findChild(ActionsPanel)
    assert panel is not None
    return window, panel


def test_a_story_that_logs_signals_renders_under_a_plain_context(qtbot) -> None:
    stories = _logging_registry()
    story = stories.get("Logging/Button")

    rendered = render_story(story, StoryContext(args={}), registry=stories)
    qtbot.addWidget(rendered.root)

    assert isinstance(rendered.widget, QPushButton)
    qtbot.mouseClick(rendered.widget, Qt.MouseButton.LeftButton)


def test_clicking_the_example_button_logs_clicked_without_arguments(qtbot, stories: StoryRegistry, themes: BuiltinThemeProvider) -> None:
    window, panel = _window(qtbot, load_stories([EXAMPLES_MODULE]).registry, themes)
    window.select_story("Buttons/Push Button/Default")
    button = window.current_preview_widget()
    assert isinstance(button, QPushButton)

    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)

    assert [(name, arguments) for _time, name, arguments in panel.rows()] == [("clicked", "")]


def test_moving_the_example_slider_logs_the_new_value(qtbot, stories: StoryRegistry, themes: BuiltinThemeProvider) -> None:
    window, panel = _window(qtbot, load_stories([EXAMPLES_MODULE]).registry, themes)
    window.select_story("Inputs/Slider")
    slider = window.current_preview_widget()
    assert isinstance(slider, QSlider)

    slider.setValue(7)

    assert [(name, arguments) for _time, name, arguments in panel.rows()] == [("valueChanged", "7")]


def test_the_side_pane_has_controls_and_actions_tabs(qtbot, themes: BuiltinThemeProvider) -> None:
    window, panel = _window(qtbot, _logging_registry(), themes)

    tabs = window.findChild(QTabWidget, "sbkSideTabs")
    assert tabs is not None
    assert [tabs.tabText(index) for index in range(tabs.count())] == ["Controls", "Actions"]
    assert tabs.documentMode()
    assert tabs.widget(1) is panel
    assert window.findChild(QWidget, "sbkControlsScroll") is tabs.widget(0)


class _Pinger(QWidget):
    """A widget that emits a logged signal while it is being hidden."""

    ping = Signal()

    def hideEvent(self, event: QHideEvent) -> None:
        self.ping.emit()
        super().hideEvent(event)


def _pinger_window(qtbot, themes: BuiltinThemeProvider) -> tuple[GalleryWindow, ActionsPanel]:
    stories = StoryRegistry()

    @stories.story("Logging/Pinger")
    def pinger(ctx: StoryContext) -> QWidget:
        widget = _Pinger()
        ctx.log_signal(widget.ping)
        return widget

    window, panel = _window(qtbot, stories, themes)
    window.show()
    qtbot.waitExposed(window)
    preview = window.current_preview_widget()
    assert preview is not None
    qtbot.waitUntil(preview.isVisible, timeout=2000)
    return window, panel


def test_a_signal_emitted_while_the_old_preview_is_hidden_is_not_logged_on_rebuild(qtbot, themes: BuiltinThemeProvider) -> None:
    window, panel = _pinger_window(qtbot, themes)

    window.set_theme("Dark")

    assert panel.count() == 0


def test_a_signal_emitted_while_the_window_closes_is_not_logged(qtbot, themes: BuiltinThemeProvider) -> None:
    window, panel = _pinger_window(qtbot, themes)

    window.close()

    assert panel.count() == 0


def test_the_new_preview_logs_after_a_rebuild(qtbot, themes: BuiltinThemeProvider) -> None:
    window, panel = _pinger_window(qtbot, themes)
    window.set_theme("Dark")
    preview = window.current_preview_widget()
    assert isinstance(preview, _Pinger)

    preview.ping.emit()

    assert panel.count() == 1


def test_selecting_another_story_clears_the_log(qtbot, themes: BuiltinThemeProvider) -> None:
    window, panel = _window(qtbot, _logging_registry(), themes)
    button = window.current_preview_widget()
    assert isinstance(button, QPushButton)
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
    assert panel.count() == 1

    window.select_story("Logging/Slider")

    assert panel.count() == 0


def test_the_log_is_kept_when_the_same_story_renders_again(qtbot, themes: BuiltinThemeProvider) -> None:
    window, panel = _window(qtbot, _logging_registry(), themes)
    first = window.current_preview_widget()
    assert isinstance(first, QPushButton)
    qtbot.mouseClick(first, Qt.MouseButton.LeftButton)

    window.set_theme("Dark")
    second = window.current_preview_widget()
    assert second is not first
    assert isinstance(second, QPushButton)
    qtbot.mouseClick(second, Qt.MouseButton.LeftButton)

    assert [name for _time, name, _arguments in panel.rows()] == ["clicked", "clicked"]


def test_set_registry_keeps_the_log_for_the_same_story_and_clears_it_for_another(qtbot, themes: BuiltinThemeProvider) -> None:
    window, panel = _window(qtbot, _logging_registry(), themes)
    button = window.current_preview_widget()
    assert isinstance(button, QPushButton)
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)

    window.set_registry(_logging_registry())
    assert panel.count() == 1

    smaller = StoryRegistry()

    @smaller.story("Other/Story")
    def other(ctx: StoryContext) -> QWidget:
        return QLabel("other")

    window.set_registry(smaller)
    assert window.current_story_id() == "Other/Story"
    assert panel.count() == 0


def test_a_replaced_preview_widget_cannot_log_any_more(qtbot, themes: BuiltinThemeProvider, qapp: QApplication) -> None:
    window, panel = _window(qtbot, _logging_registry(), themes)
    old = window.current_preview_widget()
    assert isinstance(old, QPushButton)

    window.set_theme("Dark")
    old.click()

    assert panel.count() == 0
    qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert not shiboken6.isValid(old)

import itertools
import os
import re
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QApplication, QComboBox, QLabel, QLineEdit
from story_files import story_source, write

from pyside6_storybook import StoryContext, StoryRegistry, load_stories
from pyside6_storybook.discovery.reload import ReloadResult, ReloadSession
from pyside6_storybook.discovery.sources import EXAMPLES_FOLDER
from pyside6_storybook.gui.actions_panel import ActionsPanel
from pyside6_storybook.gui.canvas import Canvas
from pyside6_storybook.gui.error_panel import ErrorPanel
from pyside6_storybook.gui.reload_status import ReloadStatus
from pyside6_storybook.gui.reload_watcher import ReloadWatcher
from pyside6_storybook.gui.window import GalleryWindow
from pyside6_storybook.themes import BuiltinThemes

_clock = itertools.count(2_100_000_000, 10)
_WAIT_MS = 5000
_SHORT_DEBOUNCE_MS = 50
_NEGATIVE_WAIT_MS = 600  # how long to watch for a reload that must not happen


def _write(root: Path, relative: str, source: str) -> Path:
    path = write(root, relative, source)
    stamp = next(_clock)
    os.utime(path, (stamp, stamp))
    return path


def _session(root: Path, targets: tuple[str, ...] = ("stories",)) -> ReloadSession:
    return ReloadSession(targets, cwd=root, initial=load_stories(targets, cwd=root))


@pytest.fixture
def make_watcher() -> Iterator[Callable[..., tuple[ReloadWatcher, list[ReloadResult]]]]:
    """Create watchers that are deleted after the test, with a list of the results each one emits."""
    watchers: list[ReloadWatcher] = []

    def make(session: ReloadSession, *, debounce_ms: int = _SHORT_DEBOUNCE_MS) -> tuple[ReloadWatcher, list[ReloadResult]]:
        watcher = ReloadWatcher(session, debounce_ms=debounce_ms)
        watchers.append(watcher)
        results: list[ReloadResult] = []
        watcher.reloaded.connect(results.append)
        return watcher, results

    try:
        yield make
    finally:
        for watcher in watchers:
            watcher.deleteLater()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def _label_text(result: ReloadResult, story_id: str) -> str:
    widget = result.load.registry.get(story_id)(StoryContext(args={}))
    assert isinstance(widget, QLabel)
    return widget.text()


def test_trigger_now_reloads_once_and_emits_the_result(qtbot, make_watcher, tmp_path: Path, stories: StoryRegistry) -> None:
    _write(tmp_path, "stories/a_story.py", story_source("Inputs/A", "'one'"))
    watcher, results = make_watcher(_session(tmp_path))

    _write(tmp_path, "stories/a_story.py", story_source("Inputs/A", "'two'"))
    watcher.trigger_now()

    assert len(results) == 1
    assert results[0].accepted
    assert _label_text(results[0], "Inputs/A") == "two"


def test_every_story_file_and_folder_below_a_folder_target_is_watched(qtbot, make_watcher, tmp_path: Path, stories: StoryRegistry) -> None:
    a_path = _write(tmp_path, "stories/a_story.py", story_source("Inputs/A"))
    _write(tmp_path, "stories/deep/er/b_story.py", story_source("Inputs/B"))
    watcher, _ = make_watcher(_session(tmp_path))

    watched = set(watcher.watched_paths())

    assert str(a_path) in watched
    assert str(tmp_path / "stories" / "deep" / "er" / "b_story.py") in watched
    assert {str(tmp_path / "stories"), str(tmp_path / "stories" / "deep"), str(tmp_path / "stories" / "deep" / "er")} <= watched


def test_a_real_edit_is_picked_up(qtbot, make_watcher, tmp_path: Path, stories: StoryRegistry) -> None:
    path = _write(tmp_path, "stories/a_story.py", story_source("Inputs/A", "'one'"))
    watcher, results = make_watcher(_session(tmp_path), debounce_ms=300)

    path.write_text(story_source("Inputs/A", "'two'"), encoding="utf-8")
    qtbot.waitUntil(lambda: len(results) == 1, timeout=_WAIT_MS)

    assert results[0].accepted
    assert _label_text(results[0], "Inputs/A") == "two"
    assert watcher.watched_paths()


def test_a_rename_save_is_watched_again(qtbot, make_watcher, tmp_path: Path, stories: StoryRegistry) -> None:
    path = _write(tmp_path, "stories/a_story.py", story_source("Inputs/A", "'one'"))
    _, results = make_watcher(_session(tmp_path))

    for text in ("'two'", "'three'"):
        before = len(results)
        scratch = _write(tmp_path, "stories/a_story.py.tmp", story_source("Inputs/A", text))
        os.replace(scratch, path)
        qtbot.waitUntil(lambda before=before: len(results) > before, timeout=_WAIT_MS)
        assert _label_text(results[-1], "Inputs/A") == text.strip("'")


def test_a_new_story_file_in_a_subfolder_triggers_a_reload(qtbot, make_watcher, tmp_path: Path, stories: StoryRegistry) -> None:
    _write(tmp_path, "stories/a_story.py", story_source("Inputs/A"))
    watcher, results = make_watcher(_session(tmp_path))
    sub = tmp_path / "stories" / "sub"
    sub.mkdir()
    qtbot.waitUntil(lambda: str(sub) in watcher.watched_paths(), timeout=_WAIT_MS)
    assert results == []

    _write(tmp_path, "stories/sub/c_story.py", story_source("Inputs/C"))
    qtbot.waitUntil(lambda: len(results) == 1, timeout=_WAIT_MS)

    assert results[0].load.registry.ids() == ["Inputs/A", "Inputs/C"]


def test_a_swap_file_does_not_trigger_a_reload(qtbot, make_watcher, tmp_path: Path, stories: StoryRegistry) -> None:
    _write(tmp_path, "stories/a_story.py", story_source("Inputs/A"))
    watcher, results = make_watcher(_session(tmp_path))
    assert watcher.watched_paths()

    for name in (".a_story.py.swp", "a_story.py~", "#a_story.py#", "a_story.py.bak"):
        _write(tmp_path, f"stories/{name}", "swap")
    qtbot.wait(_NEGATIVE_WAIT_MS)

    assert results == []


def test_a_burst_of_changes_runs_one_reload(qtbot, make_watcher, tmp_path: Path, stories: StoryRegistry) -> None:
    path = _write(tmp_path, "stories/a_story.py", story_source("Inputs/A", "'one'"))
    _, results = make_watcher(_session(tmp_path), debounce_ms=200)

    for text in ("'two'", "'three'", "'four'", "'five'"):
        path.write_text(story_source("Inputs/A", text), encoding="utf-8")
        qtbot.wait(10)
    qtbot.waitUntil(lambda: len(results) >= 1, timeout=_WAIT_MS)
    qtbot.wait(_NEGATIVE_WAIT_MS)

    assert len(results) == 1
    assert _label_text(results[0], "Inputs/A") == "five"


def test_a_story_file_that_failed_to_import_is_picked_up_when_it_is_fixed(qtbot, make_watcher, tmp_path: Path, stories: StoryRegistry) -> None:
    _write(tmp_path, "stories/a_story.py", story_source("Inputs/A"))
    broken = _write(tmp_path, "stories/b_story.py", "def broken(:\n")
    session = _session(tmp_path)
    assert len(session.last_accepted.errors) == 1
    watcher, results = make_watcher(session)
    assert str(broken) in watcher.watched_paths()

    broken.write_text(story_source("Inputs/B"), encoding="utf-8")
    qtbot.waitUntil(lambda: len(results) == 1, timeout=_WAIT_MS)

    assert results[0].accepted
    assert results[0].load.registry.ids() == ["Inputs/A", "Inputs/B"]
    assert results[0].load.errors == ()


def test_the_files_are_still_watched_after_a_rejected_reload(qtbot, make_watcher, tmp_path: Path, stories: StoryRegistry) -> None:
    path = _write(tmp_path, "stories/a_story.py", story_source("Inputs/A", "'one'"))
    watcher, results = make_watcher(_session(tmp_path))

    path.write_text("def broken(:\n", encoding="utf-8")
    qtbot.waitUntil(lambda: len(results) == 1, timeout=_WAIT_MS)
    assert not results[0].accepted
    assert str(path) in watcher.watched_paths()
    path.write_text(story_source("Inputs/A", "'fixed'"), encoding="utf-8")
    qtbot.waitUntil(lambda: len(results) == 2, timeout=_WAIT_MS)

    assert results[1].accepted
    assert _label_text(results[1], "Inputs/A") == "fixed"


# The window


_ENUM_STORY = """
from enum import Enum

from PySide6.QtWidgets import QLabel

from pyside6_storybook import EnumControl, TextControl, story
from shapes import Shape


@story("Shapes/Shape", controls=[EnumControl("shape", Shape.CIRCLE), TextControl("text", "start")])
def build(ctx):
    return QLabel(ctx.args["shape"].name + ":" + ctx.args["text"] + ":{marker}")
"""
_SHAPES = """
from enum import Enum


class Shape(Enum):
    CIRCLE = 1
    SQUARE = 2
{extra}
"""
_TEXT_STORY = """
from PySide6.QtWidgets import QLabel

from pyside6_storybook import TextControl, story


@story("{story_id}", controls=[TextControl("text", "start")])
def build(ctx):
    return QLabel(ctx.args["text"] + ":{marker}")
"""


def _window(qtbot, session: ReloadSession, registry: StoryRegistry, themes: BuiltinThemes) -> tuple[GalleryWindow, ReloadWatcher]:
    window = GalleryWindow(registry, themes, reload=session)
    qtbot.addWidget(window)
    watcher = window.findChild(ReloadWatcher)
    assert watcher is not None
    return window, watcher


def _status(window: GalleryWindow) -> ReloadStatus:
    status = window.findChild(ReloadStatus)
    assert status is not None
    return status


def _has_item(combo: QComboBox, prefix: str) -> bool:
    return combo.findText(prefix, Qt.MatchFlag.MatchStartsWith) >= 0


def _error_panel(window: GalleryWindow) -> ErrorPanel | None:
    panels = [panel for panel in window.findChildren(ErrorPanel) if panel.isVisibleTo(window)]
    assert len(panels) <= 1
    return panels[0] if panels else None


def _preview_text(window: GalleryWindow) -> str:
    widget = window.current_preview_widget()
    assert isinstance(widget, QLabel)
    return widget.text()


def _text_editor(window: GalleryWindow) -> QLineEdit:
    editor = next(e for e in window.findChildren(QLineEdit) if e.objectName() == "" and e.isVisibleTo(window))
    return editor


def _started(qtbot, tmp_path: Path, themes: BuiltinThemes, files: dict[str, str]) -> tuple[GalleryWindow, ReloadWatcher]:
    for relative, source in files.items():
        _write(tmp_path, relative, source)
    session = _session(tmp_path)
    return _window(qtbot, session, session.last_accepted.registry, themes)


def test_a_window_without_a_reload_session_has_no_watcher_and_no_status_bar(qtbot, registry: StoryRegistry, themes: BuiltinThemes) -> None:
    window = GalleryWindow(registry, themes)
    qtbot.addWidget(window)

    assert window.findChild(ReloadWatcher) is None
    assert window.statusBar().isHidden()


def test_an_accepted_reload_keeps_the_story_and_its_control_values_and_reports_the_time(
    qtbot, tmp_path: Path, stories: StoryRegistry, themes: BuiltinThemes
) -> None:
    window, watcher = _started(qtbot, tmp_path, themes, {"stories/a_story.py": _TEXT_STORY.format(story_id="Inputs/A", marker="one")})
    assert not window.statusBar().isHidden()
    assert _status(window).text() == ""
    editor = _text_editor(window)
    editor.selectAll()
    qtbot.keyClicks(editor, "typed")
    assert _preview_text(window) == "typed:one"

    _write(tmp_path, "stories/a_story.py", _TEXT_STORY.format(story_id="Inputs/A", marker="two"))
    watcher.trigger_now()

    assert window.current_story_id() == "Inputs/A"
    assert _preview_text(window) == "typed:two"
    label = window.findChild(QLabel, "reloadStatus")
    assert label is not None
    assert re.fullmatch(r"Reloaded \d\d:\d\d:\d\d", label.text())
    assert label.accessibleName() == "Reload status"
    assert label.accessibleDescription() == label.text()


def test_an_enum_value_is_matched_by_name_in_the_reloaded_class(qtbot, tmp_path: Path, stories: StoryRegistry, themes: BuiltinThemes) -> None:
    window, watcher = _started(
        qtbot,
        tmp_path,
        themes,
        {"shapes.py": _SHAPES.format(extra=""), "stories/a_story.py": _ENUM_STORY.format(marker="one")},
    )
    combo = next(c for c in window.findChildren(QComboBox) if c.findText("SQUARE") >= 0)
    combo.setCurrentIndex(combo.findText("SQUARE"))
    assert _preview_text(window) == "SQUARE:start:one"

    _write(tmp_path, "shapes.py", _SHAPES.format(extra="    TRIANGLE = 3"))
    watcher.trigger_now()

    assert _preview_text(window) == "SQUARE:start:one"
    new_combo = next(c for c in window.findChildren(QComboBox) if c.findText("TRIANGLE") >= 0)
    assert new_combo.currentText() == "SQUARE"


def test_an_enum_value_whose_name_is_gone_starts_at_the_default(qtbot, tmp_path: Path, stories: StoryRegistry, themes: BuiltinThemes) -> None:
    window, watcher = _started(
        qtbot,
        tmp_path,
        themes,
        {"shapes.py": _SHAPES.format(extra=""), "stories/a_story.py": _ENUM_STORY.format(marker="one")},
    )
    combo = next(c for c in window.findChildren(QComboBox) if c.findText("SQUARE") >= 0)
    combo.setCurrentIndex(combo.findText("SQUARE"))

    _write(tmp_path, "shapes.py", "from enum import Enum\n\n\nclass Shape(Enum):\n    CIRCLE = 1\n    OVAL = 2\n")
    watcher.trigger_now()

    assert _preview_text(window) == "CIRCLE:start:one"


def test_a_removed_story_falls_back_to_the_story_at_its_row_then_the_previous_one(
    qtbot, tmp_path: Path, stories: StoryRegistry, themes: BuiltinThemes
) -> None:
    window, watcher = _started(
        qtbot,
        tmp_path,
        themes,
        {f"stories/{name}_story.py": _TEXT_STORY.format(story_id=f"Inputs/{name.upper()}", marker=name) for name in "abc"},
    )
    window.select_story("Inputs/B")
    (tmp_path / "stories" / "b_story.py").unlink()
    watcher.trigger_now()
    assert window.current_story_id() == "Inputs/C"

    (tmp_path / "stories" / "c_story.py").unlink()
    watcher.trigger_now()
    assert window.current_story_id() == "Inputs/A"


def test_theme_canvas_settings_and_the_actions_log_are_untouched_by_a_reload(
    qtbot, tmp_path: Path, stories: StoryRegistry, themes: BuiltinThemes
) -> None:
    window, watcher = _started(qtbot, tmp_path, themes, {"stories/a_story.py": _TEXT_STORY.format(story_id="Inputs/A", marker="one")})
    window.set_theme("Dark")
    canvas = window.findChild(Canvas)
    assert canvas is not None
    canvas.set_zoom(200)
    background = window.findChild(QComboBox, "canvasBackground")
    assert background is not None
    background.setCurrentIndex(1)
    panel = window.findChild(ActionsPanel)
    assert panel is not None
    panel.record("kept", ())

    _write(tmp_path, "stories/a_story.py", _TEXT_STORY.format(story_id="Inputs/A", marker="two"))
    watcher.trigger_now()

    assert themes.current == "Dark"
    assert canvas.zoom() == 200
    assert background.currentIndex() == 1
    assert [name for _time, name, _arguments in panel.rows()] == ["kept"]


def test_size_presets_are_read_again_after_a_reload(qtbot, tmp_path: Path, stories: StoryRegistry, themes: BuiltinThemes) -> None:
    source = _TEXT_STORY.format(story_id="Inputs/A", marker="one")
    window, watcher = _started(qtbot, tmp_path, themes, {"stories/a_story.py": source})
    size = window.findChild(QComboBox, "canvasSize")
    assert size is not None
    assert _has_item(size, "Tablet") is False

    preset = "from pyside6_storybook import SizePreset, default_registry\n\ndefault_registry.size_presets.append(SizePreset('Tablet', 768, 1024))\n"
    _write(tmp_path, "stories/a_story.py", preset + source)
    watcher.trigger_now()

    assert _has_item(size, "Tablet")


def test_a_rejected_reload_shows_the_errors_and_keeps_the_stories_until_the_next_accepted_one(
    qtbot, tmp_path: Path, stories: StoryRegistry, themes: BuiltinThemes
) -> None:
    window, watcher = _started(
        qtbot,
        tmp_path,
        themes,
        {
            "stories/a_story.py": _TEXT_STORY.format(story_id="Inputs/A", marker="one"),
            "stories/b_story.py": _TEXT_STORY.format(story_id="Inputs/B", marker="one"),
        },
    )
    _write(tmp_path, "stories/b_story.py", "def broken(:\n")
    watcher.trigger_now()

    panel = _error_panel(window)
    assert panel is not None
    assert panel.title() == "1 story source failed to load"
    assert str(tmp_path / "stories" / "b_story.py") in panel.details()
    assert window.current_story_id() == "Inputs/A"
    assert re.fullmatch(r"Reload failed \d\d:\d\d:\d\d: 1 story source failed to load", _status(window).text())
    assert stories.ids() == ["Inputs/A", "Inputs/B"]

    editor = _text_editor(window)
    editor.selectAll()
    qtbot.keyClicks(editor, "again")
    assert _error_panel(window) is None
    assert _preview_text(window) == "again:one"
    assert _status(window).text().startswith("Reload failed")

    _write(tmp_path, "stories/b_story.py", _TEXT_STORY.format(story_id="Inputs/B", marker="two"))
    watcher.trigger_now()

    assert _error_panel(window) is None
    assert _preview_text(window) == "again:one"
    assert _status(window).text().startswith("Reloaded")
    window.select_story("Inputs/B")
    assert _preview_text(window) == "start:two"


def test_a_reload_that_finds_no_stories_says_so(qtbot, tmp_path: Path, stories: StoryRegistry, themes: BuiltinThemes) -> None:
    window, watcher = _started(qtbot, tmp_path, themes, {"stories/a_story.py": _TEXT_STORY.format(story_id="Inputs/A", marker="one")})
    (tmp_path / "stories" / "a_story.py").unlink()

    watcher.trigger_now()

    assert re.fullmatch(r"Reload failed \d\d:\d\d:\d\d: No stories were found", _status(window).text())
    assert window.current_story_id() == "Inputs/A"


def test_the_window_gets_the_example_stories_back_after_a_reload(qtbot, stories: StoryRegistry, themes: BuiltinThemes) -> None:
    targets = (str(EXAMPLES_FOLDER),)
    session = ReloadSession(targets, cwd=Path.cwd(), initial=load_stories(targets))
    window, watcher = _window(qtbot, session, session.last_accepted.registry, themes)
    window.select_story("Inputs/Slider")

    watcher.trigger_now()

    assert window.current_story_id() == "Inputs/Slider"
    assert _status(window).text().startswith("Reloaded")


def test_the_watcher_and_status_are_owned_by_the_window(qtbot, tmp_path: Path, stories: StoryRegistry, themes: BuiltinThemes) -> None:
    window, watcher = _started(qtbot, tmp_path, themes, {"stories/a_story.py": _TEXT_STORY.format(story_id="Inputs/A", marker="one")})

    assert watcher.parent() is window
    assert _status(window).window() is window

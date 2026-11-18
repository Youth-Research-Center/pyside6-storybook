import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication, QLabel
from story_files import story_source, write

import pyside6_storybook
from pyside6_storybook import StoryRegistry
from pyside6_storybook import registry as registry_module
from pyside6_storybook.discovery.sources import StorySources
from pyside6_storybook.registry.rendering import StoryRenderError
from pyside6_storybook.testing.storybook_options import StorybookOptions
from pyside6_storybook.testing.storybook_session import StorybookFailure, StorybookSession


def _session(root: Path, *, themes: tuple[str, ...] | None = ("Light", "Dark"), warnings_fail: bool = True) -> StorybookSession:
    options = StorybookOptions(
        enabled=False,
        targets=("stories",),
        theme_provider=None,
        themes=themes,
        qt_warnings_fail=warnings_fail,
        qt_warnings_ignore=(re.compile("propagateSizeHints"),),
    )
    return StorybookSession(options, StorySources(("stories",), "test"), rootpath=root)


@pytest.fixture
def session(tmp_path: Path, stories: StoryRegistry, qapp: QApplication, restore_application_look: None) -> Iterator[StorybookSession]:
    write(tmp_path, "stories/demo_stories.py", story_source("Demo/First", '"one"'))
    state = _session(tmp_path)
    try:
        yield state
    finally:
        state.finish()


def test_prepare_loads_the_stories_into_a_fresh_registry_and_finish_puts_the_bindings_back(
    tmp_path: Path, stories: StoryRegistry, qapp: QApplication, restore_application_look: None
) -> None:
    write(tmp_path, "stories/demo_stories.py", story_source("Demo/First"))
    state = _session(tmp_path)
    before = (registry_module.default_registry, pyside6_storybook.default_registry)

    state.prepare()
    try:
        assert state.registry is not None
        assert state.registry.ids() == ["Demo/First"]
        assert registry_module.default_registry is pyside6_storybook.default_registry is state.registry
        assert state.registry is not before[0]
        assert state.themes == ("Light", "Dark")
    finally:
        state.finish()

    assert (registry_module.default_registry, pyside6_storybook.default_registry) == before
    assert len(stories) == 0


def test_prepare_does_nothing_the_second_time(session: StorybookSession) -> None:
    session.prepare()
    registry = session.registry

    session.prepare()

    assert session.registry is registry


def test_get_story_returns_a_story_or_lists_the_close_ids(session: StorybookSession) -> None:
    assert session.get_story("Demo/First").id == "Demo/First"
    with pytest.raises(KeyError, match="unknown story 'Demo/Frist'; did you mean: Demo/First"):
        session.get_story("Demo/Frist")
    with pytest.raises(KeyError, match="the stories are: Demo/First"):
        session.get_story("Nothing/Alike")


def test_render_overrides_arguments_and_shows_the_story_in_an_opaque_host(session: StorybookSession) -> None:
    session.prepare()
    story = session.get_story("Demo/First")

    rendered = session.render(story)
    try:
        assert isinstance(rendered.widget, QLabel)
        assert rendered.widget.text() == "one"
        assert rendered.host.isVisible()
        assert rendered.host.autoFillBackground()
        assert rendered.host.backgroundRole() == QPalette.ColorRole.Window
        assert rendered.root.parentWidget() is rendered.host
    finally:
        rendered.dispose()

    assert rendered.host not in QApplication.topLevelWidgets()


def test_the_provider_is_activated_once_and_released_idempotently(session: StorybookSession) -> None:
    session.prepare()
    before = QPalette(QApplication.palette())

    session.set_theme("Dark")
    session.set_theme("Light")

    assert session.active
    session.release_provider()
    session.release_provider()
    assert not session.active
    assert QApplication.palette() == before


def test_a_story_that_raises_leaves_no_widget_behind(session: StorybookSession, tmp_path: Path) -> None:
    write(
        tmp_path,
        "stories/broken_stories.py",
        """
        from PySide6.QtWidgets import QLabel

        from pyside6_storybook import story


        @story("Broken/Half")
        def half(ctx):
            QLabel("built, never returned")
            raise RuntimeError("boom")
        """,
    )
    session.prepare()
    widgets = set(QApplication.topLevelWidgets())

    with pytest.raises(StoryRenderError, match="boom"):
        session.render(session.get_story("Broken/Half"))

    assert set(QApplication.topLevelWidgets()) == widgets


def test_check_story_fails_on_an_unexcused_qt_warning_only_when_asked_to(tmp_path: Path, stories: StoryRegistry, qapp: QApplication) -> None:
    write(
        tmp_path,
        "stories/warn_stories.py",
        """
        from PySide6.QtCore import qWarning
        from PySide6.QtWidgets import QLabel

        from pyside6_storybook import story


        @story("Warn/One")
        def one(ctx):
            qWarning("a warning")
            return QLabel("x")
        """,
    )
    failing, tolerant = _session(tmp_path), _session(tmp_path, warnings_fail=False)
    try:
        failing.prepare()
        story = failing.get_story("Warn/One")
        with pytest.raises(StorybookFailure, match=r"(?s)Qt logged 1 warning.*Warn/One in Light.*warning: a warning"):
            failing.check_story(story, "Light")
        tolerant.prepare()
        tolerant.check_story(story, "Light")
    finally:
        tolerant.finish()
        failing.finish()

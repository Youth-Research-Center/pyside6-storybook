"""The pytest plugin, run with ``pytester`` on small projects. Every test uses the ``stories`` fixture: in-process runs share the
default registry, ``sys.modules`` and ``sys.path`` with the run that tests them."""

import re
import subprocess
import sys
import textwrap
from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import QEvent, qInstallMessageHandler
from PySide6.QtGui import QFont, QPalette
from PySide6.QtWidgets import QApplication
from story_files import write

import pyside6_storybook
from pyside6_storybook import StoryRegistry
from pyside6_storybook import registry as registry_module
from pyside6_storybook.discovery import sources
from pyside6_storybook.testing.storybook_session import NO_STORIES_CONFIGURED

_TWO_THEMES = ("--storybook-themes", "Light,Dark")
_NO_PYTEST_QT = ("-p", "no:pytest-qt")
_WITH_AND_WITHOUT_PYTEST_QT = [pytest.param((), id="pytest-qt"), pytest.param(_NO_PYTEST_QT, id="no-pytest-qt")]

_BUTTONS = """
from PySide6.QtWidgets import QLabel, QPushButton

from pyside6_storybook import TextControl, story


@story("Inputs/Button", controls=[TextControl("text", "Click me")])
def button(ctx):
    return QPushButton(ctx.args["text"])


@story("Inputs/Label")
def label(ctx):
    return QLabel("plain")
"""


def _look(app: QApplication) -> tuple[object, ...]:
    return (app.style().name(), QPalette(app.palette()), app.styleSheet(), QFont(app.font()))


def _handler() -> object:
    current = qInstallMessageHandler(None)
    qInstallMessageHandler(current)
    return current


def _run(pytester: pytest.Pytester, *args: str, setup_errors: bool = False) -> pytest.RunResult:
    """Run pytest in-process in the project, and fail when the run leaves the Qt message handler changed.

    pytest-qt itself leaves its handler installed when a fixture fails in setup, so a run that expects a setup error (``setup_errors``)
    only puts the handler back.
    """
    before = _handler()
    result = pytester.runpytest(*args)
    after = _handler()
    if setup_errors:
        qInstallMessageHandler(before)  # ty: ignore[invalid-argument-type]
    else:
        assert after is before, "the Qt message handler changed"
    return result


@pytest.fixture(autouse=True)
def no_leaked_state(qapp: QApplication) -> Iterator[None]:
    """Fail a test that leaves the default registry, ``sys.path``, the application's look or a top-level widget changed.

    The Qt message handler is checked around each run by ``_run``: pytest-qt installs its own handler per phase, so the handler at setup
    and at teardown are not comparable.
    """
    bindings = (registry_module.default_registry, pyside6_storybook.default_registry)
    path = list(sys.path)
    look = _look(qapp)
    widgets = set(QApplication.topLevelWidgets())
    yield
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert (registry_module.default_registry, pyside6_storybook.default_registry) == bindings, "the default registry bindings changed"
    assert sys.path == path, "sys.path changed"
    assert _look(qapp) == look, "the application's style, palette, style sheet or font changed"
    assert set(QApplication.topLevelWidgets()) - widgets == set(), "a top-level widget was left behind"


@pytest.fixture(autouse=True)
def no_entry_points(no_leaked_state: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Nothing advertises stories, so a project without configuration reaches the built-in examples fallback.

    It depends on ``no_leaked_state`` so that the state is read before ``monkeypatch`` changes anything and compared after it undid it.
    """
    monkeypatch.setattr(sources, "entry_points", lambda group: [])


def _project(pytester: pytest.Pytester, source: str = _BUTTONS, *, ini: str = "", name: str = "demo_stories.py", toml: str = "") -> None:
    pytester.makepyprojecttoml(
        f'[tool.pyside6-storybook]\nstories = ["stories"]\n{toml}\n[tool.pytest.ini_options]\n{ini}\n',
    )
    write(pytester.path, f"stories/{name}", source)


def _story_module(body: str, *, imports: str = "") -> str:
    return f"from PySide6.QtWidgets import QLabel\n{imports}\nfrom pyside6_storybook import story\n\n{textwrap.dedent(body)}"


# --- the plugin is off unless enabled -------------------------------------------------------------------------------------------


def test_the_plugin_collects_nothing_without_the_flag(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _project(pytester)
    pytester.makepyfile(test_plain="def test_plain():\n    pass\n")

    result = _run(pytester, "-v")

    result.assert_outcomes(passed=1)
    assert "storybook::" not in result.stdout.str()


def test_the_ini_option_turns_the_plugin_on(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _project(pytester, ini="storybook = true")

    result = _run(pytester, *_TWO_THEMES)

    result.assert_outcomes(passed=4)


# --- a passing project ----------------------------------------------------------------------------------------------------------


def test_every_story_and_theme_is_one_item_with_a_readable_id(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _project(pytester)

    collected = _run(pytester, "--storybook", *_TWO_THEMES, "--collect-only", "-q")
    result = _run(pytester, "--storybook", *_TWO_THEMES, "-v")

    assert collected.outlines[:4] == [
        "storybook::Inputs/Button[Light]",
        "storybook::Inputs/Button[Dark]",
        "storybook::Inputs/Label[Light]",
        "storybook::Inputs/Label[Dark]",
    ]
    assert "4 tests collected" in collected.outlines[-1]
    result.assert_outcomes(passed=4)
    result.stdout.fnmatch_lines(["storybook::Inputs/Button[[]Light[]] PASSED*", "storybook::Inputs/Label[[]Dark[]] PASSED*"])


def test_without_themes_every_theme_of_the_provider_is_used(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _project(pytester)

    result = _run(pytester, "--storybook", "--collect-only", "-q")

    assert [line for line in result.outlines if line.startswith("storybook::Inputs/Label")] == [
        "storybook::Inputs/Label[Light]",
        "storybook::Inputs/Label[Dark]",
        "storybook::Inputs/Label[System]",
    ]


def test_the_collection_order_is_the_registry_order_then_the_theme_order(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    source = _story_module(
        """
        @story("Zed/Last")
        def last(ctx):
            return QLabel("z")


        @story("Alpha/First")
        def first(ctx):
            return QLabel("a")
        """
    )
    _project(pytester, source)

    first = _run(pytester, "--storybook", "--storybook-themes", "Dark,Light", "--collect-only", "-q").outlines[:4]
    second = _run(pytester, "--storybook", "--storybook-themes", "Dark,Light", "--collect-only", "-q").outlines[:4]

    assert first == second == [
        "storybook::Zed/Last[Dark]",
        "storybook::Zed/Last[Light]",
        "storybook::Alpha/First[Dark]",
        "storybook::Alpha/First[Light]",
    ]


def test_every_item_carries_the_storybook_marker_and_the_marker_is_registered(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _project(pytester)
    pytester.makepyfile(test_plain="def test_plain():\n    pass\n")

    only_plain = _run(pytester, "--storybook", *_TWO_THEMES, "-m", "not storybook", "--strict-markers")
    only_stories = _run(pytester, "--storybook", *_TWO_THEMES, "-m", "storybook", "--strict-markers")

    only_plain.assert_outcomes(passed=1, deselected=4)
    only_stories.assert_outcomes(passed=4, deselected=1)


def test_the_ini_option_still_lets_the_other_tests_run_alone(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _project(pytester, ini="storybook = true")
    pytester.makepyfile(test_plain="def test_plain():\n    pass\n")

    result = _run(pytester, "-m", "not storybook", *_TWO_THEMES)

    result.assert_outcomes(passed=1, deselected=4)


# --- failures -------------------------------------------------------------------------------------------------------------------


def test_a_story_that_raises_fails_with_its_own_traceback(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    source = _story_module(
        """
        @story("Broken/Raises")
        def raises(ctx):
            raise RuntimeError("boom from the story")


        @story("Fine/Label")
        def fine(ctx):
            return QLabel("ok")
        """
    )
    _project(pytester, source)

    result = _run(pytester, "--storybook", *_TWO_THEMES)

    result.assert_outcomes(passed=2, failed=2)
    output = result.stdout.str()
    assert "Broken/Raises raised RuntimeError: boom from the story" in output
    assert "demo_stories.py" in output
    assert 'raise RuntimeError("boom from the story")' in output
    assert "storybook_session.py" not in output
    assert "story_item.py" not in output


def test_a_story_that_returns_none_fails(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    source = _story_module(
        """
        @story("Broken/Nothing")
        def nothing(ctx):
            QLabel("built but not returned")
        """
    )
    _project(pytester, source)

    result = _run(pytester, "--storybook", "--storybook-themes", "Light")

    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*Broken/Nothing returned None, expected a QWidget*", "*A story function must return the widget it builds.*"])


def test_a_decorator_that_raises_fails_the_item(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    source = _story_module(
        """
        def explode(widget, ctx):
            raise ValueError("decorator boom")


        @story("Broken/Decorated", decorators=[explode])
        def decorated(ctx):
            return QLabel("x")
        """
    )
    _project(pytester, source)

    result = _run(pytester, "--storybook", "--storybook-themes", "Light")

    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*decorator*raised ValueError: decorator boom*"])


def test_an_import_error_is_a_failing_load_error_item_and_the_other_stories_still_run(
    pytester: pytest.Pytester, stories: StoryRegistry
) -> None:
    _project(pytester)
    write(pytester.path, "stories/broken_stories.py", "raise ImportError('no such widget library')\n")

    result = _run(pytester, "--storybook", "--storybook-themes", "Light", "-v")

    result.assert_outcomes(passed=2, failed=1)
    result.stdout.fnmatch_lines(["storybook::load-error[[]*broken_stories.py[]] FAILED*", "*ImportError: no such widget library*"])


def test_a_missing_target_is_a_failing_load_error_item(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _project(pytester)

    result = _run(pytester, "--storybook", "--storybook-stories", "stories", "--storybook-stories", "nowhere", "--storybook-themes", "Light")

    result.assert_outcomes(passed=2, failed=1)
    result.stdout.fnmatch_lines(["*no such file, folder or module*"])


# --- selection ------------------------------------------------------------------------------------------------------------------


def test_k_selects_items_by_theme_and_by_story_name(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _project(pytester)

    dark = _run(pytester, "--storybook", *_TWO_THEMES, "-k", "Dark", "--collect-only", "-q")
    inputs = _run(pytester, "--storybook", *_TWO_THEMES, "-k", "Inputs and not Label", "--collect-only", "-q")

    assert dark.outlines[:2] == ["storybook::Inputs/Button[Dark]", "storybook::Inputs/Label[Dark]"]
    assert inputs.outlines[:2] == ["storybook::Inputs/Button[Light]", "storybook::Inputs/Button[Dark]"]
    assert "2/4 tests collected (2 deselected)" in inputs.outlines[-1]


def test_deselect_removes_one_item_by_node_id(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _project(pytester)

    result = _run(pytester, "--storybook", *_TWO_THEMES, "--deselect", "storybook::Inputs/Button[Dark]", "-v")

    result.assert_outcomes(passed=3, deselected=1)
    assert "Inputs/Button[Dark]" not in result.stdout.str().replace("deselected", "")


def test_a_node_id_cannot_be_given_as_an_argument(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _project(pytester)

    result = _run(pytester, "--storybook", "storybook::Inputs/Button[Dark]")

    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines(["*not found*"])


def test_the_project_conftest_sees_the_story_items_in_collection_modifyitems(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _project(pytester)
    pytester.makeconftest(
        """
        def pytest_collection_modifyitems(items):
            names = [item.nodeid for item in items]
            assert "storybook::Inputs/Label[Dark]" in names, names
        """
    )

    result = _run(pytester, "--storybook", *_TWO_THEMES)

    result.assert_outcomes(passed=4)


def _flaky_project(pytester: pytest.Pytester) -> Path:
    source = _story_module(
        """
        from pathlib import Path


        @story("Flaky/Story")
        def flaky(ctx):
            if Path("fail.txt").exists():
                raise RuntimeError("flaky failure")
            return QLabel("ok")


        @story("Steady/Story")
        def steady(ctx):
            return QLabel("ok")
        """
    )
    _project(pytester, source)
    pytester.makepyfile(test_plain="def test_plain():\n    pass\n")
    return pytester.path / "fail.txt"


def test_lf_reruns_only_the_failed_story_items(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    marker = _flaky_project(pytester)
    marker.write_text("fail")
    failing = _run(pytester, "--storybook", *_TWO_THEMES)
    failing.assert_outcomes(passed=3, failed=2)
    marker.unlink()

    rerun = _run(pytester, "--storybook", *_TWO_THEMES, "--lf", "-v")

    rerun.assert_outcomes(passed=2, deselected=3)
    rerun.stdout.fnmatch_lines(["storybook::Flaky/Story[[]Light[]] PASSED*", "storybook::Flaky/Story[[]Dark[]] PASSED*"])


def test_lf_skips_the_story_items_when_only_another_test_failed(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _flaky_project(pytester)
    pytester.makepyfile(test_plain="def test_plain():\n    assert False\n")
    _run(pytester, "--storybook", *_TWO_THEMES).assert_outcomes(passed=4, failed=1)

    rerun = _run(pytester, "--storybook", *_TWO_THEMES, "--lf")

    rerun.assert_outcomes(failed=1, deselected=4)


# --- Qt warnings and exceptions -------------------------------------------------------------------------------------------------


_WARNING_STORIES = _story_module(
    """
    @story("Warn/Custom")
    def custom(ctx):
        qWarning("custom warning here")
        return QLabel("x")


    @story("Warn/SizeHints")
    def size_hints(ctx):
        qWarning("This plugin does not support propagateSizeHints()")
        return QLabel("x")
    """,
    imports="from PySide6.QtCore import qWarning",
)


@pytest.mark.parametrize("extra", _WITH_AND_WITHOUT_PYTEST_QT)
def test_a_qt_warning_fails_the_item_except_the_default_ignored_one(
    pytester: pytest.Pytester, stories: StoryRegistry, extra: tuple[str, ...]
) -> None:
    _project(pytester, _WARNING_STORIES)

    result = _run(pytester, "--storybook", "--storybook-themes", "Light", *extra, "-v")

    result.assert_outcomes(passed=1, failed=1)
    result.stdout.fnmatch_lines(["storybook::Warn/Custom[[]Light[]] FAILED*", "storybook::Warn/SizeHints[[]Light[]] PASSED*"])
    result.stdout.fnmatch_lines(["*Qt logged 1 warning(s) while rendering Warn/Custom in Light:*", "*warning: custom warning here*"])


@pytest.mark.parametrize("extra", _WITH_AND_WITHOUT_PYTEST_QT)
def test_storybook_qt_warnings_ignore_lets_every_warning_pass(pytester: pytest.Pytester, stories: StoryRegistry, extra: tuple[str, ...]) -> None:
    _project(pytester, _WARNING_STORIES)

    result = _run(pytester, "--storybook", "--storybook-themes", "Light", "--storybook-qt-warnings", "ignore", *extra)

    result.assert_outcomes(passed=2)


def test_a_story_module_imported_before_collection_is_reported(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _project(pytester)
    pytester.makeconftest("import sys\nfrom pathlib import Path\n\nsys.path.insert(0, str(Path(__file__).parent / 'stories'))\nimport demo_stories\n")

    result = _run(pytester, "--storybook", "--storybook-themes", "Light", "-v")

    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(
        [
            "storybook::load-error[[]demo_stories[]] FAILED*",
            "*demo_stories was imported before the plugin collected the stories*Inputs/Button, Inputs/Label are not tested*",
        ]
    )


@pytest.mark.parametrize("extra", _WITH_AND_WITHOUT_PYTEST_QT)
def test_a_custom_ignore_pattern_replaces_the_default(pytester: pytest.Pytester, stories: StoryRegistry, extra: tuple[str, ...]) -> None:
    _project(pytester, _WARNING_STORIES, ini='storybook_qt_warnings_ignore = ["custom warning"]')

    result = _run(pytester, "--storybook", "--storybook-themes", "Light", *extra, "-v")

    result.assert_outcomes(passed=1, failed=1)
    result.stdout.fnmatch_lines(["storybook::Warn/Custom[[]Light[]] PASSED*", "storybook::Warn/SizeHints[[]Light[]] FAILED*"])


_PAINT_STORY = _story_module(
    """
    class Painter(QLabel):
        def paintEvent(self, event):
            raise RuntimeError("paint boom")


    @story("Paint/Raises")
    def painter(ctx):
        return Painter("x")
    """
)


@pytest.mark.parametrize("extra", _WITH_AND_WITHOUT_PYTEST_QT)
def test_an_exception_in_a_qt_virtual_method_fails_the_item(pytester: pytest.Pytester, stories: StoryRegistry, extra: tuple[str, ...]) -> None:
    _project(pytester, _PAINT_STORY)
    hook = sys.excepthook

    result = _run(pytester, "--storybook", "--storybook-themes", "Light", *extra)

    result.assert_outcomes(failed=1)
    output = result.stdout.str()
    # PySide6 6.8 raises it out of processEvents with its own prefix; newer versions hand it to sys.excepthook. Both show the source line.
    assert "paint boom" in output
    assert 'raise RuntimeError("paint boom")' in output
    assert sys.excepthook is hook


@pytest.mark.parametrize("extra", _WITH_AND_WITHOUT_PYTEST_QT)
def test_the_exception_hook_is_restored_when_a_story_raises(pytester: pytest.Pytester, stories: StoryRegistry, extra: tuple[str, ...]) -> None:
    _project(pytester, _story_module(
        """
        @story("Broken/Raises")
        def broken(ctx):
            raise ValueError("story boom")
        """
    ))
    hook = sys.excepthook

    result = _run(pytester, "--storybook", "--storybook-themes", "Light", *extra)

    result.assert_outcomes(failed=1)
    assert "story boom" in result.stdout.str()
    assert sys.excepthook is hook


def test_a_warning_is_chained_to_the_handler_installed_before(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _project(pytester, _WARNING_STORIES)
    received: list[str] = []
    original = _handler()
    qInstallMessageHandler(lambda kind, context, message: received.append(message))
    try:
        result = _run(pytester, "--storybook", "--storybook-themes", "Light", *_NO_PYTEST_QT)
        handler_after = _handler()
    finally:
        qInstallMessageHandler(original)  # ty: ignore[invalid-argument-type]

    result.assert_outcomes(passed=1, failed=1)
    assert received == ["custom warning here", "This plugin does not support propagateSizeHints()"]
    assert callable(handler_after)


# --- configuration errors -------------------------------------------------------------------------------------------------------


def test_a_malformed_pyproject_table_is_a_usage_error_before_collection(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    pytester.makepyprojecttoml('[tool.pyside6-storybook]\nstories = "stories"\n\n[tool.pytest.ini_options]\n')

    result = _run(pytester, "--storybook")

    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines(["*'stories' must be a list of strings*"])


def test_nothing_configured_is_a_usage_error_and_never_tests_the_examples(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    pytester.makepyprojecttoml("[tool.pytest.ini_options]\n")

    result = _run(pytester, "--storybook")

    assert result.ret == pytest.ExitCode.USAGE_ERROR
    assert NO_STORIES_CONFIGURED in result.stderr.str()


def test_the_ini_file_can_name_the_stories_without_a_pyproject_table(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    pytester.makepyprojecttoml('[tool.pytest.ini_options]\nstorybook_stories = ["stories"]\n')
    write(pytester.path, "stories/demo_stories.py", _BUTTONS)

    result = _run(pytester, "--storybook", *_TWO_THEMES)

    result.assert_outcomes(passed=4)


@pytest.mark.parametrize("option", [("--storybook-themes", ",Dark"), ("--storybook-qt-warnings", "warn")])
def test_a_malformed_option_is_a_usage_error(pytester: pytest.Pytester, stories: StoryRegistry, option: tuple[str, str]) -> None:
    _project(pytester)

    result = _run(pytester, "--storybook", *option)

    assert result.ret == pytest.ExitCode.USAGE_ERROR


def test_a_malformed_ini_value_is_a_usage_error(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _project(pytester, ini='storybook_qt_warnings_ignore = ["("]')

    result = _run(pytester, "--storybook")

    assert result.ret == pytest.ExitCode.USAGE_ERROR
    assert "storybook_qt_warnings_ignore" in result.stderr.str()


def test_a_provider_that_cannot_be_loaded_is_one_failing_configuration_item(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _project(pytester)

    result = _run(pytester, "--storybook", "--storybook-theme-provider", "missing_module:provider", "-v")

    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(
        ["storybook::configuration FAILED*", "*theme provider 'missing_module:provider': module 'missing_module' cannot be imported*"]
    )
    assert "Inputs/Button" not in result.stdout.str()


def test_an_unknown_theme_is_one_failing_configuration_item(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _project(pytester)

    result = _run(pytester, "--storybook", "--storybook-themes", "Light,Neon", "-v")

    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["storybook::configuration FAILED*", "*unknown theme 'Neon'*the available themes are: Light, Dark, System*"])


def test_a_project_without_stories_fails_instead_of_passing_silently(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _project(pytester, "")

    result = _run(pytester, "--storybook", "-v")

    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["storybook::configuration FAILED*", "*no stories found in: stories*"])


# --- the theme provider ---------------------------------------------------------------------------------------------------------


_RECORDING_PROVIDER = """
from pyside6_storybook import BuiltinThemeProvider


def _log(text):
    with open("events.log", "a", encoding="utf-8") as stream:
        stream.write(text + "\\n")


class Recording(BuiltinThemeProvider):
    def activate(self, app):
        _log("activate")
        super().activate(app)

    def set_theme(self, name):
        _log("set_theme " + name)
        super().set_theme(name)

    def deactivate(self):
        _log("deactivate")
        super().deactivate()


provider = Recording()
"""


def _provider_project(pytester: pytest.Pytester, *, provider: str = _RECORDING_PROVIDER, source: str = _BUTTONS) -> None:
    _project(pytester, source, toml='theme_provider = "recording:provider"\npythonpath = ["."]')
    write(pytester.path, "recording.py", provider)


def test_the_provider_is_activated_lazily_and_deactivated_at_the_end(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _provider_project(pytester)
    log = pytester.path / "events.log"

    collected = _run(pytester, "--storybook", *_TWO_THEMES, "--collect-only", "-q")
    assert not log.exists()
    result = _run(pytester, "--storybook", "--storybook-themes", "Dark,Light")

    collected.assert_outcomes()
    result.assert_outcomes(passed=4)
    assert log.read_text().splitlines() == ["activate", "set_theme Dark", "set_theme Light", "set_theme Dark", "set_theme Light", "deactivate"]


def test_the_look_is_restored_between_interleaved_tests_and_the_provider_activates_again(
    pytester: pytest.Pytester, stories: StoryRegistry
) -> None:
    _provider_project(pytester)
    pytester.makeconftest(
        """
        from PySide6.QtGui import QPalette
        from PySide6.QtWidgets import QApplication

        def pytest_collection_modifyitems(config, items):
            config.original_window = QApplication.palette().color(QPalette.ColorRole.Window)
            stories = [item for item in items if item.get_closest_marker("storybook")]
            plain = [item for item in items if not item.get_closest_marker("storybook")]
            assert len(stories) == 4 and len(plain) == 2, (stories, plain)
            items[:] = [stories[0], plain[0], stories[1], plain[1], stories[2], stories[3]]
        """
    )
    pytester.makepyfile(
        test_plain="""
        from PySide6.QtGui import QPalette
        from PySide6.QtWidgets import QApplication


        def test_after_the_first_dark_story(pytestconfig):
            assert QApplication.palette().color(QPalette.ColorRole.Window) == pytestconfig.original_window


        def test_after_the_light_story(pytestconfig):
            assert QApplication.palette().color(QPalette.ColorRole.Window) == pytestconfig.original_window
        """
    )

    result = _run(pytester, "--storybook", "--storybook-themes", "Dark,Light")

    result.assert_outcomes(passed=6)
    assert (pytester.path / "events.log").read_text().splitlines() == [
        "activate",
        "set_theme Dark",
        "deactivate",
        "activate",
        "set_theme Light",
        "deactivate",
        "activate",
        "set_theme Dark",
        "set_theme Light",
        "deactivate",
    ]


def test_a_provider_whose_tokens_raise_fails_the_story_item(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    provider = _RECORDING_PROVIDER + "\n\ndef _tokens(self):\n    raise RuntimeError('tokens are broken')\n\n\nRecording.tokens = _tokens\n"
    _provider_project(pytester, provider=provider)

    result = _run(pytester, "--storybook", "--storybook-themes", "Light", "-v")

    result.assert_outcomes(failed=2)
    result.stdout.fnmatch_lines(["*theme provider Recording: tokens() failed: RuntimeError: tokens are broken*"])
    assert (pytester.path / "events.log").read_text().splitlines()[-1] == "deactivate"


def test_a_provider_whose_activate_raises_fails_the_item_and_is_not_deactivated(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    provider = _RECORDING_PROVIDER.replace('_log("activate")', '_log("activate")\n        raise RuntimeError("cannot activate")')
    _provider_project(pytester, provider=provider)

    result = _run(pytester, "--storybook", "--storybook-themes", "Light")

    result.assert_outcomes(failed=2)
    result.stdout.fnmatch_lines(["*theme provider Recording: activate() failed: RuntimeError: cannot activate*"])
    assert "deactivate" not in (pytester.path / "events.log").read_text()


# --- what a story receives and where it is rendered -----------------------------------------------------------------------------


_CONTEXT_STORIES = _story_module(
    """
    @story("Ctx/Base", controls=[TextControl("text", "A")])
    def base(ctx):
        label = QLabel(ctx.args["text"])
        ctx.log("built", ctx.args["text"])
        ctx.log_signal(QPushButton("b", label).clicked, "clicked")
        seen = (ctx.theme, ctx.args["text"], "window" in ctx.tokens, ctx.color_scheme.name, ctx.actions is not None)
        with open("calls.log", "a", encoding="utf-8") as stream:
            stream.write(" ".join(map(str, seen)) + "\\n")
        return label


    base.variant("Other", args={"text": "B"})


    class Probe(QLabel):
        def showEvent(self, event):
            super().showEvent(event)
            host = self.window()
            record = {
                "separate_host": host is not self,
                "autofill": host.autoFillBackground(),
                "window_role": host.backgroundRole() == QPalette.ColorRole.Window,
                "visible": self.isVisible(),
            }
            with open("probe.json", "w", encoding="utf-8") as stream:
                json.dump(record, stream)


    @story("Probe/Host")
    def probe(ctx):
        return Probe("probe")
    """,
    imports="import json\nfrom PySide6.QtGui import QPalette\nfrom PySide6.QtWidgets import QPushButton\nfrom pyside6_storybook import TextControl",
)


def test_a_story_gets_its_default_arguments_the_theme_the_tokens_and_a_sink_that_discards(
    pytester: pytest.Pytester, stories: StoryRegistry
) -> None:
    _project(pytester, _CONTEXT_STORIES)

    result = _run(pytester, "--storybook", *_TWO_THEMES, "-k", "Ctx")

    result.assert_outcomes(passed=4)
    assert sorted((pytester.path / "calls.log").read_text().splitlines()) == [
        "Dark A True Dark True",
        "Dark B True Dark True",
        "Light A True Light True",
        "Light B True Light True",
    ]


def test_a_story_is_rendered_inside_an_opaque_shown_host(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _project(pytester, _CONTEXT_STORIES)

    result = _run(pytester, "--storybook", "--storybook-themes", "Light", "-k", "Probe")

    result.assert_outcomes(passed=1)
    assert (pytester.path / "probe.json").read_text() == '{"separate_host": true, "autofill": true, "window_role": true, "visible": true}'


def test_the_registry_bindings_and_the_story_modules_are_not_left_behind(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _project(pytester)
    before = (registry_module.default_registry, pyside6_storybook.default_registry)

    result = _run(pytester, "--storybook", *_TWO_THEMES)

    result.assert_outcomes(passed=4)
    assert (registry_module.default_registry, pyside6_storybook.default_registry) == before
    assert len(stories) == 0
    assert "demo_stories" not in sys.modules


def test_repeated_runs_in_one_process_do_not_see_stale_stories(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _project(pytester)
    _run(pytester, "--storybook", *_TWO_THEMES).assert_outcomes(passed=4)
    write(pytester.path, "stories/demo_stories.py", _story_module('@story("Only/One")\ndef one(ctx):\n    return QLabel("1")\n'))

    result = _run(pytester, "--storybook", *_TWO_THEMES, "-v")

    result.assert_outcomes(passed=2)
    assert "Inputs/Button" not in result.stdout.str()


# --- the examples ---------------------------------------------------------------------------------------------------------------


def _forget_the_examples(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the next load import the example modules again, so their stories register in the run's registry."""
    for name in [name for name in sys.modules if name == "pyside6_storybook.examples" or name.startswith("pyside6_storybook.examples.")]:
        monkeypatch.delitem(sys.modules, name)


def test_the_examples_pass_in_light_and_dark_when_named_explicitly(
    pytester: pytest.Pytester, stories: StoryRegistry, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytester.makepyprojecttoml("[tool.pytest.ini_options]\n")
    _forget_the_examples(monkeypatch)
    listed = _run(pytester, "--storybook", "--storybook-stories", "pyside6_storybook.examples", *_TWO_THEMES, "--collect-only", "-q")
    story_count = len([line for line in listed.outlines if line.startswith("storybook::")])
    _forget_the_examples(monkeypatch)

    result = _run(pytester, "--storybook", "--storybook-stories", "pyside6_storybook.examples", *_TWO_THEMES)

    assert story_count > 10
    result.assert_outcomes(passed=story_count)


# --- the render_story fixture ---------------------------------------------------------------------------------------------------


_FIXTURE_TESTS = """
import pytest
from PySide6.QtCore import QEvent
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication, QLineEdit, QPushButton


def _window_lightness():
    return QApplication.palette().color(QPalette.ColorRole.Window).lightness()


def test_args_override_the_defaults_and_the_widget_is_the_storys_own_and_shown(render_story):
    widget = render_story("Inputs/Button", args={"text": "Hi"})

    assert isinstance(widget, QPushButton)
    assert widget.text() == "Hi"
    assert widget.isVisible()


def test_a_theme_is_active_during_the_test(render_story):
    render_story("Inputs/Button", theme="Dark")

    assert _window_lightness() < 128


def test_the_theme_and_the_widgets_are_gone_after_the_test():
    assert _window_lightness() > 128
    assert not [widget for widget in QApplication.allWidgets() if isinstance(widget, QPushButton)]


def test_an_unknown_id_lists_the_close_matches(render_story):
    with pytest.raises(KeyError, match="did you mean: Inputs/Button"):
        render_story("Inputs/Buton")


def test_an_unknown_argument_name_raises_key_error(render_story):
    with pytest.raises(KeyError, match="no control named 'nope'.*its controls are: text"):
        render_story("Inputs/Button", args={"nope": 1})


def test_focus_is_not_left_in_the_rendered_widget(qtbot, render_story):
    probe = QLineEdit()
    qtbot.addWidget(probe)
    probe.show()
    probe.activateWindow()
    qtbot.waitUntil(probe.hasFocus, timeout=3000)
    probe.hide()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    story = render_story("Edit/Line")

    assert not story.hasFocus()
    assert QApplication.focusWidget() is None or not story.window().isAncestorOf(QApplication.focusWidget())
"""

_FIXTURE_STORIES = _BUTTONS + """

from PySide6.QtWidgets import QLineEdit


@story("Edit/Line")
def line(ctx):
    return QLineEdit("text")
"""


def test_render_story_works_without_the_flag_and_cleans_up(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _project(pytester, _FIXTURE_STORIES)
    pytester.makepyfile(test_fixture=_FIXTURE_TESTS)

    result = _run(pytester, "-v")

    result.assert_outcomes(passed=6)
    assert "storybook::" not in result.stdout.str()


def test_render_story_shares_the_session_with_the_collected_items(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _project(pytester, _FIXTURE_STORIES)
    pytester.makepyfile(test_fixture=_FIXTURE_TESTS)

    result = _run(pytester, "--storybook", *_TWO_THEMES)

    result.assert_outcomes(passed=6 + 2 * 3)


def test_render_story_needs_stories_to_be_configured(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    pytester.makepyprojecttoml("[tool.pytest.ini_options]\n")
    pytester.makepyfile(test_fixture="def test_it(render_story):\n    render_story('Inputs/Button')\n")

    result = _run(pytester, setup_errors=True)

    result.assert_outcomes(errors=1)
    assert NO_STORIES_CONFIGURED in result.stdout.str()


def test_render_story_without_pytest_qt_says_how_to_install_it(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _project(pytester)
    pytester.makepyfile(test_fixture="def test_it(render_story):\n    render_story('Inputs/Button')\n")

    result = _run(pytester, *_NO_PYTEST_QT)

    result.assert_outcomes(errors=1)
    assert "render_story needs pytest-qt: install pyside6-storybook[pytest]" in result.stdout.str()


def test_the_plugin_itself_does_not_need_pytest_qt(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _project(pytester)

    result = _run(pytester, "--storybook", *_TWO_THEMES, *_NO_PYTEST_QT)

    result.assert_outcomes(passed=4)


# --- start-up cost and xdist ----------------------------------------------------------------------------------------------------


def test_importing_the_entry_module_imports_neither_qt_nor_the_library() -> None:
    code = (
        "import pyside6_storybook_pytest, sys; "
        "print(sorted(m for m in sys.modules if m.startswith(('PySide6', 'pyside6_storybook.')) or m == 'pyside6_storybook'))"
    )

    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60, check=False)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "[]"


def test_a_run_without_the_flag_imports_neither_qt_nor_the_library(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _project(pytester)
    pytester.makepyfile(
        test_plain="""
        import sys


        def test_plain():
            assert not [name for name in sys.modules if name.startswith("pyside6_storybook") and name != "pyside6_storybook_pytest"]
            assert not [name for name in sys.modules if name.startswith("PySide6")]
        """
    )

    result = pytester.runpytest_subprocess("-p", "no:pytest-qt", "-p", "no:cacheprovider", timeout=120)

    result.assert_outcomes(passed=1)


@pytest.mark.full
def test_the_items_run_under_xdist_and_are_spread_over_the_workers(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _project(pytester)

    result = pytester.runpytest_subprocess("--storybook", *_TWO_THEMES, "-n", "2", "-v", timeout=180)

    result.assert_outcomes(passed=4)
    workers = set(re.findall(r"\[(gw\d)\] .* PASSED storybook::", result.stdout.str()))
    assert workers == {"gw0", "gw1"}


@pytest.mark.full
def test_loadfile_keeps_every_storybook_item_on_one_worker(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _project(pytester)

    result = pytester.runpytest_subprocess("--storybook", *_TWO_THEMES, "-n", "2", "--dist", "loadfile", "-v", timeout=180)

    result.assert_outcomes(passed=4)
    assert len(set(re.findall(r"\[(gw\d)\] .* PASSED storybook::", result.stdout.str()))) == 1


@pytest.mark.full
def test_a_configuration_error_under_xdist_is_a_clean_usage_error(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    pytester.makepyprojecttoml("[tool.pytest.ini_options]\n")

    result = pytester.runpytest_subprocess("--storybook", "-n", "2", timeout=180)

    assert result.ret == pytest.ExitCode.USAGE_ERROR
    assert NO_STORIES_CONFIGURED in result.stderr.str()
    assert "INTERNALERROR" not in result.stdout.str() + result.stderr.str()


@pytest.mark.full
def test_a_failing_story_and_a_load_error_under_xdist(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _project(pytester)
    write(pytester.path, "stories/broken_stories.py", "raise ImportError('no such widget library')\n")

    result = pytester.runpytest_subprocess("--storybook", *_TWO_THEMES, "-n", "2", timeout=180)

    result.assert_outcomes(passed=4, failed=1)
    assert "INTERNALERROR" not in result.stdout.str()


# --- accessible names and keyboard focus (--storybook-a11y) ---------------------------------------------------------------------


_A11Y_STORIES = _story_module(
    """
    @story("Icons/Named")
    def named(ctx):
        button = QToolButton()
        button.setAccessibleName("Close")
        return button


    @story("Icons/Unnamed")
    def unnamed(ctx):
        button = QToolButton()
        button.setObjectName("close_button")
        return button


    @story("Icons/Skipped", checks_ignore={"name": "decorative icon", "focus": "not interactive"})
    def skipped(ctx):
        button = QToolButton()
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        return button
    """,
    imports="from PySide6.QtCore import Qt\nfrom PySide6.QtWidgets import QToolButton",
)


def test_a11y_adds_two_items_per_story_after_its_theme_items(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _project(pytester)

    result = _run(pytester, "--storybook", "--storybook-a11y", *_TWO_THEMES, "--collect-only", "-q")

    assert [line for line in result.outlines if line.startswith("storybook::")] == [
        "storybook::Inputs/Button[Light]",
        "storybook::Inputs/Button[Dark]",
        "storybook::Inputs/Button[a11y-name]",
        "storybook::Inputs/Button[a11y-focus]",
        "storybook::Inputs/Button[Light-contrast]",
        "storybook::Inputs/Button[Dark-contrast]",
        "storybook::Inputs/Label[Light]",
        "storybook::Inputs/Label[Dark]",
        "storybook::Inputs/Label[a11y-name]",
        "storybook::Inputs/Label[a11y-focus]",
        "storybook::Inputs/Label[Light-contrast]",
        "storybook::Inputs/Label[Dark-contrast]",
    ]


def test_without_the_a11y_option_there_are_no_a11y_items(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _project(pytester)

    result = _run(pytester, "--storybook", *_TWO_THEMES, "--collect-only", "-q")

    assert "a11y" not in result.stdout.str()


def test_the_ini_key_turns_the_a11y_items_on(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _project(pytester, ini="storybook = true\nstorybook_a11y = true")

    result = _run(pytester, "--storybook-themes", "Light")

    result.assert_outcomes(passed=8)


def test_an_unnamed_icon_button_fails_naming_the_widget(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _project(pytester, _A11Y_STORIES)

    result = _run(pytester, "--storybook", "--storybook-a11y", "--storybook-themes", "Light", "-v", "-rs")

    result.assert_outcomes(passed=9, failed=1, skipped=2)
    result.stdout.fnmatch_lines(
        [
            "storybook::Icons/Named[[]a11y-name[]] PASSED*",
            "storybook::Icons/Unnamed[[]a11y-name[]] FAILED*",
            "storybook::Icons/Unnamed[[]a11y-focus[]] PASSED*",
        ]
    )
    result.stdout.fnmatch_lines(
        ["*1 accessibility issue(s) for the 'name' rule in Icons/Unnamed:*", "*QToolButton 'close_button' at QToolButton: has no accessible*"]
    )


def test_an_ignored_rule_is_skipped_with_its_reason(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _project(pytester, _A11Y_STORIES)

    result = _run(pytester, "--storybook", "--storybook-a11y", "--storybook-themes", "Light", "-rs")

    # The skip names the story's own file, not the plugin's.
    result.stdout.fnmatch_lines(
        [
            "SKIPPED [[]1[]] stories/demo_stories.py: name ignored: decorative icon",
            "SKIPPED [[]1[]] stories/demo_stories.py: focus ignored: not interactive",
        ]
    )


def test_a_variant_is_skipped_through_the_inherited_ignore(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _project(
        pytester,
        _story_module(
            """
            @story("Icons/Button/Default", checks_ignore={"name": "decorative"})
            def button(ctx):
                return QToolButton()


            button.variant("Other")
            """,
            imports="from PySide6.QtWidgets import QToolButton",
        ),
    )

    result = _run(pytester, "--storybook", "--storybook-a11y", "--storybook-themes", "Light", "-rs")

    result.assert_outcomes(passed=6, skipped=2)
    result.stdout.fnmatch_lines(["*SKIPPED [[]2[]]*name ignored: decorative"])


@pytest.mark.parametrize("extra", _WITH_AND_WITHOUT_PYTEST_QT)
def test_an_a11y_item_fails_on_a_story_exception_like_a_story_item(pytester: pytest.Pytester, stories: StoryRegistry, extra: tuple[str, ...]) -> None:
    _project(pytester, _PAINT_STORY)

    result = _run(pytester, "--storybook", "--storybook-a11y", "--storybook-themes", "Light", *extra)

    result.assert_outcomes(failed=4)
    assert result.stdout.str().count("paint boom") >= 4


@pytest.mark.parametrize("extra", _WITH_AND_WITHOUT_PYTEST_QT)
def test_an_a11y_item_fails_when_the_story_raises(pytester: pytest.Pytester, stories: StoryRegistry, extra: tuple[str, ...]) -> None:
    _project(pytester, _story_module(
        """
        @story("Broken/Raises")
        def broken(ctx):
            raise ValueError("story boom")
        """
    ))

    result = _run(pytester, "--storybook", "--storybook-a11y", "--storybook-themes", "Light", *extra)

    result.assert_outcomes(failed=4)
    assert "story boom" in result.stdout.str()


def test_the_a11y_items_render_in_the_first_selected_theme(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _project(
        pytester,
        _story_module(
            """
            @story("Theme/Probe")
            def probe(ctx):
                raise RuntimeError(f"rendered in {ctx.theme}")
            """
        ),
    )

    result = _run(pytester, "--storybook", "--storybook-a11y", "--storybook-themes", "Dark,Light", "-k", "a11y-focus")

    result.assert_outcomes(failed=1)
    assert "rendered in Dark" in result.stdout.str()


# --- text contrast (--storybook-a11y) -------------------------------------------------------------------------------------------


_CONTRAST_STORIES = _story_module(
    """
    @story("Text/Readable")
    def readable(ctx):
        label = QLabel("Readable")
        label.setStyleSheet("background-color: #ffffff; color: #000000;")
        return label


    @story("Text/Faint")
    def faint(ctx):
        label = QLabel("Faint")
        label.setObjectName("faint_label")
        label.setStyleSheet("background-color: #888888; color: #777777;")
        return label


    @story("Text/Excused", checks_ignore={"contrast": "decorative watermark"})
    def excused(ctx):
        label = QLabel("Watermark")
        label.setStyleSheet("background-color: #888888; color: #777777;")
        return label


    @story("Text/Disabled")
    def disabled(ctx):
        label = QLabel("Disabled")
        label.setStyleSheet("background-color: #888888; color: #777777;")
        label.setEnabled(False)
        return label


    @story("Text/Middling")
    def middling(ctx):
        label = QLabel("Middling")
        label.setStyleSheet("background-color: #ffffff; color: #909090;")
        return label
    """
)


def test_a_faint_text_fails_its_theme_item_naming_the_widget_and_the_colours(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _project(pytester, _CONTRAST_STORIES)

    result = _run(pytester, "--storybook", "--storybook-a11y", *_TWO_THEMES, "-k", "contrast and Faint", "-v")

    result.assert_outcomes(failed=2)
    result.stdout.fnmatch_lines(
        [
            "*1 text contrast issue(s) in Text/Faint in Light:*",
            "*QLabel 'faint_label' at QLabel: text 'Faint' is #777777 on #888888, a contrast of 1.26:1; normal text needs 4.5:1*",
        ]
    )
    assert "storybook::Text/Faint[Dark-contrast] FAILED" in result.stdout.str()


def test_the_readable_and_the_disabled_text_pass(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _project(pytester, _CONTRAST_STORIES)

    result = _run(pytester, "--storybook", "--storybook-a11y", "--storybook-themes", "Light", "-k", "contrast and (Readable or Disabled)")

    result.assert_outcomes(passed=2)


def test_a_story_that_ignores_the_contrast_rule_is_skipped_by_a_marker_with_its_reason(
    pytester: pytest.Pytester, stories: StoryRegistry
) -> None:
    _project(pytester, _CONTRAST_STORIES)

    result = _run(pytester, "--storybook", "--storybook-a11y", *_TWO_THEMES, "-k", "contrast and Excused", "-rs")

    result.assert_outcomes(skipped=2)
    result.stdout.fnmatch_lines(["SKIPPED [[]2[]] stories/demo_stories.py: contrast ignored: decorative watermark"])


def test_an_ignored_contrast_rule_does_not_render_the_story(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _project(
        pytester,
        _story_module(
            """
            @story("Text/Raises", checks_ignore={"contrast": "not text"})
            def raises(ctx):
                raise ValueError("rendered anyway")
            """
        ),
    )

    result = _run(pytester, "--storybook", "--storybook-a11y", "--storybook-themes", "Light", "-k", "contrast")

    result.assert_outcomes(skipped=1)
    assert "rendered anyway" not in result.stdout.str()


@pytest.mark.parametrize("option", [pytest.param(("--storybook-no-contrast",), id="option"), pytest.param((), id="ini")])
def test_the_contrast_items_can_be_turned_off(pytester: pytest.Pytester, stories: StoryRegistry, option: tuple[str, ...]) -> None:
    _project(pytester, ini="" if option else "storybook_contrast = false")

    result = _run(pytester, "--storybook", "--storybook-a11y", *_TWO_THEMES, *option, "--collect-only", "-q")

    assert "contrast" not in result.stdout.str()
    assert "[a11y-name]" in result.stdout.str()


def test_without_the_a11y_option_there_are_no_contrast_items(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _project(pytester)

    result = _run(pytester, "--storybook", *_TWO_THEMES, "--collect-only", "-q")

    assert "contrast" not in result.stdout.str()


def test_the_thresholds_come_from_the_ini_keys(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _project(pytester, _CONTRAST_STORIES, ini="storybook_contrast_normal = 3\nstorybook_contrast_large = 2")

    result = _run(pytester, "--storybook", "--storybook-a11y", "--storybook-themes", "Light", "-k", "contrast and Middling")

    result.assert_outcomes(passed=1)  # 3.19:1 needs only 3


def test_the_default_thresholds_fail_a_middling_text(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _project(pytester, _CONTRAST_STORIES)

    result = _run(pytester, "--storybook", "--storybook-a11y", "--storybook-themes", "Light", "-k", "contrast and Middling")

    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*a contrast of 3.19:1; normal text needs 4.5:1*"])


def test_the_disabled_option_checks_disabled_widgets(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _project(pytester, _CONTRAST_STORIES)

    args = ("--storybook", "--storybook-a11y", "--storybook-contrast-disabled", "--storybook-themes", "Light")
    result = _run(pytester, *args, "-k", "contrast and Disabled")

    result.assert_outcomes(failed=1)


@pytest.mark.parametrize("extra", _WITH_AND_WITHOUT_PYTEST_QT)
def test_a_contrast_item_fails_on_a_story_exception_like_a_story_item(
    pytester: pytest.Pytester, stories: StoryRegistry, extra: tuple[str, ...]
) -> None:
    _project(pytester, _PAINT_STORY)

    result = _run(pytester, "--storybook", "--storybook-a11y", "--storybook-themes", "Light", "-k", "contrast", *extra)

    result.assert_outcomes(failed=1)
    assert "paint boom" in result.stdout.str()


@pytest.mark.parametrize("extra", _WITH_AND_WITHOUT_PYTEST_QT)
def test_a_contrast_item_fails_when_the_story_raises_and_on_a_qt_warning(
    pytester: pytest.Pytester, stories: StoryRegistry, extra: tuple[str, ...]
) -> None:
    _project(
        pytester,
        _story_module(
            """
            @story("Broken/Raises")
            def broken(ctx):
                raise ValueError("story boom")


            @story("Broken/Warns")
            def warns(ctx):
                from PySide6.QtCore import qWarning
                qWarning("contrast probe warning")
                return QLabel("x")
            """
        ),
    )

    result = _run(pytester, "--storybook", "--storybook-a11y", "--storybook-themes", "Light", "-k", "contrast", *extra)

    result.assert_outcomes(failed=2)
    output = result.stdout.str()
    assert "story boom" in output
    assert "contrast probe warning" in output


def test_the_contrast_items_render_in_their_own_theme(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _project(
        pytester,
        _story_module(
            """
            @story("Theme/Probe")
            def probe(ctx):
                raise RuntimeError(f"rendered in {ctx.theme}")
            """
        ),
    )

    result = _run(pytester, "--storybook", "--storybook-a11y", "--storybook-themes", "Dark,Light", "-k", "Light-contrast")

    result.assert_outcomes(failed=1)
    assert "rendered in Light" in result.stdout.str()


def test_the_examples_pass_the_a11y_and_contrast_rules_in_light_and_dark(
    pytester: pytest.Pytester, stories: StoryRegistry, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytester.makepyprojecttoml("[tool.pytest.ini_options]\n")
    _forget_the_examples(monkeypatch)
    args = ("--storybook", "--storybook-a11y", "--storybook-stories", "pyside6_storybook.examples", *_TWO_THEMES)
    listed = _run(pytester, *args, "--collect-only", "-q")
    count = len([line for line in listed.outlines if line.startswith("storybook::")])
    _forget_the_examples(monkeypatch)

    result = _run(pytester, *args)

    # Light and Dark, not System: Qt's own palette (offscreen) is white on #308cc6 in the Palette story, 3.69:1.
    assert count == 20 * (2 + 2 + 2)
    result.assert_outcomes(passed=count)


# --- screenshot snapshots (--storybook-snapshots) -------------------------------------------------------------------------------

_SNAPSHOT_STORIES = _story_module(
    """
    from pathlib import Path

    from PySide6.QtWidgets import QLabel


    def _swatch(ctx):
        # The colour and the size come from files, so a test changes the story's look between two runs without re-importing the module.
        colour = Path("colour.txt").read_text(encoding="utf-8").strip() if Path("colour.txt").exists() else "#336699"
        width = int(Path("width.txt").read_text(encoding="utf-8")) if Path("width.txt").exists() else 60
        label = QLabel()
        label.setFixedSize(width, 30)
        label.setStyleSheet(f"background-color: {colour};")
        return label


    @story("Snap/Swatch")
    def swatch(ctx):
        return _swatch(ctx)


    @story("Snap/Clock", checks_ignore={"snapshot": "shows the current time"})
    def clock(ctx):
        raise ValueError("rendered anyway")
    """
)
_SNAPSHOT_FLAGS = ("--storybook", "--storybook-snapshots", "--storybook-themes", "Light")


def _baseline(pytester: pytest.Pytester, name: str = "Snap__Swatch[Light]") -> Path:
    return pytester.path / "tests" / "storybook_snapshots" / sys.platform / f"{name}.png"


def _failures(pytester: pytest.Pytester) -> Path:
    return pytester.path / "storybook-snapshot-failures" / sys.platform


def _snapshot_project(pytester: pytest.Pytester, *, ini: str = "") -> None:
    _project(pytester, _SNAPSHOT_STORIES, ini=ini)


def _update(pytester: pytest.Pytester, *extra: str) -> pytest.RunResult:
    return _run(pytester, "--storybook", "--storybook-update-snapshots", "--storybook-themes", "Light", "-k", "Swatch and snapshot", *extra)


def _compare(pytester: pytest.Pytester, *extra: str) -> pytest.RunResult:
    return _run(pytester, *_SNAPSHOT_FLAGS, "-k", "Swatch and snapshot", *extra)


def test_the_snapshot_items_exist_only_when_asked_for(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _snapshot_project(pytester)

    plain = _run(pytester, "--storybook", *_TWO_THEMES, "--collect-only", "-q")
    asked = _run(pytester, "--storybook", "--storybook-snapshots", *_TWO_THEMES, "--collect-only", "-q")
    updating = _run(pytester, "--storybook", "--storybook-update-snapshots", *_TWO_THEMES, "--collect-only", "-q")

    assert "snapshot" not in plain.stdout.str()
    expected = ["storybook::Snap/Swatch[Light-snapshot]", "storybook::Snap/Swatch[Dark-snapshot]"]
    assert [line for line in asked.outlines if "Swatch" in line and "snapshot" in line] == expected
    assert [line for line in updating.outlines if "Swatch" in line and "snapshot" in line] == expected


def test_the_ini_key_turns_the_snapshot_items_on(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _snapshot_project(pytester, ini="storybook_snapshots = true")

    result = _run(pytester, "--storybook", "--storybook-themes", "Light", "--collect-only", "-q")

    assert "storybook::Snap/Swatch[Light-snapshot]" in result.outlines


def test_the_snapshot_items_follow_the_other_items_of_their_story_and_do_not_need_the_a11y_option(
    pytester: pytest.Pytester, stories: StoryRegistry
) -> None:
    _snapshot_project(pytester)

    without = _run(pytester, *_SNAPSHOT_FLAGS, "--collect-only", "-q")
    both = _run(pytester, *_SNAPSHOT_FLAGS, "--storybook-a11y", "--storybook-themes", "Light,Dark", "--collect-only", "-q")

    assert [line for line in without.outlines if "Swatch" in line] == ["storybook::Snap/Swatch[Light]", "storybook::Snap/Swatch[Light-snapshot]"]
    assert [line for line in both.outlines if "Swatch" in line] == [
        "storybook::Snap/Swatch[Light]",
        "storybook::Snap/Swatch[Dark]",
        "storybook::Snap/Swatch[a11y-name]",
        "storybook::Snap/Swatch[a11y-focus]",
        "storybook::Snap/Swatch[Light-contrast]",
        "storybook::Snap/Swatch[Dark-contrast]",
        "storybook::Snap/Swatch[Light-snapshot]",
        "storybook::Snap/Swatch[Dark-snapshot]",
    ]


@pytest.mark.parametrize("pytest_qt", _WITH_AND_WITHOUT_PYTEST_QT)
def test_a_baseline_is_created_by_the_update_option_and_then_matches(
    pytester: pytest.Pytester, stories: StoryRegistry, pytest_qt: tuple[str, ...]
) -> None:
    _snapshot_project(pytester)

    created = _update(pytester, *pytest_qt)
    matched = _compare(pytester, *pytest_qt)

    created.assert_outcomes(passed=1)
    matched.assert_outcomes(passed=1)
    assert _baseline(pytester).is_file()
    assert not _failures(pytester).exists()


def test_a_missing_baseline_fails_and_is_not_created(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _snapshot_project(pytester)

    result = _compare(pytester)

    result.assert_outcomes(failed=1)
    assert f"no baseline at {_baseline(pytester)}; run pytest --storybook --storybook-update-snapshots to create it" in result.stdout.str()
    assert not _baseline(pytester).exists()
    assert (_failures(pytester) / "Snap__Swatch[Light].actual.png").is_file()


def test_a_changed_colour_fails_and_writes_the_actual_and_diff_images(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    from PySide6.QtGui import QColor, QImage

    _snapshot_project(pytester)
    _update(pytester).assert_outcomes(passed=1)
    (pytester.path / "colour.txt").write_text("#993333", encoding="utf-8")

    result = _compare(pytester)

    result.assert_outcomes(failed=1)
    actual = _failures(pytester) / "Snap__Swatch[Light].actual.png"
    diff = _failures(pytester) / "Snap__Swatch[Light].diff.png"
    output = result.stdout.str()
    assert str(_baseline(pytester)) in output
    assert str(actual) in output
    assert str(diff) in output
    assert "100.0000% of the pixels differ" in output
    assert "tolerance of 0 per channel" in output
    assert QImage(str(actual)).pixelColor(5, 5) == QColor("#993333")
    assert QImage(str(diff)).pixelColor(5, 5) == QColor(255, 0, 0)
    assert QImage(str(_baseline(pytester))).pixelColor(5, 5) == QColor("#336699")


def test_a_passing_run_removes_the_images_of_an_earlier_failure(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _snapshot_project(pytester)
    _update(pytester)
    colour = pytester.path / "colour.txt"
    colour.write_text("#993333", encoding="utf-8")
    _compare(pytester).assert_outcomes(failed=1)

    colour.unlink()
    result = _compare(pytester)

    result.assert_outcomes(passed=1)
    assert list(_failures(pytester).glob("*.png")) == []


def test_a_size_change_fails_and_names_both_sizes(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _snapshot_project(pytester)
    _update(pytester)
    (pytester.path / "width.txt").write_text("80", encoding="utf-8")

    result = _compare(pytester)

    result.assert_outcomes(failed=1)
    assert "another size than its baseline: " in result.stdout.str()
    assert "80x30 instead of 60x30" in result.stdout.str()
    assert (_failures(pytester) / "Snap__Swatch[Light].actual.png").is_file()
    assert (_failures(pytester) / "Snap__Swatch[Light].diff.png").is_file()


def test_the_tolerance_and_the_max_diff_come_from_the_ini_keys(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _snapshot_project(pytester)
    _update(pytester)
    (pytester.path / "colour.txt").write_text("#346699", encoding="utf-8")  # one channel off by 1

    strict = _compare(pytester)
    tolerant = _compare(pytester, "-o", "storybook_snapshot_tolerance=1")
    limited = _compare(pytester, "-o", "storybook_snapshot_max_diff=1")

    strict.assert_outcomes(failed=1)
    tolerant.assert_outcomes(passed=1)
    limited.assert_outcomes(passed=1)


def test_a_story_that_ignores_the_snapshot_rule_is_skipped_by_a_marker_without_rendering(
    pytester: pytest.Pytester, stories: StoryRegistry
) -> None:
    _snapshot_project(pytester)

    result = _run(pytester, *_SNAPSHOT_FLAGS, "-k", "Clock and snapshot", "-rs")

    result.assert_outcomes(skipped=1)
    result.stdout.fnmatch_lines(["SKIPPED [[]1[]] stories/demo_stories.py: snapshot ignored: shows the current time"])
    assert "rendered anyway" not in result.stdout.str()


def test_the_update_option_does_not_rewrite_an_unchanged_baseline_and_replaces_a_changed_one(
    pytester: pytest.Pytester, stories: StoryRegistry
) -> None:
    from PySide6.QtGui import QColor, QImage

    _snapshot_project(pytester)
    _update(pytester)
    baseline = _baseline(pytester)
    baseline.write_bytes(baseline.read_bytes())
    marker = baseline.stat().st_mtime_ns

    _update(pytester).assert_outcomes(passed=1)
    assert baseline.stat().st_mtime_ns == marker

    (pytester.path / "colour.txt").write_text("#993333", encoding="utf-8")
    _update(pytester).assert_outcomes(passed=1)
    assert QImage(str(baseline)).pixelColor(5, 5) == QColor("#993333")


@pytest.mark.parametrize("pytest_qt", _WITH_AND_WITHOUT_PYTEST_QT)
def test_a_snapshot_item_fails_on_a_story_exception_and_on_a_qt_warning(
    pytester: pytest.Pytester, stories: StoryRegistry, pytest_qt: tuple[str, ...]
) -> None:
    _project(
        pytester,
        _story_module(
            """
            from PySide6.QtCore import qWarning


            @story("Snap/Boom")
            def boom(ctx):
                raise RuntimeError("story boom")


            @story("Snap/Warn")
            def warn(ctx):
                qWarning("snapshot probe warning")
                return QLabel("x")
            """
        ),
    )

    result = _run(pytester, *_SNAPSHOT_FLAGS, "-k", "snapshot", *pytest_qt)

    result.assert_outcomes(failed=2)
    assert "story boom" in result.stdout.str()
    assert "snapshot probe warning" in result.stdout.str()
    assert not _baseline(pytester, "Snap__Warn[Light]").exists()


def test_the_update_option_does_not_write_a_baseline_for_a_story_that_fails(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _project(
        pytester,
        _story_module(
            """
            from PySide6.QtCore import qWarning


            @story("Snap/Warn")
            def warn(ctx):
                qWarning("snapshot probe warning")
                return QLabel("x")
            """
        ),
    )

    result = _run(pytester, "--storybook", "--storybook-update-snapshots", "--storybook-themes", "Light", "-k", "snapshot")

    result.assert_outcomes(failed=1)
    assert not _baseline(pytester, "Snap__Warn[Light]").exists()


def test_an_unreadable_baseline_fails_with_a_hint(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _snapshot_project(pytester)
    _baseline(pytester).parent.mkdir(parents=True)
    _baseline(pytester).write_bytes(b"not a png")

    result = _compare(pytester)

    result.assert_outcomes(failed=1)
    assert "is not a readable image" in result.stdout.str()


def test_the_folders_come_from_the_ini_keys(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _snapshot_project(pytester, ini='storybook_snapshot_dir = "baselines"\nstorybook_snapshot_failures = "out"')
    _update(pytester).assert_outcomes(passed=1)
    assert (pytester.path / "baselines" / sys.platform / "Snap__Swatch[Light].png").is_file()
    (pytester.path / "colour.txt").write_text("#993333", encoding="utf-8")

    _compare(pytester).assert_outcomes(failed=1)

    assert (pytester.path / "out" / sys.platform / "Snap__Swatch[Light].diff.png").is_file()


@pytest.mark.parametrize(
    ("key", "value"),
    [("storybook_snapshot_tolerance", "256"), ("storybook_snapshot_tolerance", "-1"), ("storybook_snapshot_max_diff", "1.5")],
)
def test_a_malformed_snapshot_ini_value_is_a_usage_error(pytester: pytest.Pytester, stories: StoryRegistry, key: str, value: str) -> None:
    _snapshot_project(pytester, ini=f'{key} = "{value}"')

    result = _run(pytester, "--storybook", "--storybook-snapshots")

    assert result.ret == pytest.ExitCode.USAGE_ERROR
    assert key in result.stderr.str()


def test_snapshots_run_under_xdist_without_the_cache_provider(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    _snapshot_project(pytester)
    flags = ("--storybook", "--storybook-themes", "Light,Dark", "-k", "Swatch and snapshot", "-p", "no:cacheprovider", "-n", "2")

    created = pytester.runpytest_subprocess(*flags, "--storybook-update-snapshots", timeout=180)
    matched = pytester.runpytest_subprocess(*flags, "--storybook-snapshots", timeout=180)
    (pytester.path / "colour.txt").write_text("#993333", encoding="utf-8")
    failed = pytester.runpytest_subprocess(*flags, "--storybook-snapshots", timeout=180)

    created.assert_outcomes(passed=2)
    matched.assert_outcomes(passed=2)
    failed.assert_outcomes(failed=2)
    for theme in ("Light", "Dark"):
        assert (_baseline(pytester, f"Snap__Swatch[{theme}]")).is_file()
        assert (_failures(pytester) / f"Snap__Swatch[{theme}].diff.png").is_file()
    assert "INTERNALERROR" not in failed.stdout.str()


@pytest.mark.full
def test_every_example_renders_to_identical_images_twice_in_light_and_dark(
    pytester: pytest.Pytester, stories: StoryRegistry, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytester.makepyprojecttoml("[tool.pytest.ini_options]\n")
    args = ("--storybook", "--storybook-update-snapshots", "--storybook-stories", "pyside6_storybook.examples", *_TWO_THEMES)
    folders = [pytester.path / "first", pytester.path / "second"]
    for folder in folders:
        _forget_the_examples(monkeypatch)
        _run(pytester, *args, "-k", "snapshot", "-o", f"storybook_snapshot_dir={folder.name}").assert_outcomes(passed=40)

    names = sorted(path.name for path in (folders[0] / sys.platform).glob("*.png"))
    assert len(names) == 40
    assert names == sorted(path.name for path in (folders[1] / sys.platform).glob("*.png"))
    different = [name for name in names if (folders[0] / sys.platform / name).read_bytes() != (folders[1] / sys.platform / name).read_bytes()]
    assert different == []

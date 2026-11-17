import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from story_files import story_source, write

from pyside6_storybook import LoadError, StoryRegistry, __version__, cli
from pyside6_storybook.discovery import sources
from pyside6_storybook.discovery.reload import ReloadSession


class _RecordingRun:
    """Stands in for ``app.run`` so no event loop starts; records what the gallery would have shown."""

    def __init__(self, exit_code: int = 0) -> None:
        self.exit_code = exit_code
        self.calls: list[tuple[list[str], str | None]] = []
        self.load_errors: list[tuple[LoadError, ...]] = []
        self.reloads: list[ReloadSession | None] = []

    def __call__(
        self,
        registry: StoryRegistry,
        argv: list[str] | None = None,
        *,
        theme: str | None = None,
        load_errors: tuple[LoadError, ...] = (),
        reload: ReloadSession | None = None,
    ) -> int:
        self.calls.append((registry.ids(), theme))
        self.load_errors.append(load_errors)
        self.reloads.append(reload)
        return self.exit_code


@pytest.fixture
def gallery(monkeypatch: pytest.MonkeyPatch) -> _RecordingRun:
    recording = _RecordingRun()
    monkeypatch.setattr(cli, "run", recording)
    return recording


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stories: StoryRegistry) -> Path:
    """A working directory with two stories in ``stories/``."""
    write(tmp_path, "stories/a_story.py", story_source("Inputs/A"))
    write(tmp_path, "stories/b_story.py", story_source("Inputs/B"))
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["--version"])
    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"pyside6-storybook {__version__}"


def test_help_describes_targets_and_options(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["--help"])
    assert exit_info.value.code == 0
    help_text = capsys.readouterr().out
    for expected in ("TARGET", "--list", "--no-reload", "--theme", "--version", "Light", "Dark", "System"):
        assert expected in help_text


def test_an_unknown_theme_is_a_usage_error(capsys: pytest.CaptureFixture[str], gallery: _RecordingRun) -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["--theme", "Sepia", "stories"])
    assert exit_info.value.code == 2
    assert "Sepia" in capsys.readouterr().err
    assert gallery.calls == []


def test_targets_open_the_gallery_with_their_stories(project: Path, gallery: _RecordingRun) -> None:
    assert cli.main(["stories"]) == 0
    assert gallery.calls == [(["Inputs/A", "Inputs/B"], None)]


def test_theme_is_passed_to_the_gallery(project: Path, gallery: _RecordingRun) -> None:
    cli.main(["--theme", "Dark", "stories"])
    assert gallery.calls == [(["Inputs/A", "Inputs/B"], "Dark")]


def test_the_gallery_gets_a_reload_session_for_the_targets_and_the_first_load(project: Path, gallery: _RecordingRun) -> None:
    assert cli.main(["stories"]) == 0

    (session,) = gallery.reloads
    assert session is not None
    assert session.targets == ("stories",)
    assert session.last_accepted.registry.ids() == ["Inputs/A", "Inputs/B"]


def test_no_reload_passes_no_session(project: Path, gallery: _RecordingRun) -> None:
    assert cli.main(["--no-reload", "stories"]) == 0
    assert gallery.reloads == [None]


def test_list_never_builds_a_reload_session(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> ReloadSession:
        raise AssertionError("--list must not build a reload session")

    monkeypatch.setattr(cli, "ReloadSession", refuse)
    assert cli.main(["--list", "stories"]) == 0


def test_the_gallery_exit_code_is_returned(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "run", _RecordingRun(exit_code=3))
    assert cli.main(["stories"]) == 3


def test_list_prints_story_ids_and_does_not_open_the_gallery(project: Path, gallery: _RecordingRun, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["--list", "stories"]) == 0
    captured = capsys.readouterr()
    assert captured.out.splitlines() == ["Inputs/A", "Inputs/B"]
    assert captured.err == "pyside6-storybook: stories from the command line\n"
    assert gallery.calls == []


def test_list_reports_import_errors_and_exits_non_zero(project: Path, gallery: _RecordingRun, capsys: pytest.CaptureFixture[str]) -> None:
    write(project, "stories/c_story.py", "raise RuntimeError('boom at import')\n")

    assert cli.main(["--list", "stories"]) == 1

    captured = capsys.readouterr()
    assert captured.out.splitlines() == ["Inputs/A", "Inputs/B"]
    assert "error: Importing" in captured.err
    assert "RuntimeError: boom at import" in captured.err
    assert gallery.calls == []


def test_a_story_that_fails_to_import_does_not_stop_the_gallery(project: Path, gallery: _RecordingRun, capsys: pytest.CaptureFixture[str]) -> None:
    write(project, "stories/c_story.py", "raise RuntimeError('boom at import')\n")

    assert cli.main(["stories"]) == 0

    assert gallery.calls == [(["Inputs/A", "Inputs/B"], None)]
    assert "RuntimeError: boom at import" in capsys.readouterr().err
    (passed_errors,) = gallery.load_errors
    assert [Path(error.source).name for error in passed_errors] == ["c_story.py"]
    assert "RuntimeError: boom at import" in passed_errors[0].details


def test_a_missing_target_exits_non_zero_without_opening_the_gallery(
    project: Path, gallery: _RecordingRun, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["stories", "no/such/folder"]) == 1

    assert "no/such/folder: no such file, folder or module" in capsys.readouterr().err
    assert gallery.calls == []


def test_no_stories_found_exits_non_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stories: StoryRegistry, gallery: _RecordingRun, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "empty").mkdir()
    monkeypatch.chdir(tmp_path)

    assert cli.main(["empty"]) == 1

    assert "no stories found in: empty" in capsys.readouterr().err
    assert gallery.calls == []


def test_no_targets_and_nothing_configured_opens_the_examples(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stories: StoryRegistry, gallery: _RecordingRun
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sources, "entry_points", lambda group: [])

    assert cli.main([]) == 0

    ((ids, _theme),) = gallery.calls
    assert "Buttons/Push Button/Default" in ids


def test_no_targets_opens_the_stories_configured_in_pyproject(project: Path, monkeypatch: pytest.MonkeyPatch, gallery: _RecordingRun) -> None:
    write(project, "pyproject.toml", '[tool.pyside6-storybook]\nstories = ["stories"]\n')
    monkeypatch.setattr(sources, "entry_points", lambda group: [])

    assert cli.main([]) == 0

    assert gallery.calls == [(["Inputs/A", "Inputs/B"], None)]


def test_pythonpath_lets_configured_stories_import_the_application(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stories: StoryRegistry, gallery: _RecordingRun
) -> None:
    write(tmp_path, "src/demo_app/__init__.py", "CAPTION = 'from src'\n")
    write(tmp_path, "gallery/app_story.py", story_source("App/Caption", "CAPTION", imports="from demo_app import CAPTION"))
    write(tmp_path, "pyproject.toml", '[tool.pyside6-storybook]\nstories = ["gallery"]\npythonpath = ["src"]\n')
    monkeypatch.chdir(tmp_path)

    assert cli.main([]) == 0

    assert gallery.calls == [(["App/Caption"], None)]


def test_a_typo_in_the_configured_stories_is_an_error_not_the_examples(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stories: StoryRegistry, gallery: _RecordingRun, capsys: pytest.CaptureFixture[str]
) -> None:
    write(tmp_path, "pyproject.toml", '[tool.pyside6-storybook]\nstories = ["storeis"]\n')
    monkeypatch.chdir(tmp_path)

    assert cli.main([]) == 1

    assert "storeis: no such file, folder or module" in capsys.readouterr().err
    assert gallery.calls == []


def test_a_broken_configuration_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stories: StoryRegistry, gallery: _RecordingRun, capsys: pytest.CaptureFixture[str]
) -> None:
    write(tmp_path, "pyproject.toml", '[tool.pyside6-storybook]\nstory = ["stories"]\n')
    monkeypatch.chdir(tmp_path)

    assert cli.main([]) == 1

    assert "unknown key 'story'" in capsys.readouterr().err
    assert gallery.calls == []


def test_list_says_where_the_stories_came_from(
    project: Path, monkeypatch: pytest.MonkeyPatch, gallery: _RecordingRun, capsys: pytest.CaptureFixture[str]
) -> None:
    write(project, "pyproject.toml", '[tool.pyside6-storybook]\nstories = ["stories"]\n')

    assert cli.main(["--list"]) == 0

    captured = capsys.readouterr()
    assert captured.out.splitlines() == ["Inputs/A", "Inputs/B"]
    assert f"stories from [tool.pyside6-storybook] in {project / 'pyproject.toml'}" in captured.err

def test_examples_open_the_gallery_with_the_example_stories(stories: StoryRegistry, gallery: _RecordingRun) -> None:
    assert cli.main(["--examples"]) == 0
    ((ids, _theme),) = gallery.calls
    assert "Buttons/Push Button/Default" in ids
    assert all(story_id.split("/")[0] in {"Buttons", "Display", "Forms", "Inputs"} for story_id in ids)


def test_examples_combine_with_targets(project: Path, gallery: _RecordingRun) -> None:
    assert cli.main(["stories", "--examples"]) == 0
    ((ids, _theme),) = gallery.calls
    assert ids[:2] == ["Inputs/A", "Inputs/B"]
    assert "Buttons/Push Button/Default" in ids


def test_list_examples_prints_the_example_ids(stories: StoryRegistry, gallery: _RecordingRun, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["--list", "--examples"]) == 0
    listed = capsys.readouterr().out.splitlines()
    assert listed[0] == "Buttons/Push Button/Default"
    assert "Inputs/Slider" in listed
    assert gallery.calls == []


def _installed_script() -> str:
    script = shutil.which("pyside6-storybook", path=str(Path(sys.executable).parent))
    if script is None:
        pytest.skip("the pyside6-storybook script is not installed in this environment")
    return script


def _without_platform_override() -> dict[str, str]:
    """The current environment without ``QT_QPA_PLATFORM``, to check that ``--list`` needs no display by itself."""
    return {key: value for key, value in os.environ.items() if key != "QT_QPA_PLATFORM"}


@pytest.mark.full
def test_the_installed_script_lists_stories_without_a_display(tmp_path: Path) -> None:
    write(tmp_path, "stories/a_story.py", story_source("Script/A"))
    imports = "from PySide6.QtWidgets import QLabel\n_LABEL = QLabel('made at import')"
    write(tmp_path, "stories/widget_at_import_story.py", story_source("Script/B", imports=imports))

    completed = subprocess.run(
        [_installed_script(), "--list", "stories"],
        cwd=tmp_path,
        env=_without_platform_override(),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.splitlines() == ["Script/A", "Script/B"]


@pytest.mark.full
def test_the_installed_script_lists_the_examples_without_a_display(tmp_path: Path) -> None:
    completed = subprocess.run(
        [_installed_script(), "--list", "--examples"],
        cwd=tmp_path,
        env=_without_platform_override(),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "Forms/Sign-in Form" in completed.stdout.splitlines()


@pytest.mark.full
def test_python_dash_m_runs_the_same_command(tmp_path: Path) -> None:
    write(tmp_path, "stories/a_story.py", story_source("Module/A"))

    completed = subprocess.run(
        [sys.executable, "-m", "pyside6_storybook", "--list", "stories"],
        cwd=tmp_path,
        env=_without_platform_override(),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.splitlines() == ["Module/A"]


def test_examples_are_the_bundled_ones_even_next_to_a_folder_of_the_same_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stories: StoryRegistry, gallery: _RecordingRun, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "pyside6_storybook.examples").mkdir()
    monkeypatch.chdir(tmp_path)

    assert cli.main(["--list", "--examples"]) == 0

    assert "Buttons/Push Button/Default" in capsys.readouterr().out.splitlines()


def test_pythonpath_folders_win_over_modules_at_the_project_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stories: StoryRegistry, gallery: _RecordingRun
) -> None:
    write(tmp_path, "demo_app/__init__.py", "CAPTION = 'from the root'\n")
    write(tmp_path, "src/demo_app/__init__.py", "CAPTION = 'from src'\n")
    write(tmp_path, "gallery/app_story.py", story_source("App/Caption", "CAPTION", imports="from demo_app import CAPTION"))
    write(tmp_path, "pyproject.toml", '[tool.pyside6-storybook]\nstories = ["gallery"]\npythonpath = ["src"]\n')
    monkeypatch.chdir(tmp_path)

    assert cli.main([]) == 0

    assert sys.modules["demo_app"].CAPTION == "from src"

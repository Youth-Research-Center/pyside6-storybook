import sys
import textwrap
from collections.abc import Iterator
from pathlib import Path

import pytest

from pyside6_storybook import StoryRegistry, load_stories
from pyside6_storybook import registry as registry_module


@pytest.fixture
def stories(monkeypatch: pytest.MonkeyPatch) -> Iterator[StoryRegistry]:
    """A fresh default registry, with ``sys.path`` and ``sys.modules`` restored after the test."""
    isolated = StoryRegistry()
    monkeypatch.setattr(registry_module, "default_registry", isolated)
    monkeypatch.setattr(sys, "path", list(sys.path))
    modules_before = set(sys.modules)
    try:
        yield isolated
    finally:
        for name in set(sys.modules) - modules_before:
            del sys.modules[name]


def _write(root: Path, relative: str, source: str = "") -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(source), encoding="utf-8")
    return path


def _story_source(story_id: str, text: str = "x", *, imports: str = "") -> str:
    return f"""
from PySide6.QtWidgets import QLabel

from pyside6_storybook import story
{imports}

@story({story_id!r})
def build(ctx):
    return QLabel({text})
"""


def test_a_folder_loads_every_story_file_below_it(tmp_path: Path, stories: StoryRegistry) -> None:
    _write(tmp_path, "stories/a_story.py", _story_source("A"))
    _write(tmp_path, "stories/b_stories.py", _story_source("B"))
    _write(tmp_path, "stories/nested/c_story.py", _story_source("C"))
    _write(tmp_path, "stories/helper.py", "raise RuntimeError('helpers are not stories')")
    _write(tmp_path, "stories/test_a_story_test.py", "raise RuntimeError('tests are not stories')")
    _write(tmp_path, "stories/conftest.py", "raise RuntimeError('conftest is not a story')")
    _write(tmp_path, "stories/.hidden/d_story.py", "raise RuntimeError('hidden folders are skipped')")
    _write(tmp_path, "stories/venv/pyvenv.cfg", "home = /usr")
    _write(tmp_path, "stories/venv/lib/e_story.py", "raise RuntimeError('virtual environments are skipped')")

    result = load_stories(["stories"], cwd=tmp_path)

    assert result.errors == ()
    assert result.registry is stories
    assert stories.ids() == ["A", "B", "C"]
    assert len(result.modules) == 3


def test_a_package_whose_init_imports_its_story_modules_registers_each_story_once(tmp_path: Path, stories: StoryRegistry) -> None:
    """PandaPlot's layout: the stories package imports every story module, and the stories import the application from the cwd."""
    _write(tmp_path, "app/__init__.py")
    _write(tmp_path, "app/widgets.py", "def caption(name):\n    return f'app {name}'\n")
    _write(tmp_path, "gallery/__init__.py")
    _write(tmp_path, "gallery/stories/__init__.py", "from gallery.stories import a_story, b_story\n")
    _write(tmp_path, "gallery/stories/a_story.py", _story_source("Inputs/A", "caption('a')", imports="from app.widgets import caption"))
    _write(tmp_path, "gallery/stories/b_story.py", _story_source("Inputs/B", "caption('b')", imports="from app.widgets import caption"))

    result = load_stories(["gallery/stories"], cwd=tmp_path)

    assert result.errors == ()
    assert stories.ids() == ["Inputs/A", "Inputs/B"]
    assert result.modules == ("gallery.stories.a_story", "gallery.stories.b_story")
    assert stories.get("Inputs/A").module == "gallery.stories.a_story"


def test_relative_imports_work_inside_a_story_package(tmp_path: Path, stories: StoryRegistry) -> None:
    _write(tmp_path, "kit/__init__.py")
    _write(tmp_path, "kit/_shared.py", "TEXT = 'shared'\n")
    _write(tmp_path, "kit/a_story.py", _story_source("Relative", "TEXT", imports="from ._shared import TEXT"))

    result = load_stories(["kit"], cwd=tmp_path)

    assert result.errors == ()
    assert stories.ids() == ["Relative"]


def test_a_package_given_as_folder_and_as_dotted_name_is_loaded_once(tmp_path: Path, stories: StoryRegistry) -> None:
    _write(tmp_path, "kit/__init__.py")
    _write(tmp_path, "kit/a_story.py", _story_source("Once"))

    result = load_stories(["kit", "kit", "kit.a_story", "kit/a_story.py"], cwd=tmp_path)

    assert result.errors == ()
    assert stories.ids() == ["Once"]
    assert result.modules == ("kit.a_story",)


def test_a_dotted_package_imports_only_its_story_modules(tmp_path: Path, stories: StoryRegistry) -> None:
    _write(tmp_path, "kit/__init__.py")
    _write(tmp_path, "kit/stories/__init__.py")
    _write(tmp_path, "kit/stories/__main__.py", "raise RuntimeError('__main__ must not be imported')")
    _write(tmp_path, "kit/stories/conftest.py", "raise RuntimeError('conftest must not be imported')")
    _write(tmp_path, "kit/stories/test_kit.py", "raise RuntimeError('tests must not be imported')")
    _write(tmp_path, "kit/stories/helpers.py", "raise RuntimeError('helpers must not be imported')")
    _write(tmp_path, "kit/stories/a_story.py", _story_source("Kit/A"))
    _write(tmp_path, "kit/stories/inner/__init__.py")
    _write(tmp_path, "kit/stories/inner/b_stories.py", _story_source("Kit/B"))
    _write(tmp_path, "kit/stories/not_a_package/c_story.py", "raise RuntimeError('only regular subpackages are searched')")

    result = load_stories(["kit.stories"], cwd=tmp_path)

    assert result.errors == ()
    assert stories.ids() == ["Kit/A", "Kit/B"]
    assert result.modules == ("kit.stories.a_story", "kit.stories.inner.b_stories")
    assert not {"kit.stories.__main__", "kit.stories.conftest", "kit.stories.test_kit", "kit.stories.helpers"} & set(sys.modules)


def test_a_dotted_module_is_loaded_whatever_its_name(tmp_path: Path, stories: StoryRegistry) -> None:
    _write(tmp_path, "widgets_gallery.py", _story_source("Module"))

    result = load_stories(["widgets_gallery"], cwd=tmp_path)

    assert result.errors == ()
    assert result.modules == ("widgets_gallery",)
    assert stories.ids() == ["Module"]


def test_a_file_outside_any_package_gets_a_stable_synthetic_name_and_can_import_siblings(tmp_path: Path, stories: StoryRegistry) -> None:
    _write(tmp_path, "loose/helper.py", "TEXT = 'sibling'\n")
    story_file = _write(tmp_path, "loose/x_story.py", _story_source("Loose", "TEXT", imports="from helper import TEXT"))

    first = load_stories([story_file], cwd=tmp_path)
    second = load_stories([str(story_file)], cwd=tmp_path)

    assert first.errors == () and second.errors == ()
    assert stories.ids() == ["Loose"]
    assert first.modules == second.modules
    (module_name,) = first.modules
    assert module_name.startswith("_pyside6_storybook_x_story_")


def test_files_with_the_same_name_in_different_folders_do_not_collide(tmp_path: Path, stories: StoryRegistry) -> None:
    _write(tmp_path, "one/button_story.py", _story_source("One/Button"))
    _write(tmp_path, "two/button_story.py", _story_source("Two/Button"))

    result = load_stories(["one", "two"], cwd=tmp_path)

    assert result.errors == ()
    assert stories.ids() == ["One/Button", "Two/Button"]
    assert len(set(result.modules)) == 2


def test_an_existing_path_wins_over_a_module_of_the_same_name(tmp_path: Path, stories: StoryRegistry) -> None:
    _write(tmp_path, "json/x_story.py", _story_source("Not the json module"))

    result = load_stories(["json"], cwd=tmp_path)

    assert result.errors == ()
    assert stories.ids() == ["Not the json module"]


def test_a_missing_target_is_reported_and_the_others_still_load(tmp_path: Path, stories: StoryRegistry) -> None:
    _write(tmp_path, "stories/a_story.py", _story_source("A"))

    result = load_stories(["no/such/folder", "no_such_module", "stories"], cwd=tmp_path)

    assert stories.ids() == ["A"]
    assert [error.source for error in result.errors] == ["no/such/folder", "no_such_module"]
    assert all("no such file, folder or module" in error.message for error in result.errors)


def test_import_errors_are_collected_with_tracebacks(tmp_path: Path, stories: StoryRegistry) -> None:
    _write(tmp_path, "stories/a_story.py", _story_source("A"))
    broken = _write(tmp_path, "stories/broken_story.py", "def oops(:\n")
    raising = _write(tmp_path, "stories/raising_story.py", "raise RuntimeError('boom at import')\n")

    result = load_stories(["stories"], cwd=tmp_path)

    assert stories.ids() == ["A"]
    assert [error.source for error in result.errors] == [str(broken.resolve()), str(raising.resolve())]
    assert "SyntaxError" in result.errors[0].details
    assert "RuntimeError: boom at import" in result.errors[1].details
    assert len(result.modules) == 1
    assert not any("broken_story" in name or "raising_story" in name for name in sys.modules)


def test_a_story_id_registered_by_two_modules_is_reported(tmp_path: Path, stories: StoryRegistry) -> None:
    _write(tmp_path, "stories/a_story.py", _story_source("Same"))
    second = _write(tmp_path, "stories/b_story.py", _story_source("Same"))

    result = load_stories(["stories"], cwd=tmp_path)

    assert stories.ids() == ["Same"]
    assert [error.source for error in result.errors] == [str(second.resolve())]
    assert "already registered" in result.errors[0].details


def test_a_module_name_taken_by_another_file_is_reported(tmp_path: Path, stories: StoryRegistry) -> None:
    _write(tmp_path, "first/kit/__init__.py")
    _write(tmp_path, "first/kit/a_story.py", _story_source("First"))
    _write(tmp_path, "second/kit/__init__.py")
    clash = _write(tmp_path, "second/kit/a_story.py", _story_source("Second"))

    result = load_stories(["first/kit", "second/kit"], cwd=tmp_path)

    assert stories.ids() == ["First"]
    assert [error.source for error in result.errors] == [str(clash.resolve())]
    assert "kit.a_story" in result.errors[0].message


def test_a_file_that_is_not_python_is_reported(tmp_path: Path, stories: StoryRegistry) -> None:
    _write(tmp_path, "notes.txt", "not python")

    result = load_stories(["notes.txt"], cwd=tmp_path)

    assert [error.source for error in result.errors] == ["notes.txt"]
    assert "not a Python file" in result.errors[0].message


def test_the_working_directory_is_put_on_sys_path_once(tmp_path: Path, stories: StoryRegistry) -> None:
    load_stories([], cwd=tmp_path)
    load_stories([], cwd=tmp_path)

    assert sys.path.count(str(tmp_path.resolve())) == 1


@pytest.mark.parametrize("order", [("widgets_gallery.py", "widgets_gallery"), ("widgets_gallery", "widgets_gallery.py")])
def test_a_top_level_file_given_by_path_and_by_module_name_is_loaded_once(tmp_path: Path, stories: StoryRegistry, order: tuple[str, str]) -> None:
    _write(tmp_path, "widgets_gallery.py", _story_source("Top level"))

    result = load_stories(order, cwd=tmp_path)

    assert result.errors == ()
    assert stories.ids() == ["Top level"]
    assert len(result.modules) == 1


def test_a_dotted_target_whose_import_fails_is_reported_with_its_traceback(tmp_path: Path, stories: StoryRegistry) -> None:
    _write(tmp_path, "kit/__init__.py", "import missing_dependency_for_kit\n")
    _write(tmp_path, "kit/a_story.py", _story_source("Kit/A"))

    result = load_stories(["kit.a_story"], cwd=tmp_path)

    assert stories.ids() == []
    assert [error.source for error in result.errors] == ["kit.a_story"]
    assert "missing_dependency_for_kit" in result.errors[0].details
    assert "no such file" not in result.errors[0].message


def test_a_story_file_importing_a_missing_module_is_reported_as_an_import_failure(tmp_path: Path, stories: StoryRegistry) -> None:
    _write(tmp_path, "kit/__init__.py")
    story_file = _write(tmp_path, "kit/a_story.py", "import missing_dependency_for_story\n")

    by_path = load_stories(["kit"], cwd=tmp_path)
    by_name = load_stories(["kit.a_story"], cwd=tmp_path)

    assert [error.source for error in by_path.errors] == [str(story_file.resolve())]
    assert [error.source for error in by_name.errors] == ["kit.a_story"]
    for error in (*by_path.errors, *by_name.errors):
        assert "missing_dependency_for_story" in error.details

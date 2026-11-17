import importlib.util
import itertools
import os
import sys
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QLabel
from story_files import story_source, write

import pyside6_storybook
from pyside6_storybook import StoryContext, StoryRegistry, load_stories
from pyside6_storybook import registry as registry_module
from pyside6_storybook.discovery.reload import ReloadSession
from pyside6_storybook.discovery.sources import EXAMPLES_FOLDER
from pyside6_storybook.themes.provider_loader import load_theme_provider

_clock = itertools.count(2_000_000_000, 10)


def _write(root: Path, relative: str, source: str) -> Path:
    """Write a file with a modification time later than any earlier call's, whatever the file system's resolution."""
    path = write(root, relative, source)
    stamp = next(_clock)
    os.utime(path, (stamp, stamp))
    return path


def _text(registry: StoryRegistry, story_id: str) -> str:
    widget = registry.get(story_id)(StoryContext(args={}))
    assert isinstance(widget, QLabel)
    return widget.text()


def _session(
    root: Path, targets: tuple[str, ...] = ("stories",), *, pythonpath: tuple[Path, ...] = ()
) -> ReloadSession:
    result = load_stories(targets, cwd=root)
    assert result.errors == ()
    return ReloadSession(targets, cwd=root, pythonpath=pythonpath, initial=result)


def test_editing_a_story_text_is_picked_up(qapp: QApplication, tmp_path: Path, stories: StoryRegistry) -> None:
    path = _write(tmp_path, "stories/a_story.py", story_source("Inputs/A", "'one'"))
    session = _session(tmp_path)
    assert _text(stories, "Inputs/A") == "one"

    _write(tmp_path, "stories/a_story.py", story_source("Inputs/A", "'two'"))
    result = session.reload()

    assert path.exists()
    assert result.accepted
    assert result.new_errors == ()
    assert result.load.registry is not stories
    assert _text(result.load.registry, "Inputs/A") == "two"
    assert session.last_accepted is result.load
    assert registry_module.default_registry is result.load.registry
    assert pyside6_storybook.default_registry is result.load.registry


def test_a_new_story_file_is_added_and_a_deleted_one_is_removed(qapp: QApplication, tmp_path: Path, stories: StoryRegistry) -> None:
    _write(tmp_path, "stories/a_story.py", story_source("Inputs/A"))
    b_path = _write(tmp_path, "stories/b_story.py", story_source("Inputs/B"))
    session = _session(tmp_path)

    _write(tmp_path, "stories/c_story.py", story_source("Inputs/C"))
    added = session.reload()
    b_path.unlink()
    removed = session.reload()

    assert added.accepted
    assert added.load.registry.ids() == ["Inputs/A", "Inputs/B", "Inputs/C"]
    assert removed.accepted
    assert removed.load.registry.ids() == ["Inputs/A", "Inputs/C"]
    assert "b_story" not in sys.modules


def test_editing_a_widget_class_in_an_imported_module_is_picked_up(qapp: QApplication, tmp_path: Path, stories: StoryRegistry) -> None:
    widgets = """
    from PySide6.QtWidgets import QLabel


    class Greeting(QLabel):
        def __init__(self) -> None:
            super().__init__("{text}")
    """
    _write(tmp_path, "widgets.py", widgets.format(text="hello"))
    story = story_source("Inputs/A", "''", imports="from widgets import Greeting").replace("return QLabel('')", "return Greeting()")
    _write(tmp_path, "stories/a_story.py", story)
    session = _session(tmp_path)
    assert _text(stories, "Inputs/A") == "hello"
    assert tmp_path / "widgets.py" in session.watched_files()

    _write(tmp_path, "widgets.py", widgets.format(text="goodbye"))
    result = session.reload()

    assert result.accepted
    assert _text(result.load.registry, "Inputs/A") == "goodbye"


def test_a_same_size_edit_in_the_same_second_runs_the_new_code(qapp: QApplication, tmp_path: Path, stories: StoryRegistry) -> None:
    if sys.dont_write_bytecode:
        pytest.skip("bytecode is not written in this process")
    path = _write(tmp_path, "stories/a_story.py", story_source("Inputs/A", "'one1'"))
    session = _session(tmp_path)
    assert Path(importlib.util.cache_from_source(str(path))).is_file()
    before = path.stat()

    path.write_text(story_source("Inputs/A", "'two2'"), encoding="utf-8")
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert path.stat().st_size == before.st_size
    result = session.reload()

    assert result.accepted
    assert _text(result.load.registry, "Inputs/A") == "two2"


def test_a_syntax_error_is_rejected_and_the_old_state_is_restored_then_the_fix_is_accepted(
    qapp: QApplication, tmp_path: Path, stories: StoryRegistry
) -> None:
    _write(tmp_path, "stories/a_story.py", story_source("Inputs/A", "'one'"))
    session = _session(tmp_path)
    module = sys.modules["a_story"]

    _write(tmp_path, "stories/a_story.py", "def broken(:\n")
    rejected = session.reload()

    assert not rejected.accepted
    assert [error.source for error in rejected.new_errors] == [str(tmp_path / "stories" / "a_story.py")]
    assert registry_module.default_registry is stories
    assert pyside6_storybook.default_registry is stories
    assert session.last_accepted.registry is stories
    assert sys.modules["a_story"] is module
    assert _text(stories, "Inputs/A") == "one"

    _write(tmp_path, "stories/a_story.py", story_source("Inputs/A", "'fixed'"))
    accepted = session.reload()

    assert accepted.accepted
    assert _text(accepted.load.registry, "Inputs/A") == "fixed"


def test_a_rejected_reload_forgets_the_modules_it_imported_so_a_retry_imports_them_again(
    qapp: QApplication, tmp_path: Path, stories: StoryRegistry
) -> None:
    _write(tmp_path, "stories/a_story.py", story_source("Inputs/A"))
    session = _session(tmp_path)

    _write(tmp_path, "stories/a_story.py", "def broken(:\n")
    _write(tmp_path, "stories/b_story.py", story_source("Inputs/B"))
    rejected = session.reload()

    assert not rejected.accepted
    assert "b_story" not in sys.modules
    _write(tmp_path, "stories/a_story.py", story_source("Inputs/A"))
    accepted = session.reload()

    assert accepted.accepted
    assert accepted.load.registry.ids() == ["Inputs/A", "Inputs/B"]


def test_a_source_that_was_already_failing_does_not_reject_a_reload(qapp: QApplication, tmp_path: Path, stories: StoryRegistry) -> None:
    _write(tmp_path, "stories/a_story.py", story_source("Inputs/A", "'one'"))
    _write(tmp_path, "stories/broken_story.py", "def broken(:\n")
    initial = load_stories(["stories"], cwd=tmp_path)
    assert len(initial.errors) == 1
    session = ReloadSession(["stories"], cwd=tmp_path, initial=initial)

    _write(tmp_path, "stories/a_story.py", story_source("Inputs/A", "'two'"))
    result = session.reload()

    assert result.accepted
    assert result.new_errors == ()
    assert len(result.load.errors) == 1
    assert _text(result.load.registry, "Inputs/A") == "two"


def test_a_reload_without_stories_is_rejected(qapp: QApplication, tmp_path: Path, stories: StoryRegistry) -> None:
    path = _write(tmp_path, "stories/a_story.py", story_source("Inputs/A"))
    session = _session(tmp_path)

    path.unlink()
    result = session.reload()

    assert not result.accepted
    assert result.new_errors == ()
    assert len(result.load.registry) == 0
    assert registry_module.default_registry is stories
    assert stories.ids() == ["Inputs/A"]


def test_the_example_stories_survive_a_reload(qapp: QApplication, stories: StoryRegistry) -> None:
    targets = (str(EXAMPLES_FOLDER),)
    initial = load_stories(targets)
    assert initial.errors == ()
    ids = initial.registry.ids()
    session = ReloadSession(targets, cwd=Path.cwd(), initial=initial)

    result = session.reload()

    assert result.accepted
    assert result.load.registry is not initial.registry
    assert result.load.registry.ids() == ids
    assert len(ids) > 0


def test_a_package_init_that_appends_a_decorator_ends_with_one_decorator(qapp: QApplication, tmp_path: Path, stories: StoryRegistry) -> None:
    _write(
        tmp_path,
        "kit/__init__.py",
        """
        from pyside6_storybook import default_registry
        from pyside6_storybook.decorators import padding

        default_registry.decorators.append(padding(4))
        """,
    )
    _write(tmp_path, "kit/a_stories.py", story_source("Kit/A"))
    session = _session(tmp_path, ("kit",))
    assert len(stories.decorators) == 1

    result = session.reload()

    assert result.accepted
    assert result.load.registry.ids() == ["Kit/A"]
    assert len(result.load.registry.decorators) == 1
    assert len(stories.decorators) == 1


def test_a_package_target_with_stories_only_in_its_init_is_reloaded(qapp: QApplication, tmp_path: Path, stories: StoryRegistry) -> None:
    library = tmp_path / "lib"
    _write(library, "kit_only/__init__.py", story_source("Kit/Only", "'one'"))
    sys.path.insert(0, str(library))
    initial = load_stories(["kit_only"], cwd=tmp_path)
    assert initial.errors == ()
    assert initial.modules == ("kit_only",)
    session = ReloadSession(["kit_only"], cwd=tmp_path, pythonpath=[library], initial=initial)

    _write(library, "kit_only/__init__.py", story_source("Kit/Only", "'two'"))
    result = session.reload()

    assert result.accepted
    assert result.load.registry.ids() == ["Kit/Only"]
    assert _text(result.load.registry, "Kit/Only") == "two"
    assert library / "kit_only" / "__init__.py" in session.watched_files()


def test_modules_under_site_packages_and_hidden_folders_are_left_alone(qapp: QApplication, tmp_path: Path, stories: StoryRegistry) -> None:
    _write(tmp_path, "stories/a_story.py", story_source("Inputs/A"))
    _write(tmp_path, "site-packages/vendored.py", "VALUE = 1\n")
    _write(tmp_path, ".hidden/secret.py", "VALUE = 1\n")
    sys.path[:0] = [str(tmp_path / "site-packages"), str(tmp_path / ".hidden")]
    vendored = importlib.import_module("vendored")
    secret = importlib.import_module("secret")

    session = _session(tmp_path)
    result = session.reload()

    assert result.accepted
    assert sys.modules["vendored"] is vendored
    assert sys.modules["secret"] is secret


def test_watched_files_include_a_story_source_that_failed_to_import(qapp: QApplication, tmp_path: Path, stories: StoryRegistry) -> None:
    _write(tmp_path, "stories/a_story.py", story_source("Inputs/A"))
    broken = _write(tmp_path, "stories/broken_story.py", "def broken(:\n")
    single = _write(tmp_path, "single.py", "def broken(:\n")
    targets = ("stories", "single.py")
    initial = load_stories(targets, cwd=tmp_path)
    session = ReloadSession(targets, cwd=tmp_path, initial=initial)

    assert {tmp_path / "stories" / "a_story.py", broken, single} <= session.watched_files()
    assert session.watched_folders() == {tmp_path / "stories"}
    assert session.story_file_set() == {tmp_path / "stories" / "a_story.py", broken}


def _write_theming_app(root: Path) -> None:
    """A package ``theming_app`` whose ``manager`` module holds a singleton, and a provider module that imports it."""
    write(root, "theming_app/__init__.py", "")
    write(root, "theming_app/manager.py", "MANAGER = object()\n")
    write(
        root,
        "theming_app/theming.py",
        """
from theming_app import manager


class Provider:
    def theme_names(self):
        return ("Paper", "Ink")

    def current_theme(self):
        return "Paper"

    def activate(self, app):
        pass

    def set_theme(self, name):
        pass

    def on_changed(self, callback):
        pass

    def deactivate(self):
        pass


provider = Provider()
""",
    )


def _manager_story(text: str) -> str:
    return story_source("Inputs/A", f"{text!r} + str(id(manager.MANAGER))", imports="from theming_app import manager")


def test_a_kept_provider_module_is_neither_dropped_nor_watched(qapp: QApplication, tmp_path: Path, stories: StoryRegistry) -> None:
    _write_theming_app(tmp_path)
    _write(tmp_path, "stories/a_story.py", _manager_story("one"))
    sys.path.insert(0, str(tmp_path))
    loaded = load_theme_provider("theming_app.theming:provider")
    result = load_stories(("stories",), cwd=tmp_path)
    assert result.errors == ()
    session = ReloadSession(("stories",), cwd=tmp_path, initial=result, keep=loaded.modules)
    manager_module = sys.modules["theming_app.manager"]
    package = sys.modules["theming_app"]
    manager_id = str(id(manager_module.MANAGER))
    assert _text(stories, "Inputs/A") == "one" + manager_id

    _write(tmp_path, "stories/a_story.py", _manager_story("two"))
    reloaded = session.reload()

    assert reloaded.accepted
    assert sys.modules["theming_app.manager"] is manager_module
    assert sys.modules["theming_app"] is package
    assert _text(reloaded.load.registry, "Inputs/A") == "two" + manager_id
    watched = {path.resolve() for path in session.watched_files()}
    assert (tmp_path / "stories" / "a_story.py").resolve() in watched
    assert not any("theming_app" in path.parts for path in watched)


def test_without_keep_the_provider_module_is_reloaded_and_watched(qapp: QApplication, tmp_path: Path, stories: StoryRegistry) -> None:
    _write_theming_app(tmp_path)
    _write(tmp_path, "stories/a_story.py", _manager_story("one"))
    sys.path.insert(0, str(tmp_path))
    __import__("theming_app.theming")
    result = load_stories(("stories",), cwd=tmp_path)
    session = ReloadSession(("stories",), cwd=tmp_path, initial=result)
    first = sys.modules["theming_app.manager"]

    assert any("theming_app" in path.parts for path in session.watched_files())
    _write(tmp_path, "stories/a_story.py", _manager_story("two"))
    assert session.reload().accepted

    assert sys.modules["theming_app.manager"] is not first


def test_keep_modules_adds_names_and_their_parents(qapp: QApplication, tmp_path: Path, stories: StoryRegistry) -> None:
    _write_theming_app(tmp_path)
    _write(tmp_path, "stories/a_story.py", _manager_story("one"))
    sys.path.insert(0, str(tmp_path))
    __import__("theming_app.manager")
    result = load_stories(("stories",), cwd=tmp_path)
    session = ReloadSession(("stories",), cwd=tmp_path, initial=result)
    manager_module = sys.modules["theming_app.manager"]
    package = sys.modules["theming_app"]

    session.keep_modules(["theming_app.manager"])
    _write(tmp_path, "stories/a_story.py", _manager_story("two"))
    assert session.reload().accepted

    assert sys.modules["theming_app.manager"] is manager_module
    assert sys.modules["theming_app"] is package

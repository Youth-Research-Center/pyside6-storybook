"""Check that an installed pyside6-storybook works, as a user would find it after ``pip install``.

Run it with ``python -I`` from an empty directory, so neither this folder nor the working directory is on ``sys.path`` and the
installed package is the one under test::

    python -I smoke_check.py 0.1.0

The script uses the standard library and the installed package only: it imports nothing from the repository. It prints ``ok: <what>``
for every step and exits with 1 and a message on standard error at the first failure. ``--skip-installed-check`` turns off the first
step, for running the script against a development install.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import sysconfig
import tempfile
from collections.abc import Callable, Collection, Sequence
from pathlib import Path

EXPECTED_STORY_IDS = frozenset(
    {
        "Buttons/Push Button/Default",
        "Buttons/Push Button/Disabled",
        "Buttons/Push Button/Checkable",
        "Buttons/Check Box",
        "Display/Label",
        "Display/Progress Bar",
        "Display/Palette",
        "Display/Color Swatch",
        "Display/Alignment",
        "Display/Table",
        "Display/Token Badge",
        "Forms/Sign-in Form",
        "Inputs/Line Edit/Default",
        "Inputs/Line Edit/Password",
        "Inputs/Line Edit/Read-only",
        "Inputs/Spin Box",
        "Inputs/Double Spin Box",
        "Inputs/Combo Box",
        "Inputs/Slider",
        "Inputs/File Path",
    }
)

THEMES = ("Light", "Dark")
EXAMPLES_MODULE = "pyside6_storybook.examples"
PROGRAM_NAME = "pyside6-storybook"
SUBPROCESS_TIMEOUT = 120
PYTEST_TIMEOUT = 300
EXPECTED_PYTEST_SUMMARY = "40 passed"


class SmokeFailure(Exception):
    """A check failed; the message says what and why."""


def _ok(what: str) -> None:
    print(f"ok: {what}", flush=True)


def package_directory() -> Path:
    """Return the folder of the imported ``pyside6_storybook`` package."""
    import pyside6_storybook

    return Path(pyside6_storybook.__file__).resolve().parent


def _run(command: Sequence[str | os.PathLike[str]], *, package_dir: Path, timeout: int = SUBPROCESS_TIMEOUT) -> subprocess.CompletedProcess[str]:
    """Run a command that imports the package from ``package_dir``'s parent folder, and capture its output."""
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(filter(None, [str(package_dir.parent), environment.get("PYTHONPATH")]))
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False, env=environment)
    except subprocess.TimeoutExpired as error:
        raise SmokeFailure(f"{list(map(str, command))} did not finish within {timeout} seconds") from error


def check_installed(package_dir: Path, purelib: Path | None = None) -> None:
    """Step 1: the package is imported from the environment's ``purelib`` folder, not from a source tree.

    Args:
        package_dir: The folder of the imported package.
        purelib: The site-packages folder; defaults to ``sysconfig.get_paths()["purelib"]``.

    Raises:
        SmokeFailure: If the package is somewhere else.
    """
    site_packages = Path(sysconfig.get_paths()["purelib"] if purelib is None else purelib).resolve()
    if site_packages not in package_dir.resolve().parents:
        raise SmokeFailure(f"pyside6_storybook is imported from {package_dir}, not from {site_packages}")
    _ok(f"installed package in {site_packages}")


def _console_script() -> Path:
    name = f"{PROGRAM_NAME}.exe" if sys.platform == "win32" else PROGRAM_NAME
    return Path(sys.executable).parent / name


def check_version(version: str, package_dir: Path) -> None:
    """Step 2: ``__version__`` and the console script's ``--version`` both report ``version``.

    Args:
        version: The expected version.
        package_dir: The folder of the package under test.

    Raises:
        SmokeFailure: If either differs, or the console script is missing or fails.
    """
    import pyside6_storybook

    if pyside6_storybook.__version__ != version:
        raise SmokeFailure(f"pyside6_storybook.__version__ is {pyside6_storybook.__version__!r}, expected {version!r}")
    _ok(f"__version__ is {version}")
    script = _console_script()
    if not script.is_file():
        raise SmokeFailure(f"the console script {script} does not exist")
    completed = _run([script, "--version"], package_dir=package_dir)
    expected = f"{PROGRAM_NAME} {version}"
    if completed.returncode != 0 or completed.stdout.strip() != expected:
        raise SmokeFailure(f"`{PROGRAM_NAME} --version` exited {completed.returncode} and printed {completed.stdout!r}, expected {expected!r}")
    _ok(f"`{PROGRAM_NAME} --version` prints {expected!r}")


def check_package_data(package_dir: Path) -> None:
    """Step 3: ``py.typed``, every bundled icon and the Phosphor licence are in the package.

    Args:
        package_dir: The folder of the package under test.

    Raises:
        SmokeFailure: If a file is missing or an icon has no SVG.
    """
    if not (package_dir / "py.typed").is_file():
        raise SmokeFailure(f"{package_dir / 'py.typed'} is missing")
    _ok("py.typed is present")
    icons_folder = package_dir / "resources" / "icons"
    bundle = icons_folder / "icon_bundle.json"
    if not bundle.is_file():
        raise SmokeFailure(f"{bundle} is missing")
    names = sorted(json.loads(bundle.read_text(encoding="utf-8"))["icons"])
    if not names:
        raise SmokeFailure(f"{bundle} lists no icons")
    from pyside6_storybook.gui.icons import icon_svg

    for name in names:
        try:
            svg = icon_svg(name)
        except Exception as error:
            raise SmokeFailure(f"icon_svg({name!r}) failed: {error}") from error
        if "<svg" not in svg:
            raise SmokeFailure(f"icon_svg({name!r}) did not return an SVG")
    _ok(f"icon_svg returns an SVG for all {len(names)} bundled icons")
    licence = icons_folder / "licenses" / "phosphor-LICENSE.txt"
    if not licence.is_file():
        raise SmokeFailure(f"{licence} is missing")
    _ok("the Phosphor licence is present")


def _story_ids(command: Sequence[str | os.PathLike[str]], *, package_dir: Path) -> list[str]:
    completed = _run(command, package_dir=package_dir)
    if completed.returncode != 0:
        raise SmokeFailure(f"{[str(part) for part in command]} exited {completed.returncode}:\n{completed.stderr}")
    return completed.stdout.splitlines()


def check_examples(expected_ids: Collection[str], package_dir: Path) -> None:
    """Step 4: both command lines list the same story ids for ``--examples``, and they are exactly ``expected_ids``.

    Args:
        expected_ids: The ids the examples must have.
        package_dir: The folder of the package under test.

    Raises:
        SmokeFailure: If a command fails, the two lists differ or the ids are not the expected ones.
    """
    from_script = _story_ids([_console_script(), "--list", "--examples"], package_dir=package_dir)
    from_module = _story_ids([sys.executable, "-m", "pyside6_storybook", "--list", "--examples"], package_dir=package_dir)
    if from_script != from_module:
        raise SmokeFailure(f"`{PROGRAM_NAME}` and `python -m pyside6_storybook` list different stories:\n{from_script}\n{from_module}")
    _ok(f"`{PROGRAM_NAME} --list --examples` and `python -m pyside6_storybook --list --examples` agree")
    found = set(from_script)
    if found != set(expected_ids) or len(from_script) != len(found):
        missing, unexpected = sorted(set(expected_ids) - found), sorted(found - set(expected_ids))
        raise SmokeFailure(f"the examples are not the expected stories: missing {missing}, unexpected {unexpected}")
    _ok(f"the {len(found)} example ids are the expected ones")


def _forget_examples() -> None:
    """Drop the example modules from ``sys.modules``, so loading them again runs their ``@story`` decorators."""
    for name in [name for name in sys.modules if name == EXAMPLES_MODULE or name.startswith(f"{EXAMPLES_MODULE}.")]:
        del sys.modules[name]


def check_gallery(expected_ids: Collection[str]) -> None:
    """Step 5: the gallery window shows every example, in every built-in theme, without the error panel.

    Loads the examples into a fresh registry, builds a ``GalleryWindow`` with the built-in provider, selects each story in Light
    and Dark and checks that it built its widget. The window is closed and deleted and the provider deactivated afterwards.

    Args:
        expected_ids: The ids to select.

    Raises:
        SmokeFailure: If the examples fail to load, a story cannot be selected or a story shows the error panel.
    """
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QFontDatabase
    from PySide6.QtWidgets import QApplication

    import pyside6_storybook
    import pyside6_storybook.registry as registry_module
    from pyside6_storybook import StoryRegistry, load_stories
    from pyside6_storybook.gui.window import GalleryWindow
    from pyside6_storybook.themes import BuiltinThemeProvider

    existing = QApplication.instance()
    app = existing if isinstance(existing, QApplication) else QApplication([PROGRAM_NAME])
    # The first use of a font logs a Qt warning on Windows and macOS, to standard error; it does not matter here, so load them up front.
    print("loading fonts", file=sys.stderr, flush=True)
    QFontDatabase.families()

    fresh = StoryRegistry()
    original = registry_module.default_registry, pyside6_storybook.default_registry
    registry_module.default_registry = pyside6_storybook.default_registry = fresh
    provider = BuiltinThemeProvider()
    window: GalleryWindow | None = None
    try:
        _forget_examples()
        result = load_stories([EXAMPLES_MODULE])
        if result.errors:
            raise SmokeFailure(f"the examples failed to load: {[error.message for error in result.errors]}")
        if set(fresh.ids()) != set(expected_ids):
            raise SmokeFailure(f"the examples registered {sorted(fresh.ids())}, expected {sorted(expected_ids)}")
        provider.activate(app)
        window = GalleryWindow(fresh, provider)
        window.show()
        app.processEvents()
        for theme in THEMES:
            window.set_theme(theme)
            app.processEvents()
            for story_id in sorted(expected_ids):
                if not window.select_story(story_id):
                    raise SmokeFailure(f"the gallery has no story {story_id!r}")
                app.processEvents()
                if window.current_preview_widget() is None:
                    raise SmokeFailure(f"{story_id!r} shows no widget in the {theme} theme (the error panel is shown)")
            _ok(f"the gallery shows all {len(expected_ids)} stories in the {theme} theme")
    finally:
        if window is not None:
            window.close()
            window.deleteLater()
            QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        provider.deactivate()
        registry_module.default_registry, pyside6_storybook.default_registry = original
        _forget_examples()


def check_pytest_plugin() -> None:
    """Step 6: the pytest plugin loads through its entry point and passes every example in both themes.

    Raises:
        SmokeFailure: If pytest fails, times out or does not report the expected summary.
    """
    command = [
        sys.executable,
        "-m",
        "pytest",
        "--storybook",
        "--storybook-stories",
        EXAMPLES_MODULE,
        "--storybook-themes",
        ",".join(THEMES),
        "-q",
        "-p",
        "no:cacheprovider",
    ]
    with tempfile.TemporaryDirectory() as folder:
        Path(folder, "pyproject.toml").write_text("", encoding="utf-8")
        try:
            completed = subprocess.run(command, cwd=folder, capture_output=True, text=True, timeout=PYTEST_TIMEOUT, check=False)
        except subprocess.TimeoutExpired as error:
            raise SmokeFailure(f"pytest did not finish within {PYTEST_TIMEOUT} seconds") from error
    if completed.returncode != 0 or EXPECTED_PYTEST_SUMMARY not in completed.stdout:
        raise SmokeFailure(f"pytest exited {completed.returncode}, expected {EXPECTED_PYTEST_SUMMARY!r}:\n{completed.stdout}\n{completed.stderr}")
    _ok(f"the pytest plugin runs the examples ({EXPECTED_PYTEST_SUMMARY})")


def run_checks(version: str, *, skip_installed_check: bool = False) -> None:
    """Run every step in order, stopping at the first failure.

    Args:
        version: The expected version of the installed package.
        skip_installed_check: Do not require the package to be in the environment's ``purelib`` folder.

    Raises:
        SmokeFailure: At the first failing step.
    """
    package_dir = package_directory()
    steps: list[Callable[[], None]] = []
    if not skip_installed_check:
        steps.append(lambda: check_installed(package_dir))
    steps += [
        lambda: check_version(version, package_dir),
        lambda: check_package_data(package_dir),
        lambda: check_examples(EXPECTED_STORY_IDS, package_dir),
        lambda: check_gallery(EXPECTED_STORY_IDS),
        check_pytest_plugin,
    ]
    for step in steps:
        step()


def main(argv: Sequence[str] | None = None) -> int:
    """Run the checks from the command line and return the exit code."""
    parser = argparse.ArgumentParser(description="Check an installed pyside6-storybook.")
    parser.add_argument("version", help="the version the installed package must report")
    parser.add_argument("--skip-installed-check", action="store_true", help="do not require the package to be installed in site-packages")
    arguments = parser.parse_args(argv)
    try:
        run_checks(arguments.version, skip_installed_check=arguments.skip_installed_check)
    except SmokeFailure as failure:
        print(f"FAILED: {failure}", file=sys.stderr)
        return 1
    print(f"All smoke checks passed for pyside6-storybook {arguments.version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

import importlib.metadata
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import smoke_check

import pyside6_storybook
from pyside6_storybook import StoryRegistry, load_stories
from pyside6_storybook.cli import EXAMPLES_MODULE

_SCRIPT = Path(smoke_check.__file__).resolve()


@pytest.fixture
def package_copy(tmp_path: Path) -> Path:
    """A copy of the package under test, in a folder of its own."""
    source = Path(pyside6_storybook.__file__).resolve().parent
    target = tmp_path / "site" / "pyside6_storybook"
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__"))
    return target


def test_the_expected_ids_are_the_ids_of_the_examples(stories: StoryRegistry) -> None:
    result = load_stories([EXAMPLES_MODULE])
    assert result.errors == ()
    assert smoke_check.EXPECTED_STORY_IDS == frozenset(result.registry.ids())
    assert len(smoke_check.EXPECTED_STORY_IDS) == len(result.registry.ids())


def test_the_package_data_check_passes_for_an_intact_copy(package_copy: Path) -> None:
    smoke_check.check_package_data(package_copy)


def test_the_package_data_check_fails_without_py_typed(package_copy: Path) -> None:
    (package_copy / "py.typed").unlink()

    with pytest.raises(smoke_check.SmokeFailure, match=r"py\.typed"):
        smoke_check.check_package_data(package_copy)


def test_the_package_data_check_fails_without_the_licence(package_copy: Path) -> None:
    (package_copy / "resources" / "icons" / "licenses" / "phosphor-LICENSE.txt").unlink()

    with pytest.raises(smoke_check.SmokeFailure, match="phosphor-LICENSE"):
        smoke_check.check_package_data(package_copy)


def test_the_examples_check_fails_without_the_examples_package(package_copy: Path) -> None:
    shutil.rmtree(package_copy / "examples")

    with pytest.raises(smoke_check.SmokeFailure):
        smoke_check.check_examples(smoke_check.EXPECTED_STORY_IDS, package_copy)


def test_the_examples_check_fails_for_other_ids() -> None:
    package_dir = smoke_check.package_directory()

    with pytest.raises(smoke_check.SmokeFailure, match="not the expected stories"):
        smoke_check.check_examples(smoke_check.EXPECTED_STORY_IDS - {"Display/Label"}, package_dir)


def test_the_debug_info_check_fails_for_another_version() -> None:
    package_dir = smoke_check.package_directory()

    with pytest.raises(smoke_check.SmokeFailure, match=r"expected 'pyside6-storybook: 0\.0\.0' first"):
        smoke_check.check_debug_info("0.0.0", package_dir)


def test_the_installed_check_rejects_a_package_outside_the_site_packages(tmp_path: Path) -> None:
    with pytest.raises(smoke_check.SmokeFailure, match="not from"):
        smoke_check.check_installed(smoke_check.package_directory(), tmp_path)


def test_the_installed_check_accepts_a_package_inside_the_site_packages(tmp_path: Path) -> None:
    smoke_check.check_installed(tmp_path / "pyside6_storybook", tmp_path)


@pytest.mark.full
@pytest.mark.timeout(600)
def test_the_script_passes_against_the_development_install(tmp_path: Path) -> None:
    version = importlib.metadata.version("pyside6-storybook")

    completed = subprocess.run(
        [sys.executable, "-I", str(_SCRIPT), version, "--skip-installed-check"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    for line in (
        f"ok: __version__ is {version}",
        f"ok: `pyside6-storybook --debug-info` reports {version}",
        "ok: py.typed is present",
        "ok: the Phosphor licence is present",
        "ok: the 20 example ids are the expected ones",
        "ok: the gallery shows all 20 stories in the Light theme",
        "ok: the gallery shows all 20 stories in the Dark theme",
        "ok: the pytest plugin runs the examples (40 passed)",
    ):
        assert line in completed.stdout

import re
import shutil
import subprocess
import sys
import tarfile
import tomllib
import zipfile
from collections.abc import Iterator
from email.parser import Parser
from pathlib import Path

import pytest
import yaml
from PySide6.QtWidgets import QApplication

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PYPROJECT = _REPO_ROOT / "pyproject.toml"
_FULL_TESTS_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "full-tests.yml"


def _project() -> dict:
    return tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))["project"]


def _minor(version: str) -> tuple[int, int]:
    major, minor = version.split(".")[:2]
    return int(major), int(minor)


def test_the_python_classifiers_run_from_requires_python_to_the_newest_version_in_the_full_test_matrix() -> None:
    if not _FULL_TESTS_WORKFLOW.is_file():
        pytest.skip(".github/workflows/full-tests.yml is not part of this source tree")

    project = _project()
    match = re.fullmatch(r">=\s*(\d+\.\d+)", project["requires-python"])
    assert match is not None, project["requires-python"]
    oldest = _minor(match.group(1))
    workflow = yaml.safe_load(_FULL_TESTS_WORKFLOW.read_text(encoding="utf-8"))
    matrices = [job.get("strategy", {}).get("matrix", {}) for job in workflow["jobs"].values()]
    matrix_versions = [_minor(str(version)) for matrix in matrices for version in matrix.get("python-version", [])]
    assert matrix_versions
    newest = max(matrix_versions)

    expected = {f"Programming Language :: Python :: {oldest[0]}.{minor}" for minor in range(oldest[1], newest[1] + 1)}
    declared = {c for c in project["classifiers"] if re.fullmatch(r"Programming Language :: Python :: \d+\.\d+", c)}
    assert declared == expected


def test_the_metadata_has_no_license_classifier_and_no_personal_author_address() -> None:
    project = _project()

    assert not [c for c in project["classifiers"] if c.startswith("License ::")]
    assert project["authors"] == [{"name": "Youth Research Center"}]
    assert all("email" not in author for author in project["authors"])


@pytest.fixture(scope="module")
def built_distributions(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build the sdist and, from it, the wheel once for the module."""
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv is not installed")
    out_dir = tmp_path_factory.mktemp("dist")
    result = subprocess.run([uv, "build", "--out-dir", str(out_dir)], cwd=_REPO_ROOT, capture_output=True, text=True, timeout=600, check=False)
    assert result.returncode == 0, result.stderr
    return out_dir


def _sdist_names(dist_dir: Path) -> Iterator[str]:
    (sdist,) = dist_dir.glob("*.tar.gz")
    prefix = sdist.name.removesuffix(".tar.gz") + "/"
    with tarfile.open(sdist) as archive:
        for name in archive.getnames():
            yield name.removeprefix(prefix)


@pytest.mark.full
def test_the_sdist_contains_the_package_the_tests_and_the_licence_and_leaves_out_the_rest(built_distributions: Path) -> None:
    names = list(_sdist_names(built_distributions))

    assert "LICENSE" in names
    assert "THIRD_PARTY_NOTICES.md" in names
    assert "pyproject.toml" in names
    assert "src/pyside6_storybook/__init__.py" in names
    assert "src/pyside6_storybook/py.typed" in names
    assert "tests/test_packaging.py" in names
    assert ".github/workflows/tests.yml" in names
    assert ".github/dependabot.yml" not in names
    assert not [name for name in names if name.startswith((".venv/", "site/", "docs/specs/", "dist/", ".icon-cache/"))]
    assert not [name for name in names if "__pycache__" in name]


@pytest.mark.full
def test_the_wheel_contains_py_typed_stories_and_both_licence_files_and_no_tests_scripts_docs_or_workflows(built_distributions: Path) -> None:
    (wheel,) = built_distributions.glob("*.whl")
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()

    assert "pyside6_storybook/py.typed" in names
    assert [name for name in names if name.endswith("_stories.py")]
    licenses = [name for name in names if ".dist-info/licenses/" in name]
    assert sorted(name.rsplit("/", 1)[1] for name in licenses) == ["LICENSE", "THIRD_PARTY_NOTICES.md"]
    assert not [name for name in names if name.startswith(("tests/", "scripts/", "docs/", ".github/"))]


@pytest.mark.full
def test_the_wheel_metadata_has_the_licence_expression_the_urls_and_the_classifiers(built_distributions: Path) -> None:
    (wheel,) = built_distributions.glob("*.whl")
    with zipfile.ZipFile(wheel) as archive:
        (metadata_name,) = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        metadata = Parser().parsestr(archive.read(metadata_name).decode("utf-8"))

    assert metadata["License-Expression"] == "MIT"
    urls = metadata.get_all("Project-URL") or []
    assert sorted(url.split(", ")[0] for url in urls) == ["Changelog", "Documentation", "Homepage", "Issues", "Repository"]
    declared = _project()["urls"]
    assert {url.split(", ")[0]: url.split(", ")[1] for url in urls} == declared
    classifiers = metadata.get_all("Classifier") or []
    assert set(classifiers) == set(_project()["classifiers"])
    assert not [c for c in classifiers if c.startswith("License ::")]


@pytest.mark.full
def test_the_unpacked_sdist_collects_the_core_tests_without_errors(built_distributions: Path, tmp_path: Path) -> None:
    (sdist,) = built_distributions.glob("*.tar.gz")
    with tarfile.open(sdist) as archive:
        archive.extractall(tmp_path, filter="data")
    (root,) = [path for path in tmp_path.iterdir() if path.is_dir()]

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-m", "not full", "-p", "no:cacheprovider"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )

    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-2000:]


@pytest.mark.full
def test_the_wheel_contains_the_icon_bundle_and_licence_and_no_build_scripts(tmp_path: Path) -> None:
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv is not installed")

    result = subprocess.run(
        [uv, "build", "--wheel", "--out-dir", str(tmp_path)], cwd=_REPO_ROOT, capture_output=True, text=True, timeout=300, check=False
    )
    assert result.returncode == 0, result.stderr

    (wheel,) = tmp_path.glob("*.whl")
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
    assert "pyside6_storybook/resources/icons/icon_bundle.json" in names
    assert "pyside6_storybook/resources/icons/icon_manifest.toml" in names
    assert "pyside6_storybook/resources/icons/licenses/phosphor-LICENSE.txt" in names
    assert not [name for name in names if name.startswith("scripts/") or "/scripts/" in name or "icon_bundle/" in name]


@pytest.mark.full
def test_the_wheel_ships_the_pytest_plugin_module_and_registers_it_as_a_pytest_plugin(tmp_path: Path) -> None:
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv is not installed")

    result = subprocess.run(
        [uv, "build", "--wheel", "--out-dir", str(tmp_path)], cwd=_REPO_ROOT, capture_output=True, text=True, timeout=300, check=False
    )
    assert result.returncode == 0, result.stderr

    (wheel,) = tmp_path.glob("*.whl")
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        (entry_points_name,) = [name for name in names if name.endswith(".dist-info/entry_points.txt")]
        entry_points = archive.read(entry_points_name).decode("utf-8")
        (metadata_name,) = [name for name in names if name.endswith(".dist-info/METADATA")]
        metadata = archive.read(metadata_name).decode("utf-8")
    assert "pyside6_storybook_pytest.py" in names
    assert "pyside6_storybook/testing/storybook_session.py" in names
    assert "[pytest11]\npyside6_storybook = pyside6_storybook_pytest\n" in entry_points
    assert "Provides-Extra: pytest" in metadata
    assert re.search(r"Requires-Dist: pytest-qt>=4.4; extra == ['\"]pytest['\"]", metadata)


def test_the_installed_pyside6_keeps_its_reference_to_none_on_calls_that_return_nothing(qapp: QApplication) -> None:
    # PySide6 6.12.0 on Python 3.11 drops a reference to None on each such call, so a long session frees None and the interpreter aborts
    # ("none_dealloc") on exit. pyproject.toml excludes that combination. On Python 3.12 and newer None is immortal and the count is fixed.
    style_sheet = qapp.styleSheet()
    before = sys.getrefcount(None)
    for _ in range(200):
        qapp.setStyleSheet(style_sheet)
        qapp.processEvents()

    assert sys.getrefcount(None) >= before - 20

"""RELEASING.md names files, environments and a command; they must be the ones the release workflow uses."""

import re
from pathlib import Path

import pytest
import release_target
import yaml

_ROOT = Path(__file__).resolve().parents[1]
_RELEASING = _ROOT / "RELEASING.md"
_RELEASE = _ROOT / ".github" / "workflows" / "release.yml"

pytestmark = pytest.mark.skipif(
    not _RELEASING.is_file() or not _RELEASE.is_file(), reason="RELEASING.md and release.yml are not both part of this source tree"
)


def _text() -> str:
    return _RELEASING.read_text(encoding="utf-8")


def test_every_workflow_and_script_that_the_guide_names_exists() -> None:
    names = set(re.findall(r"(?:\.github/workflows|scripts/[a-z]+)/[A-Za-z0-9_.-]+\.(?:yml|py)", _text()))

    assert {".github/workflows/package.yml", ".github/workflows/release.yml", "scripts/release/release_target.py"} <= names
    for name in names:
        assert (_ROOT / name).is_file(), name
    for workflow in re.findall(r"`([a-z-]+\.yml)`", _text()):
        assert (_ROOT / ".github" / "workflows" / workflow).is_file(), workflow


def test_the_environments_in_the_guide_are_the_ones_the_workflow_uses() -> None:
    workflow = yaml.safe_load(_RELEASE.read_text(encoding="utf-8"))
    assert workflow["jobs"]["publish"]["environment"]["name"] == "${{ needs.target.outputs.repository }}"
    environments = set(release_target.INDEXES)

    text = _text()
    section = text.split("### GitHub environments", 1)[1].split("###", 1)[0]
    named = set(re.findall(r"^- \*\*`([a-z]+)`:\*\*", section, flags=re.MULTILINE))
    assert named == environments
    table = set(re.findall(r"^\| [^|]+ \| [^|]+ \| `([a-z]+)` \|$", text, flags=re.MULTILINE))
    assert table == environments
    assert set(re.findall(r"`(\w*pypi)`", text)) == environments


def _verify_install_command() -> str:
    workflow = yaml.safe_load(_RELEASE.read_text(encoding="utf-8"))
    (install,) = [step["run"] for step in workflow["jobs"]["verify"]["steps"] if step.get("name") == "Install the published version"]
    return " ".join(install.replace("\\\n", " ").split())


def test_the_testpypi_install_command_is_the_two_step_command_of_the_workflow() -> None:
    guide = " ".join(_text().replace("\\\n", " ").split())
    workflow = _verify_install_command()

    assert "pip download --no-deps --only-binary :all: --index-url https://test.pypi.org/simple/ --dest testpypi" in guide
    assert "pip download --no-cache-dir --no-deps --only-binary :all: --index-url" in workflow
    assert release_target.INDEXES["testpypi"][0] == "https://test.pypi.org/simple/"
    assert 'pip install "testpypi/<wheel file name>[pytest]"' in guide
    assert '[pytest]"' in workflow
    assert "PySide6" not in guide.split("A release candidate", 1)[1].split("The release", 1)[0]


def test_the_guide_gives_the_trusted_publisher_values_of_the_project() -> None:
    text = _text()
    workflow = yaml.safe_load(_RELEASE.read_text(encoding="utf-8"))
    pyproject = (_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "| Workflow name | `release.yml` | `release.yml` |" in text
    assert workflow["name"] == "Release"
    assert "Actions → Release → Run workflow" in text
    assert 'name = "pyside6-storybook"' in pyproject
    assert "`Youth-Research-Center`" in text

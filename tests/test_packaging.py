import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

_REPO_ROOT = Path(__file__).resolve().parent.parent


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


def test_the_installed_pyside6_keeps_its_reference_to_none_on_calls_that_return_nothing(qapp: QApplication) -> None:
    # PySide6 6.12.0 on Python 3.11 drops a reference to None on each such call, so a long session frees None and the interpreter aborts
    # ("none_dealloc") on exit. pyproject.toml excludes that combination. On Python 3.12 and newer None is immortal and the count is fixed.
    style_sheet = qapp.styleSheet()
    before = sys.getrefcount(None)
    for _ in range(200):
        qapp.setStyleSheet(style_sheet)
        qapp.processEvents()

    assert sys.getrefcount(None) >= before - 20

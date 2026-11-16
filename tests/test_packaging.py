import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

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

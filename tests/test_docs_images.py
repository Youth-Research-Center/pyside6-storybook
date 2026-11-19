"""The script that renders the docs pages' images writes every image the pages show."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from PySide6.QtGui import QImage

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _ROOT / "scripts" / "docs" / "render_docs_images.py"
_CONTROL_TYPES = ("text", "bool", "choice", "int", "float", "color", "enum", "file")

pytestmark = pytest.mark.skipif(not _SCRIPT.is_file(), reason="scripts/ is not part of this source tree")


@pytest.mark.full
def test_the_script_renders_the_gallery_and_one_image_per_control_type(tmp_path: Path) -> None:
    environment = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    environment.pop("QT_SCALE_FACTOR", None)

    completed = subprocess.run(
        [sys.executable, str(_SCRIPT), "--output", str(tmp_path)],
        env=environment,
        capture_output=True,
        text=True,
        timeout=100,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    expected = {"gallery.png": (800, 4000, 500, 3000)}
    expected.update({f"controls/{name}.png": (150, 1500, 30, 300) for name in _CONTROL_TYPES})
    assert sorted(str(path.relative_to(tmp_path).as_posix()) for path in tmp_path.rglob("*.png")) == sorted(expected)
    for name, (min_width, max_width, min_height, max_height) in expected.items():
        image = QImage(str(tmp_path / name))
        assert not image.isNull(), name
        assert min_width <= image.width() <= max_width, (name, image.width())
        assert min_height <= image.height() <= max_height, (name, image.height())

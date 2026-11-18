"""Tests for ``scripts/icons``: the manifest, the SVG clean-up, the download and cache, the bundle and the command line. No network."""

import base64
import hashlib
import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest
from icon_bundle.bundle import build_bundle, dump_bundle
from icon_bundle.cli import ICONS_DIR, MANIFEST_PATH, REPO_ROOT, run
from icon_bundle.fetch import fetch_tarball, tarball_url
from icon_bundle.manifest import Source, load_manifest
from icon_bundle.notices import render_notices
from icon_bundle.svg import sanitize_svg

PHOSPHOR_LICENSE = "MIT License\n\nCopyright (c) 2023 Phosphor Icons\n\nPermission is hereby granted...\n"
FOLDER_SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256"><!-- c --><path d="M0 0h8v8z"/></svg>'
STROKE_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" '
    'stroke="currentColor"><path d="m8 3 4 8"/></svg>'
)
_LAUNCHER = REPO_ROOT / "scripts" / "icons" / "build_icon_bundle.py"


def make_tarball(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, text in files.items():
            payload = text.encode("utf-8")
            info = tarfile.TarInfo(f"package/{name}")
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
    return buffer.getvalue()


def integrity_of(data: bytes) -> str:
    return "sha512-" + base64.b64encode(hashlib.sha512(data).digest()).decode("ascii")


PHOSPHOR_TAR = make_tarball(
    {
        "LICENSE": PHOSPHOR_LICENSE,
        "assets/regular/folder.svg": FOLDER_SVG,
        "assets/bold/folder-bold.svg": FOLDER_SVG,
        "assets/regular/mountains.svg": FOLDER_SVG,
        "assets/bold/mountains-bold.svg": FOLDER_SVG,
    }
)


def write_manifest(tmp_path: Path, *, weights: str = '["regular"]', icons: str = '["folder"]') -> Path:
    text = f"""
weights = {weights}
icons = {icons}

[sources.phosphor]
package = "@phosphor-icons/core"
title = "Phosphor Icons"
version = "2.1.1"
integrity = "{integrity_of(PHOSPHOR_TAR)}"
license = "MIT"
"""
    path = tmp_path / "icon_manifest.toml"
    path.write_text(text, encoding="utf-8")
    return path


def fake_fetch(source: Source) -> bytes:
    return {"phosphor": PHOSPHOR_TAR}[source.name]


def make_source(data: bytes = PHOSPHOR_TAR) -> Source:
    return Source(
        name="phosphor", package="@phosphor-icons/core", title="Phosphor Icons", version="2.1.1", integrity=integrity_of(data), license="MIT"
    )


def test_load_manifest_reads_sources_and_icons(tmp_path: Path) -> None:
    manifest = load_manifest(write_manifest(tmp_path, icons='["folder", "mountains"]'))

    assert manifest.weights == ("regular",)
    assert manifest.icons == ("folder", "mountains")
    assert manifest.sources["phosphor"].package == "@phosphor-icons/core"


def test_load_manifest_rejects_unknown_weight(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="weight"):
        load_manifest(write_manifest(tmp_path, weights='["regular", "chunky"]'))


def test_load_manifest_rejects_duplicate_icons(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Duplicate"):
        load_manifest(write_manifest(tmp_path, icons='["folder", "folder"]'))


def test_load_manifest_rejects_invalid_icon_names(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Invalid icon name"):
        load_manifest(write_manifest(tmp_path, icons='["Folder"]'))


def test_load_manifest_rejects_a_source_without_a_layout(tmp_path: Path) -> None:
    path = write_manifest(tmp_path)
    path.write_text(path.read_text(encoding="utf-8") + '\n[sources.lucide]\npackage = "x"\ntitle = "x"\nversion = "1"\n'
                    'integrity = "sha512-x"\nlicense = "ISC"\n', encoding="utf-8")

    with pytest.raises(ValueError, match="lucide"):
        load_manifest(path)


def test_the_committed_manifest_pins_phosphor_2_1_1() -> None:
    manifest = load_manifest(MANIFEST_PATH)

    assert manifest.sources["phosphor"].package == "@phosphor-icons/core"
    assert manifest.sources["phosphor"].version == "2.1.1"
    assert manifest.sources["phosphor"].integrity.startswith("sha512-")
    assert manifest.weights == ("regular",)


def test_sanitize_svg_strips_comments_and_root_size_and_adds_current_color() -> None:
    raw = b'<svg xmlns="x" width="256" height="256" viewBox="0 0 256 256"><!-- c --><path d="M0 0"/></svg>'

    svg = sanitize_svg(raw, label="folder")

    assert "<!--" not in svg
    assert 'width="256"' not in svg
    assert 'fill="currentColor"' in svg
    assert 'viewBox="0 0 256 256"' in svg


def test_sanitize_svg_keeps_stroke_icons_untouched() -> None:
    svg = sanitize_svg(STROKE_SVG.encode(), label="stroke")

    assert 'stroke="currentColor"' in svg
    assert svg.count("currentColor") == 1


def test_sanitize_svg_rejects_non_svg() -> None:
    with pytest.raises(ValueError, match="not an SVG"):
        sanitize_svg(b"<html></html>", label="folder")


def test_sanitize_svg_rejects_icons_that_cannot_be_tinted() -> None:
    with pytest.raises(ValueError, match="currentColor"):
        sanitize_svg(b'<svg viewBox="0 0 1 1" fill="#000000"><path d="M0 0"/></svg>', label="folder")


def test_tarball_url_handles_scoped_packages() -> None:
    assert tarball_url(make_source()) == "https://registry.npmjs.org/@phosphor-icons/core/-/core-2.1.1.tgz"


def test_fetch_tarball_downloads_verifies_and_caches(tmp_path: Path) -> None:
    calls: list[str] = []

    def opener(url: str, timeout: int) -> io.BytesIO:
        calls.append(url)
        return io.BytesIO(PHOSPHOR_TAR)

    source = make_source()

    first = fetch_tarball(source, tmp_path, opener=opener)
    second = fetch_tarball(source, tmp_path, opener=opener)

    assert first == second == PHOSPHOR_TAR
    assert len(calls) == 1


def test_fetch_tarball_rejects_a_download_that_fails_the_integrity_check(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Integrity mismatch"):
        fetch_tarball(make_source(), tmp_path, opener=lambda url, timeout: io.BytesIO(b"tampered"))

    assert list(tmp_path.iterdir()) == []


def test_fetch_tarball_refetches_when_the_cache_is_corrupt(tmp_path: Path) -> None:
    source = make_source()
    fetch_tarball(source, tmp_path, opener=lambda url, timeout: io.BytesIO(PHOSPHOR_TAR))
    next(tmp_path.iterdir()).write_bytes(b"corrupt")
    calls: list[str] = []

    def opener(url: str, timeout: int) -> io.BytesIO:
        calls.append(url)
        return io.BytesIO(PHOSPHOR_TAR)

    assert fetch_tarball(source, tmp_path, opener=opener) == PHOSPHOR_TAR
    assert len(calls) == 1


def test_build_bundle_collects_every_weight_and_the_licence(tmp_path: Path) -> None:
    manifest = load_manifest(write_manifest(tmp_path, weights='["regular", "bold"]'))

    bundle = build_bundle(manifest, fake_fetch)

    folder = bundle.data["icons"]["folder"]
    assert folder["source"] == "phosphor"
    assert set(folder["weights"]) == {"regular", "bold"}
    assert "<!--" not in folder["weights"]["regular"]
    assert bundle.data["sources"]["phosphor"] == {
        "package": "@phosphor-icons/core", "title": "Phosphor Icons", "version": "2.1.1", "license": "MIT",
    }
    assert bundle.licenses["phosphor"] == PHOSPHOR_LICENSE


def test_build_bundle_reports_all_missing_icons_at_once(tmp_path: Path) -> None:
    manifest = load_manifest(write_manifest(tmp_path, icons='["folder", "nope", "also-nope"]'))

    with pytest.raises(ValueError) as error:
        build_bundle(manifest, fake_fetch)

    assert "nope" in str(error.value) and "also-nope" in str(error.value)


def test_build_bundle_normalises_licence_line_endings(tmp_path: Path) -> None:
    crlf_tar = make_tarball({"LICENSE": "MIT License\r\nCopyright (c) 2023 X\r\n", "assets/regular/folder.svg": FOLDER_SVG})

    bundle = build_bundle(load_manifest(write_manifest(tmp_path)), lambda source: crlf_tar)

    assert "\r" not in bundle.licenses["phosphor"]


def test_render_notices_names_this_project_and_lists_copyright_and_icons(tmp_path: Path) -> None:
    bundle = build_bundle(load_manifest(write_manifest(tmp_path, icons='["folder", "mountains"]')), fake_fetch)

    notices = render_notices(bundle.data, bundle.licenses)

    assert "Phosphor Icons 2.1.1" in notices
    assert "Copyright (c) 2023 Phosphor Icons" in notices
    assert "folder" in notices and "mountains" in notices
    assert "`pyside6_storybook/resources/icons/licenses/phosphor-LICENSE.txt`" in notices
    assert "src/pyside6_storybook" not in notices
    assert "pyside6-storybook" in notices
    assert "pandaplot" not in notices.lower()


def test_dump_bundle_is_deterministic_json(tmp_path: Path) -> None:
    bundle = build_bundle(load_manifest(write_manifest(tmp_path)), fake_fetch)

    text = dump_bundle(bundle.data)

    assert text == dump_bundle(json.loads(text))
    assert text.endswith("\n")


def test_run_writes_the_outputs_and_check_passes_on_fresh_output_and_fails_on_drift(tmp_path: Path) -> None:
    manifest_path = write_manifest(tmp_path)
    icons_dir = tmp_path / "icons"
    notices = tmp_path / "NOTICES.md"
    kwargs = {"icons_dir": icons_dir, "notices_path": notices, "fetch": fake_fetch}

    assert run(manifest_path, check=False, **kwargs) == 0
    assert (icons_dir / "icon_bundle.json").is_file()
    assert (icons_dir / "licenses" / "phosphor-LICENSE.txt").read_text(encoding="utf-8") == PHOSPHOR_LICENSE
    assert notices.is_file()
    assert run(manifest_path, check=True, **kwargs) == 0

    (icons_dir / "icon_bundle.json").write_text("{}", encoding="utf-8")
    assert run(manifest_path, check=True, **kwargs) == 1


def test_check_fails_on_a_changed_licence_file_and_on_stale_notices(tmp_path: Path) -> None:
    manifest_path = write_manifest(tmp_path)
    icons_dir = tmp_path / "icons"
    kwargs = {"icons_dir": icons_dir, "notices_path": tmp_path / "NOTICES.md", "fetch": fake_fetch}
    assert run(manifest_path, check=False, **kwargs) == 0

    licence = icons_dir / "licenses" / "phosphor-LICENSE.txt"
    licence.write_text("changed", encoding="utf-8")
    assert run(manifest_path, check=True, **kwargs) == 1

    assert run(manifest_path, check=False, **kwargs) == 0
    (tmp_path / "NOTICES.md").write_text("stale", encoding="utf-8")
    assert run(manifest_path, check=True, **kwargs) == 1


def test_check_fails_on_a_stale_licence_file_of_a_source_no_longer_used(tmp_path: Path) -> None:
    manifest_path = write_manifest(tmp_path)
    icons_dir = tmp_path / "icons"
    (icons_dir / "licenses").mkdir(parents=True)
    stale = icons_dir / "licenses" / "other-LICENSE.txt"
    stale.write_text("old", encoding="utf-8")
    kwargs = {"icons_dir": icons_dir, "notices_path": tmp_path / "N.md", "fetch": fake_fetch}

    assert run(manifest_path, check=True, **kwargs) == 1
    assert run(manifest_path, check=False, **kwargs) == 0

    assert not stale.exists()


def test_the_repository_root_and_icons_directory_resolve_inside_this_repository() -> None:
    assert (REPO_ROOT / "pyproject.toml").is_file()
    assert (REPO_ROOT / "scripts" / "icons" / "icon_bundle").is_dir()
    assert ICONS_DIR == REPO_ROOT / "src" / "pyside6_storybook" / "resources" / "icons"
    assert MANIFEST_PATH.is_file()


def test_the_launcher_runs_in_isolated_mode_without_the_script_directory_on_sys_path() -> None:
    result = subprocess.run([sys.executable, "-I", str(_LAUNCHER), "--help"], capture_output=True, text=True, timeout=60, check=False)

    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout
    assert "--check" in result.stdout

"""Helpers for tests that write story modules to disk and load them."""

from __future__ import annotations

import textwrap
from pathlib import Path


def write(root: Path, relative: str, source: str = "") -> Path:
    """Write ``source`` (dedented) to ``root / relative``, creating folders, and return the path."""
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(source), encoding="utf-8")
    return path


def story_source(story_id: str, text: str = "x", *, imports: str = "") -> str:
    """Return the source of a story module that registers ``story_id`` as a ``QLabel`` showing the expression ``text``."""
    return f"""
from PySide6.QtWidgets import QLabel

from pyside6_storybook import story
{imports}

@story({story_id!r})
def build(ctx):
    return QLabel({text})
"""

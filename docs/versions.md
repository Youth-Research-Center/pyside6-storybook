# Versions and compatibility

pyside6-storybook follows [Semantic Versioning](https://semver.org/). Every release and what changed in it is in the
[Changelog](changelog.md).

## Version numbers

Before 1.0:

- a minor release (0.x.0) may break the public API. It says so under `### Breaking`, the first heading of its changelog section;
- a patch release (0.x.y) never breaks the public API. It carries fixes only.

A release candidate (`0.x.0rc1`) is published to PyPI before the release itself. pip ignores pre-releases unless you ask for one
with `pip install --pre`, so a candidate never reaches a user by accident.

## The public API

The public API is:

- the names in `__all__` of `pyside6_storybook` and of `pyside6_storybook.checks`;
- the options and exit codes of the `pyside6-storybook` command line;
- the keys of `[tool.pyside6-storybook]` in `pyproject.toml` and the `pyside6_storybook.stories` entry-point group;
- the options and ini keys of the pytest plugin, its test item ids and the `render_story` fixture;
- the `sbk` object names and the `sbkChrome` property that style the gallery.

Everything else is internal and may change in any release: the modules under `gui/`, `testing/` and `discovery/`, the gallery's look,
and the text of messages. Do not import from them, and do not match on message text.

## Supported versions

- **Python:** 3.11 up to the newest version the project's CI tests. Support for a Python version ends in a minor release after that
  version's end of life.
- **PySide6:** 6.8 and newer. CI tests 6.8.0, in the job that installs the lowest allowed dependencies, and the newest release. The
  minimum rises only in a minor release. A PySide6 release that is known to be broken is excluded in `pyproject.toml`, with a comment.

## Patch releases

A patch release is made on a branch `release/X.Y.x`, cut from the tag `vX.Y.0`. A fix is made on `main` first and cherry-picked onto
that branch, so a patch never carries the breaking changes of `main`.

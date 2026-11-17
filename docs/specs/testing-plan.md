# Testing (milestone 5): implementation plan

Status: draft. Implements `docs/specs/testing.md` (the spec) in four stacked pull requests. Section numbers (§1) refer to the spec.

## Order, branches and merging

| # | Issue | Branch | Base |
| --- | --- | --- | --- |
| 1 | #32 pytest plugin | `claude/pyside6-storybook-pytest-plugin` | `main` |
| 2 | #34 names and focus | `claude/pyside6-storybook-a11y-checks` | PR 1 |
| 3 | #35 text contrast | `claude/pyside6-storybook-contrast-check` | PR 2 |
| 4 | #33 snapshots | `claude/pyside6-storybook-snapshots` | PR 3 |

Every PR description asks for "Create a merge commit" and says "Stacked on #N; merge the stack bottom-up, retargeting each PR to `main`
before merging it". The spec PR merges independently.

## Process per PR

1. A Sonnet subagent implements the PR in its own git worktree, following the spec, this plan, `AGENTS.md`, `CLAUDE.md` and
   `/tmp/claude-0/specs5/common.md`, and commits without pushing. It pastes the last line of `ruff check` and `ty check` into its
   report.
2. I review the diff, rerun every check and fix what review finds, with a regression test for each fix:
   - `build_icon_bundle.py --check`, ruff, the W291/W292/W293 check and `ty`;
   - pytest with the default font and with DejaVu Sans, the oldest-dependencies run on Python 3.11, and a Python 3.14 run.
3. I push, open a draft PR, and start the Full test suite on the branch when the PR touches platform-dependent behaviour.

**Review checklist**
- **Start-up cost:** the plugin imports nothing from Qt or `pyside6_storybook` until it is enabled.
- **Cleanup:** every item restores the application's look and deletes what it rendered, and `-p no:cacheprovider` and `-n 2` work.
- **Story code:** failures in story code show the story's traceback, not the plugin's internals.
- **Public API:** new public names are in the changelog. The package root's `__all__` is unchanged unless the spec says otherwise.

## Tests across PRs

- Plugin tests use `pytester` (`pytest_plugins = ["pytester"]` in `tests/conftest.py`):
  - **Runs.** Prefer `runpytest_inprocess`; use `runpytest_subprocess` (with `timeout=`) for start-up cost, xdist and anything that
    must not share the `QApplication`.
  - **The project under test.** pytester's project gets its own `pyproject.toml` with `[tool.pyside6-storybook]` and story files
    written with `pytester.makepyfile`, never the repository's examples unless a test is about the examples.
  - **The default registry.** In-process runs share `sys.modules` and the default registry, so each test uses the `stories` fixture,
    or the plugin's fresh-registry loading (§1.3).
- A test that renders the examples in every theme is `full`, per AGENTS.md. One theme pair (Light, Dark) of the examples may be core
  when it is the issue's acceptance run.

## PR 1: pytest plugin (#32), spec §1

**Code**
- `src/pyside6_storybook_pytest.py` (entry module, §1.1): options, ini keys, the `storybook` marker, `pytest_configure` (sources and
  options validated, `UsageError`), `pytest_collection_modifyitems` (`tryfirst=True`), the `pytest_make_collect_report` wrapper,
  `pytest_runtest_teardown` and `pytest_sessionfinish` delegating to the session, and the `render_story` fixture (a thin wrapper).
- `pyproject.toml`:
  - the `pytest11` entry point and the `pytest` extra;
  - hatch `packages` gains `src/pyside6_storybook_pytest.py`;
  - dev dependency `pytest-xdist`;
  - `uv.lock` updated.
- `src/pyside6_storybook/testing/` (internal), as listed in §1.6.
- `src/pyside6_storybook/themes/story_context_factory.py`: `build_story_context`, now used by `gui/window.py` too, with no behaviour
  change in the window: its existing tests keep passing.
- `discovery/sources.py`: `StorySources.fallback` (keyword-only, default `False`), set for the examples fallback. `cli.py` is
  unchanged.

**Tests** (`tests/test_pytest_plugin.py`, `tests/test_storybook_session.py`, and others as needed, one module per source module)
- Everything §1.7 lists.
- The examples run: `--storybook --storybook-stories pyside6_storybook.examples --storybook-themes Light,Dark` passes. The issue's
  acceptance is "one passing test per story and theme".
- `StorySources.fallback` for each source kind.
- The start-up cost test.

**Docs**
- README "Testing stories": enabling, options and ini keys, item ids and selection (`-k`, `--deselect`; nodeids are not paths), the
  `storybook` marker, the `QApplication` note, xdist distribution, and the `render_story` fixture.
- CHANGELOG `### Added`: the plugin and the extra.
- AGENTS.md: structure and test rules.
- `docs/theming.md` and the `ThemeProvider` docstring: a provider can be activated again after `deactivate`.

## PR 2: accessible names and keyboard focus (#34), spec §2

**Code**
- `src/pyside6_storybook/checks/` (public subpackage): `check_issue.py`, `accessibility.py`, and an `__init__.py` re-exporting
  `CheckIssue`, `check_accessible_names` and `check_keyboard_focus`.
- `checks_ignore` on `story()`, `StoryRegistry.story()`, `Story.__init__` and `Story.variant`, plus `Story.checks_ignore`:
  - validated (unknown rule or empty reason raises `ValueError`);
  - stored read-only;
  - inherited by variants.
- Plugin: `--storybook-a11y` and ini `storybook_a11y`, adding the `[a11y-name]` and `[a11y-focus]` items, skipped with the reason
  when ignored.
- Examples: accessible names or buddies for Line Edit (three stories), Spin Box, Double Spin Box, Slider and Table, as §2.4 lists.

**Tests**
- Everything §2.4 lists.
- Each exclusion of §2.1, with a widget that would otherwise fail: header views, the corner button, a line edit's clear button,
  spin box and combo box internals, a tab widget, a scroll area.
- The combo box rule: an unlabelled combo box fails even though its current text is non-empty.
- `tests/test_examples.py`: every example passes both rules.

**Changed tests:** any test that pins the `story()`, `Story` or `Story.variant` signature or attribute list gains `checks_ignore`.

**Docs**
- README: the checks, `checks_ignore`, and the a11y items.
- CHANGELOG `### Added`: `pyside6_storybook.checks` and `checks_ignore`.
- CHANGELOG `### Changed`: the example fixes.

## PR 3: text contrast (#35), spec §3

**Code**
- `checks/contrast.py`: `check_text_contrast`, re-exported from `pyside6_storybook.checks`.
- Plugin items `[<theme>-contrast]`, with the options:
  - `--storybook-no-contrast` and `storybook_contrast`;
  - `storybook_contrast_normal` and `storybook_contrast_large`;
  - `--storybook-contrast-disabled` and `storybook_contrast_disabled`.
- Example Display/Color Swatch: the swatch's text uses `pick_contrasting_text` against the swatch colour, reaching 4.5:1 in both
  themes.

**Tests**
- Everything §3.2 lists, each synthetic case with its measured ratio in the assertion message.
- The one-colour box fails.
- The Color Swatch story reaches 4.5:1 for several swatch colours.

**Docs**
- README: the contrast check, its method and limits.
- CHANGELOG `### Added`, and `### Changed` for the Color Swatch example.

## PR 4: snapshots (#33), spec §4

**Code**
- `testing/snapshots.py`: `capture`, `compare`, `SnapshotDiff` and the diff-image writer.
- Plugin items `[<theme>-snapshot]`, with the options:
  - `--storybook-snapshots` and `--storybook-update-snapshots`;
  - `storybook_snapshot_dir` and `storybook_snapshot_failures`;
  - `storybook_snapshot_tolerance` and `storybook_snapshot_max_diff`.

**Tests**
- Everything §4.3 lists, with pytester. Baselines go in the pytester project; the failures folder is checked for both images.
- `compare` unit tests: equal images, a one-pixel difference within and beyond the tolerance, the share limit, a size mismatch.
- `full`: two renders of the examples are byte-identical.

**Docs**
- README: snapshots and the recommended CI setup, with an example GitHub Actions step that uploads the failures folder.
- CHANGELOG `### Added`.

## After the stack

- The user runs the Full test suite on `main`.
- #32, #33, #34 and #35 close with their PRs.

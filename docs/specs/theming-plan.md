# Theming hook (milestone 4): implementation plan

Status: draft. Implements `docs/specs/theming.md` (the spec) in six stacked pull requests. Section numbers (§1) refer to the spec.

## Order, branches and merging

| # | Issue | Branch | Base |
| --- | --- | --- | --- |
| 1 | #26 provider | `claude/pyside6-storybook-theme-provider` | `main` |
| 2 | #29 chrome styling | `claude/pyside6-storybook-chrome-styling` | PR 1 |
| 3 | #27 tokens | `claude/pyside6-storybook-design-tokens` | PR 2 |
| 4 | #30 System theme | `claude/pyside6-storybook-system-theme` | PR 3 |
| 5 | #28 provider config | `claude/pyside6-storybook-provider-config` | PR 4 |
| 6 | #31 guide and example | `claude/pyside6-storybook-themed-app` | PR 5 |

**Merging**
- Every PR description asks for "Create a merge commit" (§7) and says: "Stacked on #N. Merge the stack bottom-up and retarget this
  PR to `main` before merging it."
- The spec PR merges independently.

## Process per PR

Same as milestone 3:
1. A Sonnet subagent implements the PR on its branch, following the spec, this plan, `AGENTS.md`, `CLAUDE.md` and
   `/tmp/claude-0/specs4/common.md`, and commits without pushing.
2. I review the diff and run every check:
   - `build_icon_bundle.py --check`, ruff, the W291/W292/W293 check and `ty`;
   - both pytest runs, the normal one and the oldest-dependencies one (Python 3.11, `--resolution lowest-direct`).
3. I push and open a draft PR.

Screenshots are taken from the top of the stack in both built-in themes and with the example's provider.

**Review checklist**
- **Provider calls:** every provider call in the window is guarded, and the callback checks `shiboken6.isValid`.
- **The `sbkChrome` property:** it is never set on an ancestor of the preview surface.
- **Global state:** every test restores what it changes: the application palette, style, style sheet and font (the
  `restore_application_look` fixture), plus `default_registry` and `sys.modules` (the `stories` fixture).
- **Public API:** new public names are in `__all__`, in `tests/test_package.py`'s exact set, and in the changelog.
- **Other milestone 3 rules:** keyword-only parameters, owners for every widget, palette roles only, and no weakened assertions.

## PR 1: `ThemeProvider` (#26), spec §1

**Code**
- `themes/provider.py`: the `ThemeProvider` protocol, `@runtime_checkable`.
- `themes/builtin_theme_provider.py`: `BuiltinThemeProvider`, made from `builtin_themes.py` (which is deleted).
  - Protocol method names, the callback list, and synchronous notification in `set_theme`.
  - `deactivate` clears the callbacks and restores the font as well.
  - `BUILTIN_THEME_NAMES` stays, defined in the new module.
- `themes/__init__.py` and the package root export `ThemeProvider` and `BuiltinThemeProvider`. The package root also exports `run`.
- `gui/window.py`:
  - the provider parameter;
  - the switch filled from `theme_names()`;
  - the guarded `set_theme`, `Ctrl+T` and callback (§1);
  - the error panel titled "Theme provider failed: …";
  - `StoryContext(theme=provider.current_theme())` on every render.
- `app.py`: `run(..., theme_provider=None)`, the `theme` validation, the snapshot of style, palette, style sheet and font, and
  the restoration warning.
- `tests/fake_providers.py`:
  - `StyleSheetProvider`, a style sheet plus a palette in two themes ("Paper" and "Ink"), and also sets a font. It is about 30
    lines, as #26's acceptance criterion asks;
  - `RaisingProvider`, whose `set_theme` and `tokens` raise;
  - `LeakyProvider`, which does not restore the font.

**Tests** (`tests/test_theme_provider.py`)
- The protocol accepts `BuiltinThemeProvider` and `StyleSheetProvider`, and rejects an object missing a method.
- Activation; switching through the window's switch and through `Ctrl+T`.
- A provider-initiated change (the fake's `simulate_external_change()`) updates the switch and re-renders.
- Full restoration on `deactivate`, font included.
- `run` warns about `LeakyProvider` (`caplog`).
- `RaisingProvider` shows the error panel and the window stays usable.
- The callbacks are cleared on `deactivate`, and a dead window's callback is harmless.
- `run(theme="Sepia")` raises, listing the names.

**Changed tests**
- **The rename.** `BuiltinThemes` becomes `BuiltinThemeProvider`, `.names` becomes `.theme_names()` and `.current` becomes
  `.current_theme()`. This touches `tests/conftest.py` (the `themes` fixture) and 13 test modules, and is mechanical.
- `tests/test_themes.py` moves to the new module path, with the same assertions.
- `tests/test_package.py` gains `ThemeProvider`, `BuiltinThemeProvider` and `run`.

**Docs**
- README "Themes": the providers, and `run(theme_provider=...)`.
- CHANGELOG `### Added`.
- `AGENTS.md`: the structure, and the "Application-wide changes" rule now names the provider.

## PR 2: chrome under an application style sheet (#29), spec §5

**Code**
- `gui/chrome.py`: `mark_chrome(widget, name, *, chrome=True)`. It sets the object name and, when `chrome` is true, the
  `sbkChrome` property, re-polishing if the widget is already polished. `chrome=False` gives a name only, for the surface's
  ancestors.
- **Every** `setObjectName` in `gui/` goes through `mark_chrome`, with the `sbk` prefix.
  - Internal children get marked explicitly: tab bars, scroll viewports, the tree's viewport.
  - Editors are marked in `ControlEditor`; the error panel and the empty-state label are marked too.
- `gui/sidebar.py`: a `_SelectionDelegate` that samples `PE_PanelItemViewItem` and picks the text colour (§5), with a cache.
- `tests/fixtures/aggressive.qss`, and `AggressiveProvider` in `tests/fake_providers.py`, with two themes.

**Tests** (`tests/test_chrome_styling.py`)
- Under `AggressiveProvider`, in both its themes:
  - sidebar selection text reaches 4.5:1, with the tree focused and unfocused, for both selection forms;
  - control labels and the error panel title reach 4.5:1;
  - no chrome label is clipped at 18 pt.
- `*[sbkChrome="true"]` restyles a chrome button and not a story's button.
- `*[sbkChrome="true"] QPushButton` does not reach a story's button.
- `QPushButton[sbkChrome="true"]` and `#sbkName` overrides work.
- A widget marked after polish picks up a rule.
- The README's list of names matches the names found on a shown window (§5).
- The delegate's cache is hit on a second paint.

**Changed tests:** every object-name lookup moves to its `sbk…` name, about 170 references in 16 modules. This is one mechanical
commit, with no assertion changed.

**Docs**
- README: a "Styling the gallery" section with the name list and the selectors.
- CHANGELOG `### Changed`: the renamed object names.
- `AGENTS.md`: chrome widgets are created through `mark_chrome`, and no widget-local style sheets.
- The two palette-requirement screenshots (§5) are rendered and committed in PR 6, with the guide.

## PR 3: design tokens (#27), spec §2

**Code**
- `StoryContext.tokens`: keyword-only, a read-only copy, `repr=False`.
- `BuiltinThemeProvider.tokens()`, returning the table in §2.
- The window reads tokens after activation and on every notification, guarded, and passes them on each render.
- The `Display/Token Badge` example.

**Tests**
- The tokens reach the story and change with the theme.
- They are read-only and default to empty.
- A provider without `tokens` yields `{}`, and a raising one shows the error and yields `{}`.
- A milestone 1 story (only `ctx.args`) renders unchanged.
- The Token Badge's pixels follow the theme.

**Changed tests:** `tests/test_examples.py` `EXPECTED_IDS` gains `Display/Token Badge`.

**Docs**
- README: tokens in stories, the built-in token table, and the `set_tokens` pattern.
- CHANGELOG `### Added`.

## PR 4: System theme (#30), spec §3

**Code**
- In `BuiltinThemeProvider`:
  - "System", which restores the activation state through `_restore_color_scheme`;
  - `colorSchemeChanged` connected only while System is active, and notifying through `QTimer.singleShot(0, ...)`;
  - `color_scheme()`.
- `StoryContext.color_scheme`, and the window's heuristic for providers without `color_scheme()`.

**Tests**
- With `app.setStyle("Windows")` before `activate`, System restores Windows and the original palette and style sheet.
- Dark reapplies Fusion and the dark palette.
- Light → System → Dark → System leaves no residue.
- An emitted `colorSchemeChanged` re-renders after the event loop runs (`qtbot.waitUntil`).
- `ctx.color_scheme` for each theme, and the heuristic for a provider without `color_scheme()`.
- The signal is disconnected when switching away.

**Changed tests:** any test that asserts the exact theme names: the window switch, `--help`, `test_themes.py`.

**Docs:** README (System, `ctx.color_scheme`, the offscreen limitation), CHANGELOG `### Added`.

## PR 5: choosing a provider (#28), spec §4

**Code**
- `themes/provider_loader.py`: `load_theme_provider(spec) -> LoadedProvider(provider, modules)` and `ThemeProviderError`.
- `discovery/sources.py`: the `theme_provider` and `theme` keys and `StorySources` fields, read also when there are targets.
- `discovery/reload.py`: `ReloadSession(..., keep=())`.
- `cli.py`:
  - `--theme-provider`;
  - `--theme` without `choices`, validated after loading;
  - the provider loaded after `put_on_sys_path` and the `QApplication`;
  - the `--list` line;
  - `keep=` passed to the session;
  - errors printed with exit 1.

**Tests** (`tests/test_provider_loader.py`, `tests/test_cli.py`, `tests/test_sources.py`, `tests/test_reload.py`)
- The loader: an instance, a callable, a class, a dotted attribute.
- Each error message names the spec.
- Resolution order: the command line, then `pyproject.toml`, then built-in.
- Keys are read with targets.
- An unknown theme lists the provider's names.
- The `--list` line.
- `keep=`: the provider module is neither dropped nor watched, and the stories and the provider share the module's singleton
  after a reload.

**Changed tests:** `test_an_unknown_theme_is_a_usage_error` was an argparse error (exit 2). It becomes an error after loading
(exit 1), and the message still names "Sepia" and the valid themes. `_RecordingRun` records `theme_provider`.

**Docs:** README "Command line" and "Where your stories come from" (the new keys), CHANGELOG `### Added`.

## PR 6: guide and worked example (#31), spec §6

**Code and content**
- `examples/themed_app/`, as listed in §6.
- `docs/theming.md`.
- `docs/images/theming-no-palette.png` and `theming-with-palette.png`, rendered by `scripts/docs/render_theming_images.py`
  (development only).
- README links to the guide.

**Tests** (`tests/test_themed_app.py`, §6)
- Core: in-process `--list`, and the stories rendered in both themes.
- `full`: the subprocess `--list`.

**Docs:** CHANGELOG `### Added` (the guide and example), and the `AGENTS.md` structure (`examples/` at the root, `scripts/docs/`).

## After the stack

- The user runs the Full test suite on `main`.
- #26–#31 close with their PRs.

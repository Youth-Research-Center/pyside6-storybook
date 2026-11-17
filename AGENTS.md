# pyside6-storybook - Agent Instructions

Conventions for people and coding agents working in this repository. Tool-specific instruction files import this one; change shared guidance here.

## Project overview
`pyside6-storybook` is a small Storybook-like component explorer for PySide6. A developer writes *stories* (functions that build one
widget in one state) and opens a gallery window to browse them, edit their arguments live and switch themes. The only runtime
dependency is `PySide6-Essentials` (Qt Widgets). The plan and the design decisions are in `docs/roadmap.md`; the issue tracker is the
source of truth for scope.

## Environment
Dependencies and the lockfile are managed with **uv**. Run everything through `uv run`.

```bash
uv sync                  # create .venv with the runtime and dev dependencies
uv add <package>         # add a runtime dependency (the library has exactly one; discuss before adding another)
uv add --dev <package>   # add a development dependency
uv build                 # build the sdist and wheel into dist/ (delete dist/ afterwards)
```

Supported Python: 3.11 and newer. Commit `uv.lock` together with any change to dependencies.

## Running the gallery
```bash
uv run pyside6-storybook path/to/stories            # a folder, a .py file or a dotted module name; several are allowed
uv run pyside6-storybook --examples                 # the built-in example stories (can be combined with targets)
uv run pyside6-storybook --list path/to/stories     # print the story ids and exit, without a window or a display
uv run python -m pyside6_storybook path/to/stories  # the same command line
```
Without a target or `--examples` the command uses the default sources: `[tool.pyside6-storybook]` (`stories`, `pythonpath`,
`theme_provider`, `theme`) in the working directory's `pyproject.toml`, then the `pyside6_storybook.stories` entry points, then the
built-in examples. The README documents the settings.

## Tests
There is no display in CI or in agent sandboxes: set `QT_QPA_PLATFORM=offscreen` for every test run. `tests/conftest.py` also sets it as a
default before Qt is imported.

```bash
QT_QPA_PLATFORM=offscreen uv run pytest -q                    # every test; run this locally before pushing
QT_QPA_PLATFORM=offscreen uv run pytest -q -m "not full"      # only the core tests, as CI runs them on every push
QT_QPA_PLATFORM=offscreen uv run pytest tests/test_window.py
QT_QPA_PLATFORM=offscreen uv run --isolated --python 3.11 --resolution lowest-direct pytest -q   # oldest supported dependencies
```

`pytest-timeout` aborts any test that runs longer than 120 seconds (set in `pyproject.toml`), so a hung Qt test cannot hold a job.

Mark a test `@pytest.mark.full` when it is a slower end-to-end check rather than a test of one behaviour: it runs the installed script
in a subprocess, or renders every example or story in every theme. Everything else is a core test. `--strict-markers` is on, so a
misspelt marker fails instead of silently selecting nothing.

CI runs in two workflows:
- **Tests** (`.github/workflows/tests.yml`), on every push to `main` and every pull request: lint, `ty` and the core tests
  (`-m "not full"`) on Linux with Python 3.11.
- **Full test suite** (`.github/workflows/full-tests.yml`), started by hand (Actions > Full test suite > Run workflow, on any
  branch): every test on Windows, macOS and Linux with Python 3.11 and 3.14, plus the lowest allowed dependency versions. Run it
  before a release, after a dependency or Python bump, and for changes to platform-dependent code (paths, themes, the command line).

## Code quality
Two gates run in CI: `ruff check` (ruff's default rules `E4`, `E7`, `E9` and `F`, plus `E501` for 150-character lines, `B`, `Q`, `I` and
`FBT`; there is no `ruff format` step) and the
[`ty`](https://github.com/astral-sh/ty) type checker, which must report no diagnostics in `src/` or `tests/`. Run both and the tests for
the code you touched before every push. `W` rules are not selected, so check whitespace on the files you changed:

```bash
uv run ruff check .
uv run ruff check --fix .                                  # auto-fix, including import order
uv run ruff check --select W291,W292,W293 <files you changed>
uv run ty check
uv run python scripts/icons/build_icon_bundle.py --check   # fails when the icon bundle, licence or notices are out of date
```

Silence a `ty` diagnostic only where a test misuses the API on purpose (assigning to a frozen field, passing a non-control), with
`# ty: ignore[<rule>]` naming the rule. Fix every other diagnostic. `ty` is pre-1.0, so a version bump can bring new diagnostics; fix them
in the same pull request as the bump.

## Project structure
- `src/pyside6_storybook/` - the package
  - `__init__.py` - the public API (`__all__`) and `__version__`
  - `__main__.py` - `python -m pyside6_storybook`, which runs `cli.main`
  - `cli.py` - the `pyside6-storybook` command line (`main`): loads the targets and opens the gallery, or lists the stories
  - `controls/` - control dataclasses, one module per type (`text_control.py`, `bool_control.py`, `choice_control.py`,
    `int_control.py`, `float_control.py`, `color_control.py`, `enum_control.py`, `file_control.py`); `__init__.py` re-exports them
    and defines the `Control` union, `_range.py` holds the range check shared by the int and float controls, and `_options.py` holds
    the functions every control uses (label derivation, `label`/`description` validation, the float step and decimals rules). Controls
    share no base class: each has `label`, `description`, `display_label` and `coerce`
  - `registry/` - the story model, one module per type:
    - `story_context.py`: `StoryContext` (with `args`, `theme`, `actions`, `tokens` and `color_scheme`), `StoryFunction`, `Decorator`;
    - `story_definition.py`: `Story`, `StoryOrigin`; `Story.variant` registers a variant through the registry link that
      `StoryRegistry.register` sets;
    - `layout.py`: `Layout`, how the preview places a story's widget;
    - `size_preset.py`: `SizePreset`, a named canvas size;
    - `story_registry.py`: `StoryRegistry`, with `default_layout`, `decorators` and `size_presets`;
    - `rendering.py` (internal): `render_story`, which builds a story's widget, applies its decorators and the registry's, and raises
      `StoryRenderError` with the error panel's title and details, deleting every widget it built when it fails;
    - `__init__.py` re-exports them and holds `default_registry` and the `@story` decorator.
  - `decorators/` - the built-in story decorators, one module each: `padding.py`, `frame.py`, `fixed_size.py` (plus `_checks.py`, the
    argument checks they share); `__init__.py` re-exports them and the `Decorator` type, which is defined in `registry/story_context.py`
    because `registry` needs it and defining it here would be an import cycle
  - `discovery/` - story discovery: `loader.py` (`load_stories`, which imports story modules from folders, files and dotted module
    names, and collects errors), `reload.py` (internal, Qt-free: `ReloadSession` and `ReloadResult`, which drop the project's modules,
    load the targets into a fresh registry and accept or roll back the result), `file_search.py` (which files are stories),
    `module_import.py` (importing one file under the module name that keeps it a single module), `load_result.py` (`LoadResult`,
    `LoadError`), `sources.py` (`resolve_story_sources`: the command line's targets or the default sources from `pyproject.toml`, entry
    points or the examples; the `pythonpath`, `theme_provider` and `theme` keys are read in every case) and `constants.py` (file-name
    patterns, names and messages)
  - `gui/` - the gallery's widgets, one module per widget: `window.py` (`GalleryWindow`), `canvas.py` (`Canvas`, the preview scroll area and
    surface with the Background, Size and zoom controls above them, and `CanvasBackground`), `sidebar.py` (`StorySidebar`: the search field
    and the tree of stories, with its filter model), `controls_panel.py` (`ControlsPanel`, the
    labelled form over the editors of a story's controls), `docs_panel.py` (`DocsPanel`, the Docs tab, and `controls_rows`, the pure
    function behind its controls table), `actions_panel.py` (`ActionsPanel`, the Actions tab: the log a story fills through
    `StoryContext.log` and `log_signal`, and the per-render sink that drops entries from an older render) and
    `error_panel.py` (`ErrorPanel`, which the window shows in the preview for a story that fails and for the load errors),
    `reload_watcher.py` (`ReloadWatcher`, a `QFileSystemWatcher` with a 300 ms debounce that runs a `ReloadSession`),
    `reload_status.py` (`ReloadStatus`, the status bar's message and icon) and `chrome.py` (`mark_chrome`, which names a widget of
    the gallery and sets its `sbkChrome` property). New gallery widgets go here, not at the package root.
    - `gui/icons.py` (internal, not in `__all__`): reads the bundle and renders icons (`icon_svg`, `build_icon`, `palette_icon`,
      `clear_icon_cache`), `IconRole` (the palette role that tints an icon) and `ActionIcons`, the registry the window retints when the
      palette changes
    - `gui/editors/` - one module per editor (`text_editor.py`, `bool_editor.py`, `choice_editor.py`, `int_editor.py`,
      `float_editor.py`, `color_editor.py`, `enum_editor.py`, `file_editor.py`), all `ControlEditor` subclasses (`control_editor.py`:
      `valueChanged` and `value()`). `__init__.py` maps each control type to its editor in `EDITORS` and has `create_editor`; `_wheel.py`
      holds the wheel filter that ignores the wheel on an editor without focus. The colour and file editors open their dialogs through
      the module-level `_ask_color` and `_ask_file`, which tests replace.
  - `examples/` - the example stories `--examples` shows, built from stock Qt widgets, in `*_stories.py` modules loaded by discovery
    like any project's stories. They import only PySide6 and this package, every story has a docstring, and together they use every
    control type and every control option; `tests/test_examples.py` checks all three. They are copied as first stories, so keep them
    idiomatic.
  - `themes/` - the built-in themes: `theme_definition.py` (`ThemeDefinition`: name, colour scheme and palette colours), one module
    per theme (`light_theme.py`, `dark_theme.py`), `provider.py` (`ThemeProvider`, the protocol an application implements) and
    `builtin_theme_provider.py` (`BuiltinThemeProvider`, which applies the built-in themes and returns their design tokens), and
    `provider_loader.py` (internal: `load_theme_provider`, which imports a `module:attribute` spec, and `ThemeProviderError`)
  - `contrast.py` - WCAG contrast helpers
  - `polishing.py` (internal) - `polish_all_widgets`, the workaround for a Qt crash when the application style sheet changes while a
    widget was never polished
  - `resources/icons/` - package data, not code (`resources/__init__.py` makes it a package): `icon_manifest.toml` (the icons, the pinned
    Phosphor release), the generated `icon_bundle.json` and `licenses/phosphor-LICENSE.txt`. Never edit the generated files by hand
  - `app.py` - `run()` (exported), which creates the `QApplication`, activates the theme provider and opens the window
  - `py.typed` - marks the package as typed
- `scripts/icons/` - development only, not in the wheel: `build_icon_bundle.py` and the `icon_bundle/` package it runs, which download the
  pinned Phosphor package into `.icon-cache/` (git-ignored) and write the bundle, the licence file and `THIRD_PARTY_NOTICES.md`
- `THIRD_PARTY_NOTICES.md` - generated by the icon script
- `tests/` - pytest suite (`pytest-qt`), one test module per source module; `conftest.py` holds the shared fixtures,
  `fake_providers.py` the test theme providers and `story_files.py` the helpers that write story modules for discovery and CLI tests
- `docs/` - the roadmap, and `images/` with the README screenshot
- `README.md` - user documentation; `tests/test_readme.py` loads its first story and checks its controls table and `pyproject.toml`
  example, so keep the code in it runnable and update the test when the README's structure changes
- `.github/` - CI workflow and Dependabot configuration

## Code conventions
- **Python:** 3.11+ syntax only; the code must run on the oldest supported version.
- **Type hints** on every parameter and return value.
- **Docstrings:** Google style (`Args:`, `Returns:`, `Raises:`) on public classes, functions and methods. Docstrings and comments describe what
  the code does now; update them with the code.
- **Line length:** 150 characters.
- **Boolean parameters** are keyword-only (`def f(x, *, enabled: bool = True)`), as required by ruff `FBT`. When a Qt virtual method or a
  slot connected directly to a signal forces a positional bool, append `# noqa: FBT001` (or the matching code) with a short reason. Prefer
  `QSignalBlocker` over `blockSignals(True)`/`blockSignals(False)`.
- **New parameters** (functions, constructors, dataclass fields) are keyword-only and added after the existing ones, so positional callers do
  not break. For dataclass fields use `field(default=..., kw_only=True)`.
- **Frozen dataclasses** hold no mutable containers: use tuples, `frozenset` or a read-only mapping, and convert in `__post_init__`
  (`object.__setattr__`) when the caller may pass a list. Validate invariants in `__post_init__`.
- **Naming:** `PascalCase` classes, `snake_case` functions and variables, `_leading_underscore` for private members.
- **Logging:** class-level loggers (`self._logger = logging.getLogger(self.__class__.__name__)`); no `print()`, except for the command line's
  own output in `cli.py`.
- No commented-out code, no `TODO` comments that express uncertainty (link an issue instead), no bare `except`; do not swallow an exception
  without logging it. Keep imports sorted (stdlib, third party, local) and free of duplicates.
- Keep changes small and focused; do not add abstractions a task does not need.

## Library rules
- The library is generic: it must not import, name or depend on any application. Applications keep their stories in their own repository.
- The gallery is built from stock Qt widgets only. No widget library, and the only runtime dependency is `PySide6-Essentials`.
- Gallery chrome takes its colours from `QPalette` roles (`setBackgroundRole`, `setForegroundRole`, `palette(...)` in a style sheet), never from
  fixed colours, so it follows the active theme.
- The public API is exactly what `src/pyside6_storybook/__init__.py` exports in `__all__`. Everything else is internal and may change. A change
  to the public API adds an entry to `CHANGELOG.md`, under `## [Unreleased]` and the matching `### Added`/`### Changed`/`### Fixed` heading.
- Story discovery and the process-wide `default_registry` are for story authors. Library code takes a `StoryRegistry` as an argument instead of
  reading the global.
- A story is rebuilt from scratch on every control or theme change, so stories stay stateless.
- The built-in themes set the Fusion style and an explicit palette, including the Disabled colour group. They have no visible effect on widgets
  styled by an application-wide style sheet.

## Icons
Icons are bundled Phosphor SVGs, never downloaded at runtime, and the gallery imports nothing that can make a network request
(`tests/test_icons.py` checks it).
- **Source.** Only icons from the bundle, rendered with `palette_icon(name, role=...)` or bound to a button or action with
  `ActionIcons.bind(target, name, role=...)`. The window retints its `ActionIcons` from `changeEvent` when the palette changes, so no
  icon keeps a colour of its own. Qt delivers an application palette change to a widget as a `PaletteChange` event from the event loop,
  so a test waits for it with `qtbot.waitUntil`.
- **Adding an icon.** Add its Phosphor name to `icons` in `src/pyside6_storybook/resources/icons/icon_manifest.toml`, run
  `uv run python scripts/icons/build_icon_bundle.py`, and commit the regenerated `icon_bundle.json`, `licenses/` and
  `THIRD_PARTY_NOTICES.md`. `--check` fails when they are stale, and CI runs it.
- **Controls.** An icon-only button has an accessible name and a tooltip, and Tab reaches it. A menu is plain text without icons. A label
  is a plain name: no emoji prefix.
- **Contrast.** A chrome icon reaches 3:1 against the background it is drawn on, in both themes.

## Qt hygiene
- Every widget, layout item and menu has an owner: pass the parent at construction, or reparent a detached widget back to its owner. A
  parentless `QMenu()` or a form detached with `setParent(None)` lives on as a top-level window. Remove a widget with `deleteLater()` (after
  `hide()` or removing it from its layout), and in tests remember that `processEvents()` does not run deferred deletes; use
  `QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)`.
- Never connect a signal twice to the same slot. Connect in loops with `functools.partial`, not a lambda that closes over the loop variable.
- Use `QSignalBlocker` when setting several linked controls, then apply the change once.
- Guard slots that may run during teardown with `shiboken6.isValid`.
- **Polish before a style sheet change.** Qt crashes in `setStyleSheet` when a widget that was never polished existed while the
  application style sheet was cleared and was deleted after one was set again. Call `polish_all_widgets()` before the library changes
  the application style sheet, and `GalleryWindow._polish_widgets()` after building widgets (it runs with `_apply_tab_order` and
  polishes every widget, also those a failed render left for deletion).
- **Chrome is named through `mark_chrome`.** Every widget of the gallery that has an object name gets it from
  `mark_chrome(widget, "sbkName")` (`gui/chrome.py`): the `sbk` prefix, camel case, a string literal at the call site (a helper that
  builds widgets takes the literal from its caller), and the name added to the README's list in "Styling the gallery", which a test
  compares with the source in both directions. The helper also sets the property `sbkChrome`, which goes on every widget an application
  might style, internal children included (tab bars, viewports, editor inputs, which get no name), and never on an ancestor of the
  preview surface: those are marked with `chrome=False`. A widget made after polish is marked in its constructor.
- **No widget-local style sheets.** Colours come from palette roles and an application style sheet must be able to override every
  rule, so no widget calls `setStyleSheet`; a widget that needs a colour the palette cannot give gets code, as the sidebar's selection
  delegate does.
- Every icon-only, custom-painted or card-style control needs `setAccessibleName`/`setAccessibleDescription` and must be keyboard-focusable.
  Form labels set their editor as buddy, and the editor gets the label text as its accessible name.
- Application-wide changes (style, palette, style sheet) are applied through a `ThemeProvider` (`BuiltinThemeProvider` by default), which records what
  it found in `activate()` and restores it, the font included, in `deactivate()`; `run()` warns when one is left changed. Anything else that
  changes them must restore them too.
- Exceptions raised in a slot are printed and swallowed by Qt. Tests assert on them with `qtbot.capture_exceptions()`. Anything a story
  raises is caught by the window and shown in an `ErrorPanel`; a test for story errors asserts that `capture_exceptions()` stays empty.

## Keyboard and accessibility
- **A shortcut is added to one table.** The window's shortcuts come from `_WINDOW_SHORTCUTS` in `gui/window.py` and the canvas's from
  `_ZOOM_SHORTCUTS` in `gui/canvas.py`; the Keyboard shortcuts dialog is built from the same tables, so a new shortcut shows up in it. A
  test compares the dialog with every `QShortcut` of the window.
- **`/` is a `QShortcut`, and it is not delivered to a text field.** Qt does not deliver a `QShortcut` on a printable key to a focused
  `QLineEdit`, spin box or editable combo box, which claim it through `ShortcutOverride`, so typing a slash stays typing. A
  `keyPressEvent` fallback does not work: the tree and the actions list consume printable keys for keyboard search. Every other shortcut
  uses a modifier.
- **Do not take a key a widget already uses.** `Alt+Down` opens a combo box's popup, so story navigation is `Ctrl+Alt+Down`. When you add
  a shortcut, test that the widgets that would receive the key without it still do.
- **Order Tab explicitly.** Qt orders Tab by creation, and the story's widget, the controls and the docs are created last, so
  `GalleryWindow._apply_tab_order` chains the window again whenever they change. `QWidget.setTabOrder` moves a compound widget (a focus
  proxy that is a child: an editor, a tab widget) as one entry, but ignores a widget whose policy is `NoFocus`, so `ControlsPanel` gives
  each editor its input's policy. Walk the order with real Tab key clicks, and include the wrap from the last widget to the first.
- **A shortcut or Tab test needs an active window.** Use the `restore_window_activation` fixture and `show_active`. A widget that was
  just added is not visible until the event loop has run, and Tab skips it until then.
- **Keep focus when the preview is rebuilt.** The canvas gives focus to its scroll area before it hides a widget that has focus, or Qt
  moves focus to the next widget in the chain. A control edit never moves focus.
- **Name every focusable chrome widget.** A test walks them all, outside the story's widget, and fails on an empty accessible name.
- **Check contrast on what is drawn.** Fusion draws the focus ring in a colour derived from `Highlight` (darker when the value is at most
  200, else a fixed lightness), not in `Highlight`. The tests grab a widget after Tab and measure the ring. White text and 3:1 against
  the Dark `Window` cannot both hold for one `Highlight`, which is why Dark's colours are unchanged.
- **No fixed pixel heights in the chrome.** Use size policies and `sizeHint`, so the window follows the application font. A test sets a
  24 pt font and checks that no label is clipped and no widget has equal minimum and maximum heights.

## Test rules
- Every bug fix comes with a regression test that fails without the fix. Assert behaviour (values, objects, call counts), not a marker.
- Tests build their own `StoryRegistry`; none may register a story in `default_registry`, and a test that must touch it restores it
  (`monkeypatch`, or `try/finally`). Stories in tests are made of stock Qt widgets.
- A test that imports story modules (anything calling `load_stories`, or the CLI) uses the `stories` fixture in `tests/conftest.py`,
  which isolates `sys.path`, `sys.modules` and both bindings of the default registry (`pyside6_storybook.registry.default_registry`,
  which `@story` reads, and `pyside6_storybook.default_registry`, which projects import), and writes its story files under `tmp_path`
  with the helpers in `tests/story_files.py`.
- A test that changes the application palette, style or style sheet restores them in a fixture with `try/finally`
  (`restore_application_look` and `themes` in `tests/conftest.py`).
- Drive widgets the way a user does: `qtbot.keyClicks`, `qtbot.mouseClick`, or the editor's own setters. Assert which values were emitted, not
  only how many.
- Bound anything that can hang: a finite timeout on waits and subprocesses, and `QT_QPA_PLATFORM=offscreen` for any subprocess that starts Qt.
- Do not weaken an existing assertion to make a test pass; add an explicit exclusion instead.
- Restore global state: `monkeypatch` or `caplog.set_level`, never set a shared logger's level directly.

## Pull requests
- Keep a pull request to one concern and make its description match what it does; update it when scope changes.
- Use `Closes #N` only when the pull request fully satisfies the issue; use `Refs #N` for a partial step.
- File each known gap or follow-up as an issue and link it.
- Before pushing: `uv run ruff check .`, `uv run ty check` and `QT_QPA_PLATFORM=offscreen uv run pytest`.
- CI workflows (`.github/workflows/`): never interpolate `${{ inputs.* }}` or `${{ github.event.* }}` into shell source; pass them through
  `env:` and quote the variable.

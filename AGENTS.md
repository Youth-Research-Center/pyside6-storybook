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
uv run python -m pyside6_storybook
```
Stories are registered by importing the module that defines them. Until story discovery exists the window shows its empty state.

## Tests
There is no display in CI or in agent sandboxes: set `QT_QPA_PLATFORM=offscreen` for every test run. `tests/conftest.py` also sets it as a
default before Qt is imported.

```bash
QT_QPA_PLATFORM=offscreen uv run pytest -q
QT_QPA_PLATFORM=offscreen uv run pytest tests/test_window.py
QT_QPA_PLATFORM=offscreen uv run --isolated --python 3.11 --resolution lowest-direct pytest -q   # oldest supported dependencies
```

`pytest-timeout` aborts any test that runs longer than 120 seconds (set in `pyproject.toml`), so a hung Qt test cannot hold a job.

## Code quality
`ruff check` (rules `E`, `F`, `B`, `Q`, `I`, `FBT`, 150-character lines) is the only lint gate; there is no `ruff format` step. Run it and the
tests for the code you touched before every push. `W` rules are not selected, so check whitespace on the files you changed:

```bash
uv run ruff check .
uv run ruff check --fix .                                  # auto-fix, including import order
uv run ruff check --select W291,W292,W293 <files you changed>
```

## Project structure
- `src/pyside6_storybook/` - the package
  - `__init__.py` - the public API (`__all__`) and `__version__`
  - `__main__.py` - `python -m pyside6_storybook`
  - `controls/` - control dataclasses, one module per type (`text_control.py`, `bool_control.py`, `choice_control.py`,
    `int_control.py`, `float_control.py`); `__init__.py` re-exports them and defines the `Control` union, and `_range.py` holds
    the range check shared by the int and float controls
  - `registry/` - the story model, one module per type: `story_context.py` (`StoryContext`, `StoryFunction`), `story_definition.py`
    (`Story`, `StoryOrigin`) and `story_registry.py` (`StoryRegistry`); `__init__.py` re-exports them and holds `default_registry` and
    the `@story` decorator
  - `controls_panel.py` - `ControlsPanel`, the editors for a story's controls
  - `window.py` - `GalleryWindow`
  - `themes/` - the built-in themes: `theme_definition.py` (`ThemeDefinition`: name, colour scheme and palette colours), one module
    per theme (`light_theme.py`, `dark_theme.py`) and `builtin_themes.py` (`BuiltinThemes`, which applies them)
  - `contrast.py` - WCAG contrast helpers
  - `app.py` - `run()`, which creates the `QApplication` and opens the window
  - `py.typed` - marks the package as typed
- `tests/` - pytest suite (`pytest-qt`), one test module per source module
- `docs/` - the roadmap
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
- **Logging:** class-level loggers (`self._logger = logging.getLogger(self.__class__.__name__)`); no `print()`.
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

## Qt hygiene
- Every widget, layout item and menu has an owner: pass the parent at construction, or reparent a detached widget back to its owner. A
  parentless `QMenu()` or a form detached with `setParent(None)` lives on as a top-level window. Remove a widget with `deleteLater()` (after
  `hide()` or removing it from its layout), and in tests remember that `processEvents()` does not run deferred deletes; use
  `QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)`.
- Never connect a signal twice to the same slot. Connect in loops with `functools.partial`, not a lambda that closes over the loop variable.
- Use `QSignalBlocker` when setting several linked controls, then apply the change once.
- Guard slots that may run during teardown with `shiboken6.isValid`.
- Every icon-only, custom-painted or card-style control needs `setAccessibleName`/`setAccessibleDescription` and must be keyboard-focusable.
  Form labels set their editor as buddy, and the editor gets the label text as its accessible name.
- Application-wide changes (style, palette, style sheet) are applied through `BuiltinThemes`, which remembers what it found and restores it on
  `deactivate()`. Anything else that changes them must restore them too.
- Exceptions raised in a slot are printed and swallowed by Qt. Tests assert on them with `qtbot.capture_exceptions()`.

## Test rules
- Every bug fix comes with a regression test that fails without the fix. Assert behaviour (values, objects, call counts), not a marker.
- Tests build their own `StoryRegistry`; none may register a story in `default_registry`, and a test that must touch it restores it
  (`monkeypatch`, or `try/finally`). Stories in tests are made of stock Qt widgets.
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
- Before pushing: `uv run ruff check .` and `QT_QPA_PLATFORM=offscreen uv run pytest`.
- CI workflows (`.github/workflows/`): never interpolate `${{ inputs.* }}` or `${{ github.event.* }}` into shell source; pass them through
  `env:` and quote the variable.

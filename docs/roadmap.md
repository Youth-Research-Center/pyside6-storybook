# pyside6-storybook: plan and roadmap

Status: plan for the first release. The issue tracker is the source of truth for
scope and progress; this document records the design decisions the issues rely on.

## What it is

`pyside6-storybook` is a small, Storybook-like component explorer for PySide6
applications. A developer writes *stories* (functions that build one widget in one
state), runs `pyside6-storybook`, and gets a window where each story can be
browsed in isolation, its arguments edited live, and the theme switched. From
milestone 5 on, the same stories are rendered offscreen by a pytest plugin as smoke
tests.

| | |
| --- | --- |
| Repository | `Youth-Research-Center/pyside6-storybook` |
| PyPI name | `pyside6-storybook` |
| Import package | `pyside6_storybook` |
| CLI | `pyside6-storybook` (also `python -m pyside6_storybook`) |
| Licence | MIT |

It is not affiliated with the Qt Company or with Storybook.

## Principles

1. **Generic.** The library knows nothing about PandaPlot or any other application.
   Applications keep their stories in their own repository and use the library as a
   development dependency.
2. **Plain Qt inside.** The gallery is built from stock Qt widgets and depends on no
   widget library. An application-wide stylesheet applied by a theme provider still
   reaches the gallery's own widgets; the provider contract (milestone 4) covers that.
3. **Small.** One runtime dependency (`PySide6-Essentials`). Features that need more
   (screenshot comparison, a docs site) are optional extras or development-only.
4. **A broken story should not take the gallery down.** A story module that fails to
   import and a story that raises while rendering are shown as errors in the window,
   and the other stories keep working. A hard crash inside Qt cannot be caught.
5. **Stories are ordinary Python.** No configuration is required to get started; a
   decorator and a function are enough.

## Starting point

The code is ported from PandaPlot's `pandaplot_storybook/` (registry, controls panel,
three-pane window, WCAG contrast helpers and their tests). The port removes every
PandaPlot import:

| PandaPlot piece | Replacement |
| --- | --- |
| `DropDownComboBox`, `IntegerInput`, `SliderWithSpinbox` in `controls.py` | `QComboBox`, `QSpinBox`, `QDoubleSpinBox` |
| `SectionHeader`, `SegmentedControl` in `main_window.py` | `QLabel`, `QComboBox` |
| `ThemeManager`, `EventBus`, `ApplicationConfig` in `app.py` and `main_window.py` | built-in light and dark themes (milestone 1), then a theme provider hook (milestone 4) |
| a builder returning `StoryDef(controls, make_widget)` with `make_widget(values, tokens)` | `@story(...)` on a function that takes a `StoryContext` (see below) |
| the window calling `widget.set_tokens(tokens)` on every preview | nothing implicit: a story passes `ctx.tokens` to its widget itself |
| `sys.path` insertion in `__init__.py` | story discovery through the CLI, `pyproject.toml` and entry points |
| `SEGMENTED_SELECTED_TEXT` in `color_contrast.py` | dropped (PandaPlot-specific); `contrast_ratio` and `pick_contrasting_text` are kept and used to test the built-in palettes |

PandaPlot's 18 stories stay in PandaPlot and are migrated in milestone 7.

## Design decisions

### Package and tooling

- `src/pyside6_storybook/` layout, `hatchling` build backend, `py.typed` marker.
- Runtime dependency: `PySide6-Essentials>=6.8` (Qt Widgets only). An application that
  depends on the full `PySide6` package satisfies it, because `PySide6` pins the
  matching `PySide6-Essentials`.
- Python 3.11 or newer (3.10 reached end of life in October 2026).
- `uv` for environments and the lockfile; `ruff check` with rules `E`, `F`, `B`, `Q`,
  `I`, `FBT` and a 150-character line length, as in PandaPlot; `pytest` with
  `pytest-qt`, always run with `QT_QPA_PLATFORM=offscreen` in CI.
- CI runs lint and tests on Windows, macOS and Linux, on the oldest and newest
  supported Python. One extra job tests the lowest allowed dependency versions and is
  pinned to Python 3.11: PySide6 6.8.0 declares `Requires-Python <3.13`, and `uv`
  ignores that upper bound, so the pair must be chosen by hand.
- The version lives in `pyproject.toml`; `pyside6_storybook.__version__` reads it
  from the installed package metadata.

### Story model (milestone 1, extended in milestone 2)

A story is a function that receives a `StoryContext` and returns a `QWidget`:

```python
from PySide6.QtWidgets import QPushButton, QWidget

from pyside6_storybook import BoolControl, StoryContext, TextControl, story


@story(
    "Inputs/Button",
    controls=[TextControl("text", "Click me"), BoolControl("enabled", default=True)],
)
def button(ctx: StoryContext) -> QWidget:
    widget = QPushButton(ctx.args["text"])
    widget.setEnabled(ctx.args["enabled"])
    return widget
```

- **Identity.** The string passed to `@story` is the story's unique id. It is a
  `/`-separated path: the last segment is the story's name, the segments before it are
  groups. Milestone 1 already parses it this way (the sidebar shows the full id in a
  flat list); milestone 3 turns it into a tree. No rename is needed later.
- **`@story` returns a `Story` object**, not the bare function. It is callable
  (`button(ctx)` still works) and records the id, controls, docstring and where it was
  defined (module and qualified name). Returning an object is what lets milestone 2
  add `button.variant("Disabled", args={"enabled": False})` without breaking stories
  written for milestone 1.
- **Registry.** The decorator registers the story in a process-wide default
  `StoryRegistry`. Registering an id again from the *same* module and qualified name
  replaces the earlier story (a module that is imported twice, or reloaded, must not
  fail); registering it from a different place raises `ValueError`. A `StoryRegistry`
  can also be created directly, which the library's own tests do.
- **`load_stories(targets) -> StoryRegistry`** is the one entry point used by the CLI,
  the tests and later the pytest plugin: it imports the targets and returns the
  registry holding their stories.
- **`StoryContext`** is a frozen, keyword-only dataclass. In milestone 1 it has `args`
  (a read-only mapping of the current control values) and `theme` (the active theme
  name). Later fields (`tokens`, action logging) are added with defaults, so existing
  stories and tests that build a context keep working.
- **Controls** are frozen dataclasses: `TextControl`, `BoolControl`, `ChoiceControl`,
  `IntControl`, `FloatControl`. `ChoiceControl.options` is a tuple. A control bundles
  an argument's name, default value and editor; from milestone 2 a story variant's
  `args` override those defaults, so there is one way to give an argument a value.
- A story is rebuilt from scratch whenever a control value or the theme changes. This
  keeps stories stateless; widget-internal state (focus, scroll position) is lost on
  rebuild, which is acceptable for v0.1.

### Story discovery (milestone 1)

`pyside6-storybook [TARGET ...]` accepts, for each target:

- **a path to a folder:** every `*_story.py` and `*_stories.py` file below it is
  loaded;
- **a path to a `.py` file:** that file is loaded;
- **a dotted module or package name** (`myapp.stories`): imported; for a package, its
  submodules named `*_story` or `*_stories` are imported too. `__main__`, tests and
  `conftest` modules are never imported.

When a target is both an existing path and an importable name, the path wins.

A file is always imported under its canonical module name: the loader walks up from
the file while the folder contains `__init__.py`, puts the parent of the topmost
package on `sys.path`, and imports the dotted name. That makes relative imports work
and guarantees that a file reached through a path and through a package import is the
same module, so its stories are registered once. Only a file that is not inside a
package gets a synthetic module name. Duplicate targets are ignored. The current
working directory is put on `sys.path`, as `python -m` does, so stories can import
the application under development.

With no targets on the command line, the default sources are used, in this order:

1. `[tool.pyside6-storybook]` in the `pyproject.toml` of the current directory:
   `stories = ["path/or/module", ...]` and optional `pythonpath = ["src"]`;
2. the `pyside6_storybook.stories` entry-point group of installed packages (each
   entry point names a module to import).

Only when there are no targets, no configuration and no entry points are the built-in
examples shown, so `pyside6-storybook` opens something useful straight after
`pip install`. They are never a fallback for a load that failed. `--examples` shows
them explicitly, and `--list` prints the discovered story ids and exits without
opening a window (used by CI smoke tests).

The `QApplication` is created before any story module is imported, so a module that
creates a widget at import time does not abort the process. Loading stories means
importing and running the user's own code, exactly as running their test suite does.

### Gallery window (milestone 1, extended in milestone 3)

Three panes in a splitter, as in the PandaPlot original: story list, preview, and a
side pane with the theme switch and the controls of the selected story. The chrome is
styled through `QPalette` roles, so it follows the active theme. A story that raises,
or returns something that is not a `QWidget`, shows an error panel with the traceback
in the preview; a module that failed to import is listed with its error.

Milestone 3 replaces the list with a searchable tree and adds a canvas toolbar
(background, size presets, zoom), an Actions panel that logs widget signals, a Docs
tab built from docstrings and source, and hot reload.

### Theming (milestone 1 and milestone 4)

Qt's own colour-scheme switch (`QStyleHints.setColorScheme`) was tested on PySide6
6.8.0 and 6.12.0 and is not a usable basis: it is a no-op on the offscreen platform,
so it cannot be tested in CI, and its effect depends on the platform style. The
built-in themes therefore set the Fusion style and an explicit light or dark
`QPalette`, including the Disabled colour group (a palette built from plain
`setColor(role, ...)` calls draws disabled text in the active colour).
`setColorScheme` is still called on a best-effort basis for platform-drawn parts. The
result is the same style and colours on every platform; fonts and DPI still differ,
so screenshot snapshots (milestone 5) are per platform.

- **Milestone 1** ships the built-in Light and Dark themes and the switch in the
  window. This is internal, with no public theming API yet, but it is written behind
  the shape milestone 4 publishes: an object that is activated once with the
  `QApplication`, switches between named themes, and is deactivated on exit.
- **Milestone 4** makes that a public `ThemeProvider` protocol and adds what an
  application's theme manager needs: construction with the `QApplication`,
  `set_theme(name)`, a change notification the gallery subscribes to (an application
  may change theme by itself), design tokens handed to stories as `ctx.tokens`, and
  teardown that restores the style, palette, font and stylesheet the provider changed.
  A provider that applies an application-wide stylesheet must also set a matching
  palette, because the gallery chrome is drawn from palette roles. The built-in themes
  have no visible effect while an application stylesheet is set. PandaPlot's
  `ThemeManager` plugs in through this hook.

This moves "built-in light/dark palettes" from the draft milestone 4 into milestone 1,
so that v0.1 has the theme switch the README promises.

### Testing support (milestone 5)

A pytest plugin (`pytest11` entry point, opt-in through a command-line flag or ini
option) that collects every discovered story and renders it offscreen with its
default arguments, in each available theme. On top of that: optional screenshot
snapshots (comparison dependency behind an extra, baselines per platform), and basic
accessibility checks (interactive widgets have accessible names; text and background
meet a WCAG contrast ratio).

### Release (milestone 6)

Tag-driven GitHub Actions release with PyPI Trusted Publishing (OIDC, no stored
token), TestPyPI first by manual dispatch, a wheel-install smoke test on three
operating systems, `RELEASING.md`, a changelog, and a small docs site.

## Milestones

v0.1.0 is milestones 1 and 6.

| # | Milestone | Issues | Outcome |
| --- | --- | --- | --- |
| 1 | Foundation (v0.1) | #1 to #13 | Installable project with CI; story model, controls and window ported to plain Qt; errors shown in the window; stories loaded from modules, files, folders, `pyproject.toml` and entry points; example stories; light and dark themes |
| 2 | Story API | #14 to #18 | Several stories per component (variants with `args`), colour/enum/file arguments, control options, decorators, layout parameter |
| 3 | Gallery UI | #19 to #25 | Searchable tree, canvas toolbar and zoom, Actions panel, Docs tab, hot reload, keyboard access |
| 4 | Theming Hook | #26 to #31 | `ThemeProvider` protocol and lifecycle, tokens passed to stories, provider selection, chrome under an application stylesheet, a "System" theme, a worked example |
| 5 | Testing | #32 to #35 | pytest plugin, optional screenshot snapshots, accessibility checks |
| 6 | Release 0.1.0 | #36 to #41 | Packaging metadata, wheel smoke test, Trusted Publishing, `RELEASING.md`, docs site, first release |
| 7 | Early Users | #42 and #43 | PandaPlot's storybook migrated; contribution guide |

Order after v0.1: milestones 2 to 5 can be scheduled as needed, with these
dependencies. The sidebar tree (3) uses the id paths from milestone 1 and gains
component grouping from milestone 2. The pytest plugin (5) renders in the built-in
themes and picks up provider themes once milestone 4 is done. Milestone 7 needs
milestone 4.

## Out of scope

- A web UI, or rendering Qt Quick/QML components (widgets only for now).
- Add-on or plugin systems beyond the theme provider and entry-point discovery.
- Visual regression as a hosted service; snapshots are local files.
- Supporting PyQt6 or PySide2.
- Inferring controls from type hints, and remembering window state between runs. Both
  were considered and left out to keep the library small.

## Risks and open questions

- **PyPI name.** `pyside6-storybook` must be confirmed free and claimed (milestone 6).
- **Fusion-only built-in themes.** Stories of an application that relies on a native
  style look different under the built-in themes. The provider hook is the answer, and
  an "application default" theme that leaves style and palette untouched is part of
  milestone 4.
- **Hot reload.** Re-importing modules that hold Qt classes is fragile; the first
  version may rebuild the gallery from a fresh import instead of patching modules in
  place. Decided in the milestone 3 issue.
- **Widget zoom.** Scaling live widgets needs `QGraphicsProxyWidget` or a scaled
  screenshot; kept separate from the simpler canvas options so it can be dropped.
- **Process-wide default registry.** Simple for story authors, but tests must not leak
  stories into each other; the library's own tests use explicit registries.

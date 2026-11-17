# Testing (milestone 5): design spec

Status: reviewed (findings applied). Issues: #32 (pytest plugin), #34 (accessible names and keyboard focus), #35 (text contrast), #33 (screenshot
snapshots). The issues are the source of truth for scope; this spec records how they are met and where it deviates from their wording.

## 0. Ground rules

- **Stories keep working.** Nothing changes for a story that does not use the new `checks_ignore` parameter (§2).
- **One runtime dependency.** PySide6-Essentials stays the only runtime dependency. pytest and pytest-qt come through the optional
  extra `pyside6-storybook[pytest]`.
- **A plugin that costs nothing when it is off.** The plugin is registered through the `pytest11` entry point, so every pytest run in
  an environment that has the library loads it. Without `--storybook` it collects nothing and imports nothing from Qt (§1.1).
- **Checks are library functions first.** The accessibility and contrast checks are public functions that a hand-written test can
  call on any widget. The plugin only turns them into test items.

## 1. pytest plugin (#32)

### 1.1 Packaging and start-up cost

- `pyproject.toml` gains `[project.entry-points.pytest11] pyside6_storybook = "pyside6_storybook_pytest"` and
  `[project.optional-dependencies] pytest = ["pytest>=8.0", "pytest-qt>=4.4"]`.
- **The entry module is a separate, tiny top-level module,** `src/pyside6_storybook_pytest.py`, shipped in the same wheel (hatch
  `packages` gains it).
  - **Why not the package:** importing anything under `pyside6_storybook` runs the package `__init__`, which imports every module:
    160–230 ms, or 85–105 ms on top of an already imported PySide6.
  - **Why not a lazy `__init__`:** a lazy (PEP 562) `__init__` would cost 0.3 ms, but `ty` then loses unknown-attribute diagnostics
    and `__version__` becomes `Any`. The separate module costs 0.2 ms and leaves the public package untouched.
- **What the entry module holds:** only `pytest` and the standard library at module level. It defines the options, the ini keys,
  the `storybook` marker, `pytest_configure` and the hooks. It imports the implementation, `pyside6_storybook.testing.*` (internal,
  §1.7), inside the hook bodies, and only when the plugin is on.
- **A test of the cost:** a core test runs `python -c "import pyside6_storybook_pytest, sys; print(any(m.startswith(('PySide6',
  'pyside6_storybook.')) for m in sys.modules))"` in a subprocess with a timeout, and expects `False`.

### 1.2 Enabling and options

The plugin is inactive unless `--storybook` is given or `storybook = true` is set in the ini options. Every setting has a
command-line option and an ini option; the command line wins.

| Option | ini | Meaning |
| --- | --- | --- |
| `--storybook` | `storybook` (bool) | Turn the plugin on. |
| `--storybook-stories TARGET` (repeatable) | `storybook_stories` (linelist) | Story targets. Default: `[tool.pyside6-storybook]`. |
| `--storybook-theme-provider SPEC` | `storybook_theme_provider` | `module:attribute`. Default: `theme_provider`, else built-in. |
| `--storybook-themes NAMES` | `storybook_themes` (comma-separated) | The themes to render each story in. Default: every name the provider lists. |
| `--storybook-qt-warnings {fail,ignore}` | `storybook_qt_warnings` | Whether a Qt warning logged during a render fails the item. Default `fail`. |
| - | `storybook_qt_warnings_ignore` (linelist of regexes) | Warnings that never fail. Default: `propagateSizeHints`. |

- **The `propagateSizeHints` default.** On the offscreen platform Qt logs "This plugin does not support propagateSizeHints()" when
  some widgets are shown; the examples' Palette and Sign-in Form log it in every theme. That is why the ignore list is not empty by
  default. A test checks both the default and a custom pattern.
- **Sources.** The plugin reads `[tool.pyside6-storybook]` from `pyproject.toml` in `config.rootpath`, with
  `resolve_story_sources(targets, examples=False, cwd=rootpath)`. It puts `pythonpath` on `sys.path` with `put_on_sys_path`, as the
  command line does.
  - When neither the plugin options nor `pyproject.toml` name any stories, `resolve_story_sources` falls back to entry points and
    then to the built-in examples. `StorySources` gains a keyword-only `fallback: bool` (true when the targets are the
    built-in examples because nothing was configured), so no caller parses the `origin` string. The plugin accepts entry points, but
    treats the built-in-examples fallback as a usage error:
    "no stories configured: set `storybook_stories` or `stories` in `[tool.pyside6-storybook]`". It never silently tests the
    library's own examples.
  - The examples can still be named explicitly: `--storybook-stories pyside6_storybook.examples`.
- **Configuration errors.**
  - **Sources and options are checked in `pytest_configure`,** which needs no Qt: an invalid `pyproject.toml` table, the examples
    fallback, or a malformed option raises `pytest.UsageError` with the command line's message. A `UsageError` raised during
    collection crashes pytest-xdist workers (INTERNALERROR, exit 3), while one raised in `pytest_configure` is a clean exit 4 in every
    mode.
  - **Errors that need the `QApplication` fail a collector item:** a provider that fails to load, or an unknown name in
    `storybook_themes`. The error becomes a single failing `storybook::configuration` item, and no story items are collected.
- **The `storybook` marker.** Every storybook item carries a registered `storybook` marker, so `-m "not storybook"` runs a project's
  other tests alone, even with `storybook = true` in the ini (which otherwise adds the story items to every run, including
  `pytest tests/test_x.py`).

### 1.3 Collection

- **The QApplication comes first.** On the first collection with the plugin on, the plugin:
  1. sets `QT_QPA_PLATFORM` to `offscreen` unless it is already set;
  2. creates the `QApplication` (or reuses an existing one), before any story module is imported, so a module that builds a widget
     at import time works, as with the command line;
  3. loads the provider, then the stories (`load_stories`), in the same order as the command line.
  pytest-qt's `qapp` fixture reuses an existing `QApplication`, so the two do not conflict. The plugin's `QApplication` ignores
  pytest-qt's `qapp_cls`, `qapp_args` and `qt_qapp_name` (pytest-qt only warns about the class); the README says so. The stories are
  loaded into a fresh `StoryRegistry` with the default registry swapped in, as `ReloadSession` does, so repeated in-process runs
  (pytester) do not see stale stories.
- **Items.** In `pytest_collection_modifyitems` (`tryfirst=True`, so a project's own `conftest.py` hook sees the story items), the
  plugin creates a `StorybookCollector` node (a `pytest.Collector`, parent the session, built with `nodeid="storybook"`) and appends
  its items to `items`.
  - Each item is built with an explicit `nodeid=f"storybook::{id}[{suffix}]"`. Without it the session-parented collector's nodeid is
    `::storybook`, and on pytest 9 `--lf` mis-parses `[...]` as parameters of an item without params and reruns everything.
  - A `pytest_make_collect_report` wrapper appends the collector to the session's report, so "collected N items" and `--co` count the
    story items.
  - Nodeids look like `storybook::Inputs/Button/Default[Dark]`. A storybook nodeid cannot be given as a positional argument ("file or
    directory not found"); `-k` and `--deselect` select items, and the README says so.
  - The items come in registry order, then theme order, so collection is deterministic, as pytest-xdist requires.
  - `-k Dark`, `-k "Inputs and not Disabled"` and `--lf` work. The last-failed plugin's `pytest_collection_modifyitems` is a
    wrapper that filters after every other implementation has run, so it sees the appended items. The plan's review must confirm
    `-k`, `--lf`, `--co` and `-n 2` with experiments.
- **Kinds of item.** One `StoryItem` per story and theme. The checks of §2–§4 add more kinds, with one bracketed suffix each, so the
  suffix is never parsed as two parameters:
  - `[a11y-name]` and `[a11y-focus]`, once per story;
  - `[<theme>-contrast]`, per story and theme;
  - `[<theme>-snapshot]`, per story and theme.
  Every item kind is listed in `README.md`.
- **pytest-xdist.** With `-n`, the default `load` distribution spreads the story items; with `--dist loadfile` or `loadscope` all
  storybook items share one node and run on one worker. The README says so.
- **Load errors.** Each `LoadError` from `load_stories` becomes a `StoryLoadErrorItem` named `load-error[<source>]`. It fails with
  the error's message and traceback, so a story module that fails to import is a failing test, not a silent skip.

### 1.4 Running an item

- **Provider lifecycle.** The `StorybookSession` object, stored on `config.stash`, owns the provider and the `QApplication`.
  - It activates the provider before the first story item it runs.
  - In `pytest_runtest_teardown(item, nextitem)`, it deactivates the provider when `nextitem` is not a storybook item, and always
    in `pytest_sessionfinish`. The application's look is therefore restored before any other test runs, even when the storybook
    items are interleaved with other tests (`pytest-randomly`, pytest-xdist).
  - The plugin activates a provider again after `deactivate`. The built-in provider supports that. `docs/theming.md` and the
    `ThemeProvider` docstring gain the rule "a provider can be activated again after `deactivate`" (the pytest plugin needs it).
- **Steps of a `StoryItem`:**
  1. Polish every widget, then `set_theme(theme)` if the provider's current theme differs.
  2. Build a `StoryContext` with:
     - the story's default arguments (`story.default_args()`, the same values the gallery starts with, variant overrides included);
     - the theme;
     - an `ActionSink` that discards entries;
     - the provider's `tokens()` and `color_scheme()`, read with `read_tokens(provider)` and `read_color_scheme(provider)` from a
       new internal module, `themes/provider_values.py`. These helpers raise on a provider error or a wrong type (a `tokens()` that
       is not a mapping). The window uses the same two helpers inside its `_call_provider` guard and keeps its caching and error
       behaviour unchanged (`tests/test_tokens.py` and `tests/test_theme_provider.py` keep passing). In the plugin, a provider error
       fails the story item.
  3. `render_story(story, ctx, registry=registry)` builds the widget and its decorators.
  4. Put the root in a host widget with `autoFillBackground` and the `Window` background role, as the gallery's preview surface does,
     and show the host (offscreen). Rendered as a top-level window, a translucent style-sheet background is painted twice over a
     transparent image, which skews pixel checks and snapshots. Then clear focus (`QApplication.focusWidget().clearFocus()` when the
     focus is inside the root), and run `QApplication.processEvents()` twice. The shown host becomes the active window offscreen and
     a line edit or spin box takes focus; its blinking caret would make snapshots differ and its focus look would enter the checks.
  5. Run the item's check, if it is a check item (§2–§4): the accessibility rules on the root, and contrast and snapshots on the
     rendered host.
  6. Hide the host and delete it with the root, flushing `DeferredDelete`.
- **Failures.** A `StoryRenderError` fails the item with its title and details. A failure caused by the story's own code does not
  print a pytest traceback, because `repr_failure` returns the error's text. While the item runs, a Qt message handler collects
  `QtWarningMsg`, `QtCriticalMsg` and `QtFatalMsg`. With `storybook_qt_warnings = fail` the item fails and lists the messages that no
pattern of `storybook_qt_warnings_ignore` matches. The handler
  chains to the previous one, so pytest-qt's capture still works.
- `reportinfo()` returns the story function's file and line, and `"story <id> [<theme>]"`.
- **Session end.** In `pytest_sessionfinish` the session deactivates the provider, restores both bindings of the default registry
  (`pyside6_storybook.registry.default_registry` and `pyside6_storybook.default_registry`) to what they were before loading, and
  reinstalls the previous Qt message handler. pytester restores `sys.path` and `sys.modules`; the provider restores the look.

### 1.5 The `render_story` fixture

- `render_story(story_id, *, args=None, theme=None) -> QWidget` renders a story by id and returns the story's own (undecorated)
  widget, shown.
  - `args` overrides some default arguments; it is coerced with the controls, and an unknown name raises `KeyError`.
  - `theme` activates the provider for the test, sets the theme, and deactivates the provider at teardown.
  - At teardown every rendered root is hidden and deleted.
- The fixture works without `--storybook`. It loads the same sources lazily, once per session, and an unknown story id raises
  `KeyError` listing close matches.
- It depends on pytest-qt's `qapp`. Without pytest-qt it raises `pytest.UsageError("render_story needs pytest-qt: install
  pyside6-storybook[pytest]")`. The plugin itself (the collected items) does not need pytest-qt.

### 1.6 Module layout

- `src/pyside6_storybook_pytest.py`: the entry module (§1.1).
- `src/pyside6_storybook/testing/` (internal), one module per type:
  - `storybook_session.py`: `StorybookSession` (the `QApplication`, the provider lifecycle, the registry);
  - `storybook_collector.py`: `StorybookCollector`;
  - `story_item.py`: `StoryItem` and the check items;
  - `load_error_item.py`: `StoryLoadErrorItem` and the configuration item;
  - `qt_messages.py`: the message handler and the ignore patterns;
  - `fixtures.py`: the `render_story` fixture's implementation.
- `src/pyside6_storybook/testing/snapshots.py`: capture, comparison and diff images (§4, added by PR 4).
- `src/pyside6_storybook/themes/provider_values.py`: `read_tokens` and `read_color_scheme`, shared with the window (§1.4).

### 1.7 Tests

- `tests/conftest.py` enables `pytester` (`pytest_plugins = ["pytester"]`).
- New tests in `tests/test_pytest_plugin.py` use `pytester` with in-process runs, and subprocess runs where isolation needs it:
  - a passing project (one item per story and theme, readable ids);
  - a story that raises (the traceback is shown);
  - a story that returns `None`;
  - an import error (a failing `load-error[...]` item);
  - `-k` selection, `--lf` (on the installed pytest), `--co` counts, `-m "not storybook"`, and a logged Qt warning (fail, `ignore`,
    and the ignore patterns);
  - configuration errors: a usage error from `pytest_configure`, and the failing `storybook::configuration` item;
  - the provider restored after the items and between interleaved tests;
  - the examples fallback as a usage error;
  - the `render_story` fixture (args, theme, unknown id, teardown).
- `pytest-xdist` joins the dev dependencies, and a `full` test runs `-n 2`, including a configuration error under `-n 2` (exit 4, no
  INTERNALERROR).
- The import-cost test of §1.1.

## 2. Accessible names and keyboard focus (#34)

### 2.1 The checks (public)

- A new public subpackage, `pyside6_storybook.checks`, with one module per type:
  - `check_issue.py`: `CheckIssue`, a frozen dataclass with `rule`, `widget_class`, `object_name`, `path` (the class names from the
    checked root down to the widget, with indices among siblings of the same class, for example `QWidget/QGroupBox[0]/QToolButton[1]`)
    and `message`;
  - `accessibility.py`: `check_accessible_names(widget) -> list[CheckIssue]` and `check_keyboard_focus(widget) -> list[CheckIssue]`.
  `pyside6_storybook.checks` re-exports these. The package root does not, so its `__all__` is unchanged. CHANGELOG `### Added`
  lists them.
- **Which widgets are checked.** A descendant of the checked widget (the widget itself included) is checked when it is visible to the
  root, enabled, and either:
  - an instance of `QAbstractButton`, `QLineEdit`, `QTextEdit`, `QPlainTextEdit`, `QAbstractSpinBox`, `QComboBox`, `QAbstractSlider`
    (except `QScrollBar`), `QAbstractItemView` or `QTabBar`; or
  - a widget whose `focusPolicy()` includes `TabFocus`.
- **Excluded internal children,** which their composite handles:
  - a widget that is the `focusProxy()` of an ancestor, or whose ancestor's focus proxy chain reaches it (the line edit of a spin box
    or an editable combo box);
  - scroll-area viewports;
  - scroll bars;
  - the `QTabBar` of a `QTabWidget`, checked through the tab widget's page titles instead;
  - the internal children of `QAbstractSpinBox` and `QComboBox`;
  - descendants of a `QAbstractScrollArea` that are outside its viewport: an item view's `QHeaderView`s and its corner button, which
    the view handles;
  - children of a `QLineEdit` (its clear button and actions, which are `NoFocus` and unnamed by design).
- **Containers.** A `QTabWidget` itself is not checked (it has `TabFocus` and no name); its tabs are, through their texts. A
  `QScrollArea` is not checked either: it is a container, and its content is.
- **Rule `name`.** `QAccessible.queryAccessibleInterface(widget).text(QAccessible.Text.Name).strip()` is not empty. This is what a
  screen reader sees: the widget's text, a buddy label's text, or `setAccessibleName`. It works offscreen with no assistive
  technology active (`QAccessible.isActive()` is false), and mnemonics are stripped (`&Save` gives "Save").
  - **Exception for `QComboBox`:** its accessible name falls back to the current text, so an unlabelled combo box would pass. A
    combo box needs `accessibleName()` or a buddy label.
  - A tooltip does not supply a name.
- **Rule `focus`.** `widget.focusPolicy()` includes `Qt.FocusPolicy.TabFocus`.

### 2.2 Opting out per story

- `story()`, `StoryRegistry.story()` and `Story.__init__` gain a keyword-only parameter after the existing ones,
  `checks_ignore: Mapping[str, str] = {}`, mapping a rule to the reason. `Story.variant` gains
  `checks_ignore: Mapping[str, str] | None = None`, like `layout` and `decorators`, so `None` means "use the base's".
  - Unknown rules and empty reasons raise `ValueError`. Each PR adds the rule names it implements: PR 2 `"name"` and `"focus"`,
    PR 3 `"contrast"`, PR 4 `"snapshot"`, so no rule is accepted before something checks it.
  - The mapping is stored read-only on `Story.checks_ignore` (a new `__slots__` entry).
- **Deviation from the issue.** #34 names the parameter `a11y_ignore`. One mapping serves all four checks (#33, #34 and #35 each ask
  for a per-story opt-out with a reason), so it is named for checks in general. The issue's example becomes
  `@story(..., checks_ignore={"focus": "decorative"})`.
- An ignored rule's item is skipped, and the skip reason is `"<rule> ignored: <reason>"`, so `-rs` and the summary show it.

### 2.3 In the plugin

- `--storybook-a11y` (ini `storybook_a11y`) adds two items per story, `<id>[a11y-name]` and `<id>[a11y-focus]`. Names and focus do
  not depend on the theme, so the items render in the first selected theme. The #34 acceptance run uses
  `--storybook-themes Light,Dark`, as #35's does.
- A failure lists every issue: the rule, then the class, object name and path, then the message.

### 2.4 Examples and tests

- Run both rules on the built-in examples and fix what they find in the examples, not by adding exclusions. Today `name` fails on
  Line Edit (three stories), Spin Box, Double Spin Box, Slider, Table and Combo Box (whose only name is its current text, which the
  combo box rule rejects). Each gets `setAccessibleName` on the widget itself, not a wrapper with a buddy label: tests check that
  the Slider story's preview widget is the `QSlider`, and the Table keeps `Layout.FILL`.
- **Tests:**
  - an icon-only `QToolButton` fails `name`, and `setAccessibleName` fixes it;
  - a `NoFocus` `QPushButton` fails `focus`;
  - a labelled `QLineEdit` with a buddy passes;
  - spin box and combo box internals are not reported;
  - `checks_ignore` skips with the reason;
  - variants inherit `checks_ignore`;
  - the pytester acceptance run: `--storybook --storybook-a11y` passes on the examples and fails, naming the widget, on a story with
    an unnamed icon button.

## 3. Text contrast (#35)

### 3.1 The method (recorded in the issue as the scope asks)

- **Pixels, not palette roles.** Palette roles are wrong for widgets styled by a style sheet and for custom-painted ones.
- **The checked widgets.** The checked root is shown, its focus cleared (§1.4), and rendered once with `QWidget.render` into a
  `QImage` at device pixel ratio 1. For each visible, enabled (§3.2) text-bearing descendant, the check takes a container rectangle:
  - `QLabel` with text and no pixmap: `contentsRect()` with the label's alignment;
  - `QAbstractButton` with text: the style's contents sub-element (`SE_PushButtonContents`, `SE_CheckBoxContents`,
    `SE_RadioButtonContents`);
  - `QLineEdit` with text: `contentsRect()`, left-aligned;
  - `QAbstractSpinBox`: the edit field;
  - `QComboBox`: `SC_ComboBoxEditField`;
  - item views: each visible index's `visualRect` that has display text, up to 50 per view.
- **The text box.** The rectangle sampled is the text's own box inside the container,
  `fontMetrics().boundingRect(container, alignment, text)`, grown by 1 pixel and clipped to the container. Sampling the whole
  container let gradients and borders win: Push Button measured 1.14 and Table 1.62 in Light although their text is readable.
- **Background and text colours.** Within the text box, the background is the most frequent colour. The text colour is the colour
  with the highest `contrast_ratio` against the background among the colours covering at least 3 pixels. There is no share
  threshold: with it, small fonts (an 8 pt label) measured nothing.
- **A box of one colour fails.** When a box holds only one colour, the text is drawn in the background colour (or not at all), and
  the issue's message says so, instead of skipping.
- **Thresholds.** 4.5:1 for normal text and 3:1 for large text. Large text is at least 18 pt, or at least 14 pt and bold; a
  pixel-sized font is converted with the widget's `logicalDpiY()`.
- **Measured on the review's prototype:**
  - `#777777` on `#888888` is 1.26 (fail); black on white is 21 (pass); 7.0 passes and 2.0 fails.
  - 3.19 passes at 18 pt and at 14 pt bold, and fails at 10 pt; 4.61 at 8 pt passes.
  - Hosted as §1.4 describes, the default Color Swatch measures 5.41 in Light and 4.24 in Dark, a real failure in Dark. Choosing
    the text colour from the swatch's RGB alone also fails for translucent colours (3.97 in Dark, 1.59 for a fully transparent one).
    PR 3 fixes the example by blending the swatch colour over the palette's `Window` colour and picking black or white text against
    the result (computed in the example, which imports only PySide6 and the library's public API). PR 3 re-measures every number in
    this section with the hosted rendering and corrects them.
- **Not covered, documented plainly:**
  - progress-bar text, `QGroupBox` titles, placeholder text, and custom-painted text such as the Token Badge;
  - text on gradients or images, and thin anti-aliased text, which give estimates.

### 3.2 API, options and tests

- `pyside6_storybook.checks.check_text_contrast(widget, *, normal=4.5, large=3.0, include_disabled=False) -> list[CheckIssue]`.
  In the plugin, `--storybook-contrast-disabled` (ini `storybook_contrast_disabled`) sets `include_disabled`, the opt-in #35 asks
  for.
  Rule `contrast`. A failure names the widget, the two colours (`#rrggbb`), the measured ratio, the threshold and whether the text
  was large.
- **In the plugin.** `--storybook-a11y` also adds `<id>[<theme>-contrast]` per story and theme, unless the rule is turned off with
  `--storybook-no-contrast` (ini `storybook_contrast = false`), because it is heuristic. The thresholds come from
  `storybook_contrast_normal` and `storybook_contrast_large`. The theme is part of the failure, through the item id.
- **Tests:**
  - synthetic labels: `#777777` on `#888888` fails and the message has the ratio; black on white passes; 7:1 passes and 2:1 fails;
    an 18 pt label passes at 3.2:1 where a 10 pt one fails;
  - disabled widgets are skipped unless `include_disabled`;
  - the built-in examples pass in Light and Dark.
  - System is Qt's palette (offscreen, the Palette story's white on `#308cc6` is 3.69:1), so the examples test and the acceptance run
    pass `--storybook-themes Light,Dark`, and a comment says why.

## 4. Screenshot snapshots (#33)

### 4.1 Capture and baselines

- **Capture.** `adjustSize()` on the root, show its host (§1.4), clear focus, process events, then `QWidget.render` into a `QImage`
  (`Format_ARGB32`) of the host's size at device pixel ratio 1. Without clearing focus, Line Edit/Default gave two different frames
  within 1.5 s (the caret blinks); with it, every example renders byte-identical twice in one process and across two processes, in
  Light and Dark. Rendering into an image fixes the device pixel ratio, whatever the screen's.
  - The plugin does not change the application font. The provider's theme sets it, so a snapshot shows the story as the application
    looks.
  - "Fixed font" in the issue is met by the deterministic theme plus per-platform baselines. Fonts and anti-aliasing differ between
    systems.
- **Baselines.** `<snapshot_dir>/<platform>/<id with "/" replaced by "__">[<theme>].png`. A story that animates (a busy progress
  bar) opts out with `checks_ignore`.
  - `platform` is `sys.platform`.
  - `snapshot_dir` is the ini `storybook_snapshot_dir`, default `tests/storybook_snapshots`, relative to `rootpath`.

### 4.2 Options, comparison and failures

- **Options.** `--storybook-snapshots` (ini `storybook_snapshots`) adds `<id>[<theme>-snapshot]` items.
  `--storybook-update-snapshots` implies it, writes or replaces each baseline, and passes. A missing baseline without the update
  flag fails with "no baseline at <path>; run pytest --storybook --storybook-update-snapshots to create it", and is never created
  silently.
- **Comparison** (`testing/snapshots.py`, on `QImage`, no extra dependency):
  - Different sizes fail.
  - Otherwise a pixel differs when any channel differs by more than `storybook_snapshot_tolerance` (default 0).
  - The item fails when the share of differing pixels exceeds `storybook_snapshot_max_diff` (default 0.0).
  - Equal bytes are a fast path, and rows are compared as bytes before any per-pixel work.
- **On failure:**
  - write `<failures_dir>/<platform>/<name>.actual.png` and `<name>.diff.png`, the diff showing differing pixels in red over a
    faded actual image;
  - the message names both paths, the share and the tolerance;
  - `failures_dir` is the ini `storybook_snapshot_failures`, default `storybook-snapshot-failures` under `rootpath`, and the
    README suggests ignoring it in git.
- **Opt-out.** `checks_ignore={"snapshot": "shows the current time"}` skips the item with the reason.

### 4.3 Docs and tests

- **Docs:** the README describes the recommended setup: one platform in CI as the reference, baselines committed, the update
  command, and the failures folder uploaded as a CI artifact.
- **Tests with pytester:**
  - create a baseline, then match it;
  - a mismatch after changing a colour in a story, with a diff image written and the paths named;
  - a missing baseline;
  - the opt-out;
  - a size change.
- A `full` test renders the examples twice and checks that the images are byte-identical.

## 5. Documentation

- **README:** a new "Testing stories" section covering:
  - enabling the plugin, its options and ini keys;
  - the item ids and kinds;
  - the `render_story` fixture;
  - the checks and `checks_ignore`;
  - snapshots and the recommended CI setup.
- **AGENTS.md:** the structure (`pyside6_storybook_pytest.py`, `testing/`, `checks/`), and a test rule: plugin tests use `pytester`.
- **docs/theming.md:** a provider can be activated again after `deactivate`.

## 6. Pull requests

They are stacked in this order, and each PR asks for "Create a merge commit":

| # | Issue | Branch | Content |
| --- | --- | --- | --- |
| 1 | #32 | `claude/pyside6-storybook-pytest-plugin` | Entry module, the plugin, the fixture, the extra, xdist |
| 2 | #34 | `claude/pyside6-storybook-a11y-checks` | `checks` package, names and focus, `checks_ignore`, example fixes |
| 3 | #35 | `claude/pyside6-storybook-contrast-check` | `check_text_contrast`, its items, the Color Swatch fix |
| 4 | #33 | `claude/pyside6-storybook-snapshots` | Snapshot items, comparison, baselines |

## 7. Review

The open questions of the draft were answered by experiment (pytest 8.0, 8.3.5 and 9.2, pytest-xdist 3.8, PySide6 6.12) and the
answers are folded into §1–§4: the entry module (§1.1), nodeids, collect report and `tryfirst` (§1.3), configuration errors in
`pytest_configure` (§1.2), the warning ignore list (§1.2), focus cleared before checks and snapshots (§1.4), the accessibility
exclusions and the combo box rule (§2.1), the text-box contrast method (§3.1) and the `fallback` field (§1.2).

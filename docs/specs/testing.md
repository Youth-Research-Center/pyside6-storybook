# Testing (milestone 5): design spec

Status: draft. Issues: #32 (pytest plugin), #34 (accessible names and keyboard focus), #35 (text contrast), #33 (screenshot
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

- `pyproject.toml` gains `[project.entry-points.pytest11] pyside6_storybook = "pyside6_storybook.pytest_plugin"` and
  `[project.optional-dependencies] pytest = ["pytest>=8.0", "pytest-qt>=4.4"]`.
- Importing `pyside6_storybook` today imports every module, PySide6 included: about 0.57 s, measured with `python -X importtime`.
  Loading the plugin means importing `pyside6_storybook.pytest_plugin`, which runs the package's `__init__`. The package `__init__`
  therefore becomes lazy:
  - A module-level `__getattr__` (PEP 562) imports a public name from its module on first access.
  - `__all__` is unchanged, and `__dir__` lists it.
  - Imports under `if TYPE_CHECKING:` keep ty and editors seeing the real types.
  - `from pyside6_storybook import story` and every other documented import keep working, and `tests/test_package.py`'s exact
    `__all__` check is unchanged.
- `pyside6_storybook/pytest_plugin/__init__.py` (the entry module) imports only `pytest` and the standard library at module level.
  Everything else is imported inside hook bodies, and only when the plugin is enabled.
- A core test runs `python -c "import pyside6_storybook.pytest_plugin, sys; print(any(m.startswith('PySide6') for m in sys.modules))"`
  in a subprocess (with a timeout) and expects `False`.

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

- **Sources.** The plugin reads `[tool.pyside6-storybook]` from `pyproject.toml` in `config.rootpath`, with
  `resolve_story_sources(targets, examples=False, cwd=rootpath)`. It puts `pythonpath` on `sys.path` with `put_on_sys_path`, as the
  command line does.
  - When neither the plugin options nor `pyproject.toml` name any stories, `resolve_story_sources` falls back to entry points and
    then to the built-in examples. The plugin accepts entry points, but treats the built-in-examples fallback as a usage error:
    "no stories configured: set `storybook_stories` or `stories` in `[tool.pyside6-storybook]`". It never silently tests the
    library's own examples.
  - The examples can still be named explicitly: `--storybook-stories pyside6_storybook.examples`.
- **Configuration errors are usage errors.** An invalid `pyproject.toml` table, a provider that fails to load, or an unknown name in
  `storybook_themes` raises `pytest.UsageError` with the same message the command line prints. The run stops before any test runs.

### 1.3 Collection

- **The QApplication comes first.** On the first collection with the plugin on, the plugin:
  1. sets `QT_QPA_PLATFORM` to `offscreen` unless it is already set;
  2. creates the `QApplication` (or reuses an existing one), before any story module is imported, so a module that builds a widget
     at import time works, as with the command line;
  3. loads the provider, then the stories (`load_stories`), in the same order as the command line.
  pytest-qt's `qapp` fixture reuses an existing `QApplication`, so the two do not conflict.
- **Items.** In `pytest_collection_modifyitems`, the plugin creates a `StorybookCollector` node (a `pytest.Collector` named
  `storybook`, whose parent is the session) and appends its items to `items`.
  - Nodeids look like `storybook::Inputs/Button/Default[Dark]`.
  - The items come in registry order, then theme order, so collection is deterministic, as pytest-xdist requires.
  - `-k Dark`, `-k "Inputs and not Disabled"` and `--lf` work. The last-failed plugin's `pytest_collection_modifyitems` is a
    wrapper that filters after every other implementation has run, so it sees the appended items. The plan's review must confirm
    `-k`, `--lf`, `--co` and `-n 2` with experiments.
- **Kinds of item.** One `StoryItem` per story and theme. The checks of §2–§4 add more kinds:
  - `StoryCheckItem` `[a11y-name]` and `[a11y-focus]`, once per story;
  - `[contrast]`, per story and theme;
  - `[snapshot]`, per story and theme.
  Every item kind is listed in `README.md`.
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
     - the provider's `tokens()` and `color_scheme()` (read with `getattr` and the window's palette heuristic, as the window does).
     The context-building code moves from the window into a shared internal helper (`themes/story_context_factory.py`:
     `build_story_context(story, provider, *, args, actions)`), which both use.
  3. `render_story(story, ctx, registry=registry)` builds the widget and its decorators.
  4. Show the root (offscreen), run `QApplication.processEvents()` twice, then hide it and delete it, flushing `DeferredDelete`.
- **Failures.** A `StoryRenderError` fails the item with its title and details. A failure caused by the story's own code does not
  print a pytest traceback, because `repr_failure` returns the error's text. While the item runs, a Qt message handler collects
  `QtWarningMsg`, `QtCriticalMsg` and `QtFatalMsg`. With `storybook_qt_warnings = fail` the item fails and lists them. The handler
  chains to the previous one, so pytest-qt's capture still works.
- `reportinfo()` returns the story function's file and line, and `"story <id> [<theme>]"`.

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

### 1.6 Tests

- `tests/conftest.py` enables `pytester` (`pytest_plugins = ["pytester"]`).
- New tests in `tests/test_pytest_plugin.py` use `pytester` with in-process runs, and subprocess runs where isolation needs it:
  - a passing project (one item per story and theme, readable ids);
  - a story that raises (the traceback is shown);
  - a story that returns `None`;
  - an import error (a failing `load-error[...]` item);
  - `-k` selection, `--lf`, and a logged Qt warning (fail, and `ignore`);
  - the provider restored after the items and between interleaved tests;
  - the examples fallback as a usage error;
  - the `render_story` fixture (args, theme, unknown id, teardown).
- `pytest-xdist` joins the dev dependencies, and a `full` test runs `-n 2`.
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
  - the internal children of `QAbstractSpinBox` and `QComboBox`.
  The review must run the rules on every built-in example and on the gallery's own widgets, and list any further exclusion it needs,
  with the reason.
- **Rule `name`.** `QAccessible.queryAccessibleInterface(widget).text(QAccessible.Text.Name).strip()` is not empty. This is what a
  screen reader sees: the widget's text, a buddy label's text, or `setAccessibleName`. The review must confirm that
  `queryAccessibleInterface` answers offscreen with no assistive technology active, and say which widget classes need the buddy.
- **Rule `focus`.** `widget.focusPolicy()` includes `Qt.FocusPolicy.TabFocus`.

### 2.2 Opting out per story

- `story()`, `StoryRegistry.story()`, `Story.__init__` and `Story.variant` gain a keyword-only parameter after the existing ones:
  `checks_ignore: Mapping[str, str] = {}`, mapping a rule (`"name"`, `"focus"`, `"contrast"`, `"snapshot"`) to the reason.
  - Unknown rules and empty reasons raise `ValueError`.
  - The mapping is stored read-only on `Story.checks_ignore`.
  - A variant without its own mapping uses its base's, as with layout and decorators.
- **Deviation from the issue.** #34 names the parameter `a11y_ignore`. One mapping serves all four checks (#33, #34 and #35 each ask
  for a per-story opt-out with a reason), so it is named for checks in general. The issue's example becomes
  `@story(..., checks_ignore={"focus": "decorative"})`.
- An ignored rule's item is skipped, and the skip reason is `"<rule> ignored: <reason>"`, so `-rs` and the summary show it.

### 2.3 In the plugin

- `--storybook-a11y` (ini `storybook_a11y`) adds two items per story, `<id>[a11y-name]` and `<id>[a11y-focus]`. Names and focus do
  not depend on the theme, so the items render in the first selected theme.
- A failure lists every issue: the rule, then the class, object name and path, then the message.

### 2.4 Examples and tests

- Run both rules on the built-in examples and fix what they find in the examples, not by adding exclusions.
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
- **The checked widgets.** The checked root is grabbed once with `QWidget.render` into a `QImage` at device pixel ratio 1. For each
  visible, enabled (§3.2) text-bearing descendant, the check samples a text rectangle mapped to the root's coordinates:
  - `QLabel` with text and no pixmap: `contentsRect()`;
  - `QAbstractButton` with text: the style's contents sub-element (`SE_PushButtonContents`, `SE_CheckBoxContents`,
    `SE_RadioButtonContents`, `SE_ToolButton...` as applicable);
  - `QLineEdit` with text: `contentsRect()`;
  - `QAbstractSpinBox`: the edit field;
  - `QComboBox`: `SC_ComboBoxEditField`;
  - item views: each visible index's `visualRect` that has display text, up to 50 per view.
- **Background and text colours.** Within the rectangle:
  - the background is the most frequent colour;
  - the text colour is the colour that, among those covering at least 2% of the rectangle's pixels (and at least 4 pixels), has
    the highest `contrast_ratio` against the background.
  The ratio between the two is compared with the threshold.
- **Thresholds.** 4.5:1 for normal text and 3:1 for large text. Large text is at least 18 pt, or at least 14 pt and bold; a
  pixel-sized font is converted with the widget's `logicalDpiY()`.
- **Limits, documented plainly.** Text on gradients or images, thin anti-aliased text and icons give estimates. A widget whose
  rectangle holds a single colour has no text to measure and is skipped.

### 3.2 API, options and tests

- `pyside6_storybook.checks.check_text_contrast(widget, *, normal=4.5, large=3.0, include_disabled=False) -> list[CheckIssue]`.
  Rule `contrast`. A failure names the widget, the two colours (`#rrggbb`), the measured ratio, the threshold and whether the text
  was large.
- **In the plugin.** `--storybook-a11y` also adds `<id>[<theme>][contrast]` per story and theme, unless the rule is turned off with
  `--storybook-no-contrast` (ini `storybook_contrast = false`), because it is heuristic. The thresholds come from
  `storybook_contrast_normal` and `storybook_contrast_large`. The theme is part of the failure, through the item id.
- **Tests:**
  - synthetic labels: `#777777` on `#888888` fails and the message has the ratio; black on white passes; 7:1 passes and 2:1 fails;
    an 18 pt label passes at 3.2:1 where a 10 pt one fails;
  - disabled widgets are skipped unless `include_disabled`;
  - the built-in examples pass in Light and Dark.
  - System is Qt's palette, so the examples test does not assert it, and a comment says why.

## 4. Screenshot snapshots (#33)

### 4.1 Capture and baselines

- **Capture.** `adjustSize()` on the root, show it, process events, then `QWidget.render` into a `QImage` (`Format_ARGB32`) of the
  root's size at device pixel ratio 1. Rendering into an image fixes the device pixel ratio, whatever the screen's.
  - The plugin does not change the application font. The provider's theme sets it, so a snapshot shows the story as the application
    looks.
  - "Fixed font" in the issue is met by the deterministic theme plus per-platform baselines. Fonts and anti-aliasing differ between
    systems.
- **Baselines.** `<snapshot_dir>/<platform>/<id with "/" replaced by "__">[<theme>].png`.
  - `platform` is `sys.platform`.
  - `snapshot_dir` is the ini `storybook_snapshot_dir`, default `tests/storybook_snapshots`, relative to `rootpath`.

### 4.2 Options, comparison and failures

- **Options.** `--storybook-snapshots` (ini `storybook_snapshots`) adds `<id>[<theme>][snapshot]` items.
  `--storybook-update-snapshots` implies it, writes or replaces each baseline, and passes. A missing baseline without the update
  flag fails with "no baseline at <path>; run pytest --storybook --storybook-update-snapshots to create it", and is never created
  silently.
- **Comparison** (`pytest_plugin/snapshots.py`, on `QImage`, no extra dependency):
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
- **AGENTS.md:** the structure (`pytest_plugin/`, `checks/`, the lazy package `__init__`), and a test rule: plugin tests use
  `pytester`.
- **docs/theming.md:** a provider can be activated again after `deactivate`.

## 6. Pull requests

They are stacked in this order, and each PR asks for "Create a merge commit":

| # | Issue | Branch | Content |
| --- | --- | --- | --- |
| 1 | #32 | `claude/pyside6-storybook-pytest-plugin` | Lazy package init, the plugin, the fixture, the extra, xdist |
| 2 | #34 | `claude/pyside6-storybook-a11y-checks` | `checks` package, names and focus, `checks_ignore`, example fixes |
| 3 | #35 | `claude/pyside6-storybook-contrast-check` | `check_text_contrast` and its items |
| 4 | #33 | `claude/pyside6-storybook-snapshots` | Snapshot items, comparison, baselines |

## 7. Open questions for the review

1. Do `-k`, `--lf`, `--co`, `-n 2` and `-p no:cacheprovider` work with items appended under a session-parented collector? If not,
   what is the smallest change (a `pytest_collect_directory`/`pytest_collect_file` hook, a virtual file node) that makes them work?
2. Does a lazy `__init__` keep `from pyside6_storybook import X`, `ty check`, the docs and `tests/test_package.py` working, and how
   much does it save? Is a separate top-level module simpler?
3. Does `QAccessible.queryAccessibleInterface` give names offscreen? Which of the example widgets fail `name` or `focus` today?
4. Does the contrast method pass the built-in examples in Light and Dark and fail the synthetic `#777777`/`#888888` label? What
   share threshold and minimum pixel count avoid false positives from anti-aliasing?
5. Are two consecutive offscreen renders of each example byte-identical with `QWidget.render` into a `QImage`?

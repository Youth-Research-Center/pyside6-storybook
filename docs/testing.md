# Testing stories

The `pytest` extra adds a pytest plugin that renders every story in every theme as a test, and a `render_story` fixture for tests you
write yourself.

```bash
pip install "pyside6-storybook[pytest]"      # or: uv add --dev "pyside6-storybook[pytest]"
pytest --storybook
```

The extra installs `pytest` and `pytest-qt`. The plugin is registered with pytest through an entry point, and it does nothing, and
imports neither Qt nor the library, unless you turn it on with `--storybook` or `storybook = true` in the pytest ini options.

## What runs

Each story and theme is one test, and its id is `storybook::<story id>[<theme>]`, for example `storybook::Inputs/Button/Default[Dark]`.
A test builds the story's widget from the story's default arguments (a variant's included), inside the theme, shows it offscreen and
deletes it. It fails when:

- the story or one of its decorators raises, or the story does not return a `QWidget`: the report shows the story's own traceback;
- the theme provider fails (a `tokens()` that raises, for one);
- Qt logs a warning, a critical or a fatal message while it renders, unless an ignore pattern matches it (see below).

A story file that fails to import is a failing test too, `storybook::load-error[<file>]`, and the other stories still run. A theme provider that
cannot be loaded, an unknown theme in `storybook_themes`, or a project with no story at all gives one failing test,
`storybook::configuration`, with the reason, and no story tests. Every test carries the `storybook` marker, so
`pytest -m "not storybook"` runs your other tests alone, even with `storybook = true` in the ini options, which adds the story tests to
every run.

The widget is shown inside an opaque host widget painted with the palette's `Window` colour, as the gallery's preview is, and focus is
cleared after it is shown, so a line edit does not keep a blinking caret. The offscreen platform is the default: the plugin sets
`QT_QPA_PLATFORM=offscreen` unless it is already set.

## Options

Every setting has a command-line option and an ini option (`pytest.ini`, `pyproject.toml` under `[tool.pytest.ini_options]`, ...), and
the command line wins. While the plugin is off, a command-line option that only shapes the story tests (`--storybook-themes`,
`--storybook-qt-warnings`, `--storybook-a11y`, the contrast and snapshot options) is a usage error that asks for `--storybook`, so
`pytest --storybook-update-snapshots` alone does not silently update nothing. `--storybook-stories`, `--storybook-theme-provider` and
the ini options are accepted, for the `render_story` fixture and for a project that turns the plugin on with `--storybook` only in CI.

- `--storybook`, ini `storybook` (a bool): turn the plugin on.
- `--storybook-stories TARGET` (repeatable), ini `storybook_stories` (one target per line): the folders, files and dotted module names
  to load, as on the gallery's command line. Default: `stories` in `[tool.pyside6-storybook]`.
- `--storybook-theme-provider SPEC`, ini `storybook_theme_provider`: the `module:attribute` of your theme provider. Default:
  `theme_provider` in `[tool.pyside6-storybook]`, else the built-in themes.
- `--storybook-themes NAMES`, ini `storybook_themes`: comma-separated themes to render each story in. Default: every theme the
  provider lists (the built-in ones are Light, Dark and System).
- `--storybook-a11y`, ini `storybook_a11y` (a bool): also check names and keyboard focus (see [Accessibility checks](#accessibility-checks)).
- `--storybook-no-contrast`, ini `storybook_contrast` (a bool, default true): with `--storybook-a11y`, leave out the text-contrast tests.
- ini `storybook_contrast_normal` (default `4.5`) and `storybook_contrast_large` (default `3`): the contrast ratios, from 1 to 21,
  that normal and large text need.
- `--storybook-contrast-disabled`, ini `storybook_contrast_disabled` (a bool): also check the text of disabled widgets.
- `--storybook-snapshots`, ini `storybook_snapshots` (a bool): also compare a screenshot of every story and theme with its baseline (see
  [Screenshot snapshots](#screenshot-snapshots)). `--storybook-update-snapshots` writes the baselines instead and implies it.
- ini `storybook_snapshot_dir` (default `tests/storybook_snapshots`) and `storybook_snapshot_failures` (default
  `storybook-snapshot-failures`): the folders of the baselines and of the images of a failure, relative to pytest's rootdir.
- ini `storybook_snapshot_tolerance` (default `0`, a whole number from 0 to 255) and `storybook_snapshot_max_diff` (default `0`, from 0 to 1):
  how far a colour channel may differ, and what share of the pixels may differ, before a snapshot fails.
- `--storybook-qt-warnings {fail,ignore}`, ini `storybook_qt_warnings`: whether a Qt warning logged during a render fails the test.
  Default `fail`.
- ini `storybook_qt_warnings_ignore` (one regular expression per line, no command-line option): the warnings that never fail a test; a
  pattern is searched in the message. Default: `propagateSizeHints`.

The offscreen platform logs "This plugin does not support propagateSizeHints()" when some widgets are shown, so that message is
ignored by default. Setting `storybook_qt_warnings_ignore` replaces the default, so list it again if you still want it ignored.

The stories come from `storybook_stories`, or else from `[tool.pyside6-storybook]` in the `pyproject.toml` next to pytest's rootdir,
with its `pythonpath` put on `sys.path` as the gallery does. If nothing names them, the plugin reports a usage error instead of testing
the library's built-in examples; name them explicitly with `--storybook-stories pyside6_storybook.examples` if you want that. A
malformed option or `pyproject.toml` table is a usage error (exit code 4) before anything is collected.

```toml
[tool.pytest.ini_options]
storybook = true
storybook_themes = "Light,Dark"
storybook_qt_warnings_ignore = [
    "propagateSizeHints",
    "QFont::setPointSize: Point size <= 0",
]
```

## Accessibility checks

`--storybook-a11y` adds two tests per story, `storybook::<story id>[a11y-name]` and `storybook::<story id>[a11y-focus]`. They do not
depend on the theme, so each renders the story once, in the first selected theme. A failing test lists every issue with the rule, the
widget's class and object name, its path (the class names from the story's outermost widget down, with the index among siblings of the
same class: `QWidget/QGroupBox[0]/QToolButton[1]`) and what to do.

- `name`: every visible, enabled control has an accessible name, the text a screen reader announces: the widget's text, a buddy label's
  text, or `setAccessibleName`. A tooltip is not a name, and a combo box's current text does not count (it needs `setAccessibleName` or a
  buddy label). Buttons, line and text edits, spin boxes, combo boxes, sliders, item views, tab bars and anything that takes focus with
  Tab are controls; the tabs of a `QTabWidget` are checked through their texts.
- `focus`: the same controls take focus with the Tab key (their focus policy includes `TabFocus`).

The internals of composite widgets are not checked: the line edit of a spin box or an editable combo box, the headers, scroll bars and
viewport of an item view, a tab widget's tab bar, the clear button of a line edit. A `QScrollArea` is a container, so its content is
checked, not the area.

- `contrast`: the text is readable against what is drawn behind it (see [Text contrast](#text-contrast) below).

A story opts out of a rule with `checks_ignore`, a mapping from the rule to the reason; the test is then skipped and `-rs` shows
`name ignored: decorative icon`. A variant has its base's `checks_ignore` unless it passes its own.

```python
from PySide6.QtWidgets import QLabel, QWidget

from pyside6_storybook import StoryContext, story


@story("Icons/Close", checks_ignore={"name": "decorative: the label next to it names the action"})
def close_icon(ctx: StoryContext) -> QWidget:
    return QLabel("\u00d7")
```

The checks are plain functions in `pyside6_storybook.checks`, so a test of your own can run them on any widget:
`check_accessible_names(widget)` and `check_keyboard_focus(widget)` return a list of `CheckIssue` (`rule`, `widget_class`,
`object_name`, `path`, `message`), empty when the widget passes.

<!-- docs-test: skip — builds the reader's own widget with build_toolbar and needs the qtbot fixture -->
```python
from pyside6_storybook.checks import check_accessible_names


def test_the_toolbar_is_named(qtbot):
    toolbar = build_toolbar()
    qtbot.addWidget(toolbar)
    toolbar.show()

    assert [str(issue) for issue in check_accessible_names(toolbar)] == []
```

## Text contrast

`--storybook-a11y` also adds `storybook::<story id>[<theme>-contrast]` for every story and theme, which renders the story and checks
that its text has enough contrast against its background (WCAG AA: 4.5:1, or 3:1 for large text, which is at least 18 pt, or at least
14 pt and bold). Light and Dark are checked by their own tests, so a failure names the theme. Turn the tests off with
`--storybook-no-contrast`, change the ratios with `storybook_contrast_normal` and `storybook_contrast_large`, and opt a story out with
`checks_ignore={"contrast": "reason"}`. System is Qt's own palette, so list the themes you want with `--storybook-themes Light,Dark`
when the application's own palette is not the one you ship.

The check measures pixels, not palette roles, because the palette is wrong for widgets that a style sheet colours and for custom
painting. The story is shown and rendered once into an image, with text in greyscale anti-aliasing even where the system draws
subpixel (coloured) text, so the colours measured are the text's own. For each visible, enabled widget with text, the check takes the box of
the text itself inside the widget's text area: the most frequent colour in it is the background, and among the colours that cover at
least 3 pixels, the one with the highest contrast against it is the text. A box that holds a single colour fails, because the text is
drawn in the background colour or not at all. A failure names the widget, the two colours as `#rrggbb`, the measured ratio, the
threshold and whether the text is large. Disabled widgets are skipped (their text is faint by design) unless you pass
`--storybook-contrast-disabled`.

It checks labels without a pixmap, buttons, line edits, spin boxes, combo boxes and up to 50 visible items of each list, table and
tree. It does not check progress-bar text, group box titles, header text, placeholder text or text that a widget paints itself (a
custom `paintEvent`), and text that is cut off by a scroll area is skipped. Text on a gradient or an image, and thin anti-aliased text
(small sizes), give an estimate, so treat a result near the threshold as a hint.

`check_text_contrast(widget, *, normal=4.5, large=3.0, include_disabled=False)` runs it on any shown widget and returns a list of
`CheckIssue`, empty when the text passes:

<!-- docs-test: skip — builds the reader's own widget with build_banner and needs the qtbot fixture -->
```python
from pyside6_storybook.checks import check_text_contrast


def test_the_banner_is_readable(qtbot):
    banner = build_banner()
    qtbot.addWidget(banner)
    banner.show()
    qtbot.waitUntil(banner.isVisible, timeout=5000)

    assert [str(issue) for issue in check_text_contrast(banner)] == []
```

The widget's window is rendered, so show it first, and clear the focus if a focus ring would cover text.

## Screenshot snapshots

`--storybook-snapshots` adds `storybook::<story id>[<theme>-snapshot]` for every story and theme, after the story's other tests. The test
renders the story as the other tests do (an exception or a Qt warning fails it), takes a screenshot of the host widget and compares it with
a baseline PNG. The screenshot is rendered into an image at device pixel ratio 1, after the focus is cleared so that no caret blinks, so the
same story gives the same image twice. The plugin does not change the application's font: the theme provider sets it, so a snapshot shows the
story as your application looks.

Baselines are files you commit: `<storybook_snapshot_dir>/<platform>/<story id with / replaced by __>[<theme>].png`, where the platform is
`sys.platform` (`linux`, `win32` or `darwin`), for example `tests/storybook_snapshots/linux/Inputs__Button__Default[Dark].png`.

```bash
pytest --storybook --storybook-update-snapshots   # write or replace every baseline; the tests pass
pytest --storybook --storybook-snapshots          # compare
```

A snapshot test fails when there is no baseline (it never creates one silently; the message tells you the update command), when the image has
another size, or when the share of differing pixels is above `storybook_snapshot_max_diff`. A pixel differs when a channel differs by more
than `storybook_snapshot_tolerance`. A failure writes `<name>.actual.png` and `<name>.diff.png` (the differing pixels in red over a faded
copy of the actual image) to `<storybook_snapshot_failures>/<platform>/` and names both files, the baseline, the share of differing pixels
and the tolerance. A passing run deletes the images of an earlier failure. Open the three images side by side to see what changed, and run the
update command to accept it. A story that animates or shows the time opts out with `checks_ignore={"snapshot": "shows the current time"}`.

Fonts and anti-aliasing differ between systems, so a baseline made on one machine fails on another. Use one platform as the reference:

- Make the baselines on the machine that CI uses, or in the same image, and commit them. A developer on another platform runs
  `pytest --storybook` without `--storybook-snapshots`, or sets a `storybook_snapshot_dir` for the platform.
- Install the same fonts everywhere (on a Linux runner, one package such as `fonts-dejavu-core`), or a theme provider that sets the font.
- Add the failures folder to `.gitignore` and upload it from CI, so that a failed run shows you the images:

```gitignore
storybook-snapshot-failures/
```

```yaml
      - name: Test the stories
        run: pytest --storybook --storybook-snapshots
        env:
          QT_QPA_PLATFORM: offscreen
      - name: Upload the snapshot failures
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: storybook-snapshot-failures
          path: storybook-snapshot-failures/
          if-no-files-found: ignore
```

## Selecting tests

`-k`, `--deselect`, `-m` and `--lf` work on the story tests as on any others:

```bash
pytest --storybook -k Dark                          # one theme
pytest --storybook -k "Inputs and not Disabled"     # by story name
pytest --storybook --deselect "storybook::Inputs/Button/Default[Dark]"
pytest --storybook --lf                             # the tests that failed last time
pytest --storybook --collect-only -q                # list the ids
```

A story id is not a path, so a `storybook::...` id cannot be given as an argument (pytest answers "file or directory not found"); select
with `-k` or `--deselect`.

## Things to know

- **The `QApplication`.** The plugin creates it (or reuses an existing one) before it imports any story, so a story module that builds
  a widget at import time works, as it does under the command line. pytest-qt's `qapp` fixture reuses it, and the plugin's
  `QApplication` ignores `qapp_cls`, `qapp_args` and `qt_qapp_name`.
- **pytest-qt is optional for the story tests.** An exception raised in a Qt virtual method (a `paintEvent`, for one) or a slot while a
  story renders fails its test with the story's traceback, with or without pytest-qt. The `render_story` fixture needs pytest-qt.
- **The theme provider is activated lazily** before the first story test and deactivated when the next test is not a story test and at
  the end of the run, so the application's look is back before any other test runs. A provider can be activated again after
  `deactivate`; see [the provider contract](themes.md#the-contract).
- **pytest-xdist.** The story tests are collected in the same order in every worker. With `-n`, the default `load` distribution spreads
  them over the workers; `--dist loadfile` and `--dist loadscope` put all of them on one worker.
- **Stories imported earlier.** The plugin loads the stories into a new registry when it collects. A story module that something else
  already imported at module level (a test module or a `conftest.py`) is not executed again, so its stories cannot be tested; the run
  reports it as a failing `load-error[<module>]` test that names the stories. Import story modules inside the tests that use them.

## The `render_story` fixture

For a test that does more than render, `render_story` builds a story's widget and returns it, shown:

```python
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton


def test_a_disabled_button_stays_disabled(render_story, qtbot):
    button = render_story("Inputs/Button/Default", args={"enabled": False}, theme="Dark")

    assert isinstance(button, QPushButton)
    assert not button.isEnabled()
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)  # nothing happens
```

`render_story(story_id, *, args=None, theme=None)` returns the story's own widget, without the decorators' wrappers. `args` replaces
some default arguments, converted by the story's controls; an unknown name raises `KeyError`, and so does an unknown story id, listing the
closest ids. `theme` activates the theme provider for the test and switches to that theme; the provider is deactivated afterwards. Without
`theme` the widget is rendered in the application's current look, and the context has no design tokens. Everything the fixture rendered is
hidden and deleted at teardown. The fixture works without `--storybook`, loads the same stories lazily, and needs pytest-qt: without it
the test fails with "render_story needs pytest-qt: install pyside6-storybook[pytest]".

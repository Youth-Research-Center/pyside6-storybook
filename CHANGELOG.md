# Changelog

All notable changes to this project are documented in this file. The format follows
[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/), and the project follows [Semantic Versioning](https://semver.org/). The
[Versions and compatibility](https://youth-research-center.github.io/pyside6-storybook/versions/) page says what counts as the public API.

Every user-facing pull request adds one entry under `[Unreleased]`, below the matching heading: `### Breaking`, `### Added`,
`### Changed`, `### Fixed`, `### Removed`, `### Deprecated` or `### Security`. `### Breaking` comes first, and a minor release before 1.0
that breaks the public API lists the break there. A release section is named `## [X.Y.Z] - YYYY-MM-DD`; release candidates get no section
of their own.

## [Unreleased]

## [0.1.0] - 2026-11-19

### Added
- `pyside6-storybook --debug-info` prints the versions of pyside6-storybook, PySide6, Qt, Python and the platform for a bug report.
- Version policy: the documentation page Versions and compatibility says what the public API is, what a minor and a patch release before
  1.0 may change, and which Python and PySide6 versions are supported. `RELEASING.md` describes how a release is made. The changelog header
  states the format, and `### Breaking` is the first heading of a release that breaks the public API.
- Documentation site (MkDocs with Material and mkdocstrings) at https://youth-research-center.github.io/pyside6-storybook/: a home page, a page
  for each part of the guide (writing stories, controls, finding stories, the command line, the gallery, themes, testing stories and
  troubleshooting), the API reference generated from the docstrings, the changelog and the roadmap. The README is now a short front page that
  links to them. The `docs` dependency group installs the generator;
  `docs.yml` builds it with `mkdocs build --strict` and deploys it to GitHub Pages from `main`.
- PyPI metadata: the licence files (`LICENSE`, `THIRD_PARTY_NOTICES.md`), authors, keywords, classifiers (Python 3.11 to 3.14, Pytest,
  Typed) and the project URLs (homepage, documentation, repository, issues, changelog). The sdist has an explicit include list: the package,
  the tests with the workflows they read, the docs and the scripts, without `docs/specs/` and `.github/dependabot.yml`.
- Screenshot snapshots: `pytest --storybook-snapshots` (ini `storybook_snapshots`) adds `storybook::<id>[<theme>-snapshot]` for every story and
  theme, which compares a screenshot of the rendered story with the baseline
  `tests/storybook_snapshots/<platform>/<id with / as __>[<theme>].png`. `--storybook-update-snapshots` writes or replaces the baselines; a
  missing baseline fails and is never created silently. A mismatch (another size, or more differing pixels than `storybook_snapshot_max_diff`,
  where a pixel differs when a channel differs by more than `storybook_snapshot_tolerance`) writes the actual and diff images to
  `storybook-snapshot-failures/<platform>/` and names them. `storybook_snapshot_dir` and `storybook_snapshot_failures` move the folders.
  `checks_ignore` accepts `"snapshot"`. See Screenshot snapshots in the Testing stories page of the documentation.
- Text contrast check: `pyside6_storybook.checks.check_text_contrast(widget, *, normal=4.5, large=3.0, include_disabled=False)`
  renders a shown widget and returns a `CheckIssue` for each text (labels, buttons, line edits, spin boxes, combo boxes and items of
  item views) whose contrast against its background, measured on the pixels, is below 4.5:1 (3:1 for large text). `pytest
  --storybook-a11y` runs it as `storybook::<id>[<theme>-contrast]` for every story and theme; `--storybook-no-contrast` (ini
  `storybook_contrast = false`) turns it off, `storybook_contrast_normal` and `storybook_contrast_large` set the ratios, and
  `--storybook-contrast-disabled` (ini `storybook_contrast_disabled`) includes disabled widgets. `checks_ignore` accepts `"contrast"`.
  See Text contrast in the Testing stories page of the documentation.
- Accessibility checks: `pyside6_storybook.checks` has `check_accessible_names(widget)` and `check_keyboard_focus(widget)`, which return
  a `CheckIssue` (`rule`, `widget_class`, `object_name`, `path`, `message`) for each control without an accessible name or without Tab
  focus. `pytest --storybook-a11y` (ini `storybook_a11y`) runs them on every story as `storybook::<id>[a11y-name]` and
  `storybook::<id>[a11y-focus]`. `story()`, `StoryRegistry.story()`, `Story` and `Story.variant()` take `checks_ignore`, a mapping from
  a rule (`"name"` or `"focus"`) to the reason the story opts out; the test is skipped with that reason, and a variant inherits it.
- pytest plugin: install the `pytest` extra (`pyside6-storybook[pytest]`, which adds `pytest` and `pytest-qt`) and run `pytest --storybook`
  (or set `storybook = true`) to render every story in every theme as one test, `storybook::<story id>[<theme>]`, which fails when the
  story or a decorator raises (with the story's own traceback, also from a `paintEvent` or a slot, with or without pytest-qt), the
  story returns no widget, the theme provider fails, or Qt logs a
  warning (`--storybook-qt-warnings`, `storybook_qt_warnings_ignore`; `propagateSizeHints` is ignored by default). A story file that
  fails to import, or was imported before collection so its stories cannot be tested, is a failing
  `storybook::load-error[...]` test, a provider or theme that cannot be used is a failing
  `storybook::configuration` test, and a project without configured stories is a usage error instead of testing the built-in examples.
  Options and ini keys: `--storybook-stories`, `--storybook-theme-provider`, `--storybook-themes`. The tests carry the `storybook`
  marker and work with `-k`, `--deselect`, `--lf` and pytest-xdist. The new `render_story(story_id, *, args=None, theme=None)` fixture
  renders a story by id in a test you write yourself. The plugin imports neither Qt nor the library unless it is enabled, and an option
  that only shapes the story tests is a usage error while it is off (#94).
  `StorySources` has the keyword-only `fallback`, true for the built-in examples fallback. See Testing stories in the documentation.
- Theming guide (now the Themes page of the documentation, `docs/themes.md`), with two screenshots (rendered by
  `scripts/docs/render_theming_images.py`), and the worked example `examples/themed_app`: an application with two themes, a pill
  button, a token-painted gauge and a `ThemeProvider` for them. Run it from
  its folder with `uv run --project ../.. pyside6-storybook`.
- Choosing a theme provider: `--theme-provider module:attribute` on the command line, or `theme_provider = "module:attribute"` in
  `[tool.pyside6-storybook]`, loads an application's own `ThemeProvider` (an instance, a class or a no-argument function; the attribute
  may be dotted), and `theme` in `pyproject.toml` chooses the starting theme like `--theme`. The command line wins. The provider is
  loaded before the stories, an error in it or an unknown theme exits with code 1 and never falls back to the built-in themes, and
  `--list` names the provider and its themes on standard error without activating it. A reload keeps the provider's modules (and those
  it imports in `activate`) instead of re-importing them, so the stories and the provider share the application's theme manager;
  restart the gallery after editing the provider.
- System theme: `BuiltinThemeProvider` has a third theme, System, which restores the style, palette and style sheet the application had
  when the gallery started and lets the colour scheme follow the operating system (unless the application forced one), including a
  change while the gallery runs. `Ctrl+T` cycles Light, Dark, System. `StoryContext.color_scheme` (a `Qt.ColorScheme`, `Unknown` by
  default) tells a story whether the theme is light or dark; a provider supplies it with an optional `color_scheme()` method, and the
  gallery guesses from the application palette without one. On the offscreen platform and where Qt has no colour-scheme setting, System
  is whatever Qt defaults to.
- Design tokens: `StoryContext.tokens` is a read-only mapping of the active theme's tokens, empty by default. A theme provider supplies
  it through an optional `tokens()` method, which the gallery reads after activation and after every change notification (a provider
  without it, or one that raises, gives an empty mapping). `BuiltinThemeProvider.tokens()` returns twelve `#rrggbb` colours read from the
  application palette (`window`, `accent`, `border` and others), and the new `Display/Token Badge` example paints a widget from them.
- Theme providers: the new `ThemeProvider` protocol lets an application supply its own themes to the gallery (`theme_names`, `current_theme`,
  `activate`, `set_theme`, `on_changed`, `deactivate`), and `BuiltinThemeProvider` is the default Light and Dark provider. `run`, which
  opens the gallery, is now exported from the package and takes the keyword-only `theme_provider`; it validates `theme` against the
  provider's names and logs a warning for each of the application's style, palette, style sheet and font that the provider did not
  restore. The theme switch lists the provider's names, and an exception from the provider is shown in the preview instead of closing
  the gallery.
- Keyboard navigation and accessibility: Tab follows reading order (search, tree, preview tabs, canvas controls, the preview, then the
  theme switch, the side tabs and the controls), `F6` and `Shift+F6` move between the three panes and return to the widget that had
  focus there, `Ctrl+Alt+Down` and `Ctrl+Alt+Up` open the next and previous story in the list, and `Ctrl+T` switches to the next
  theme. A Help menu has "Keyboard shortcuts" (`F1`), a dialog that lists every shortcut of the window. The panes are named "Story
  list", "Preview" and "Controls and actions", and the preview area "Preview of <story id>". A rebuilt preview never takes focus
  from the control being edited, and when focus was inside the story's own widget it moves to the preview area.
- Hot reload: the gallery loads the stories again when a story file or a module of the project changes, so an edit shows without a restart.
  It drops the project's modules and loads the targets into a fresh registry; a reload that finds no story, or in which a source fails
  that was not already failing, is rejected and leaves the previous stories in place, with the errors in the preview. After a good reload
  the selected story (or the one now at its position) and its control values stay, a status bar shows "Reloaded HH:MM:SS" or "Reload
  failed HH:MM:SS: ...", and `LoadResult.modules` lists a dotted-name target itself, including a package. `--no-reload` turns it
  off, and `--list` never reloads.
- Actions panel: the side pane has "Controls" and "Actions" tabs. A story shows what happens to its widget with
  `ctx.log_signal(button.clicked)` (the signal's name, or `name=`) or `ctx.log("name", *args)`; each emission is a row with the time, the
  action and its arguments (`QPushButton.clicked` delivers none, `valueChanged` delivers the value), newest first, at most 500 rows, with
  a Clear button and an "N actions logged" count that is announced to assistive technology. The log clears when another story is
  selected and stays when the same story is built again. Both methods do nothing under a plain `StoryContext`. New public `ActionSink`
  (the protocol behind `StoryContext.actions`), exported from the package; `StoryContext` gains the keyword-only `actions` field, which
  does not take part in equality or `repr`. The push button and slider examples log their signals.
- Zoom: buttons for zoom out, zoom in and reset in the canvas toolbar, with the level (50, 67, 100, 150, 200, 300 and 400%) between them,
  the shortcuts `Ctrl++`, `Ctrl+=`, `Ctrl+-` and `Ctrl+0` while focus is in the preview pane, and `Ctrl`+wheel, also over the story's
  own widgets. A level that would need more than 64 million pixels is skipped. At 100% the live
  widget is shown as before; at another level the preview is an image of the widget scaled without smoothing, which is not interactive,
  and a line says so.
- Canvas controls: a Background menu (Window, Base, Alternate Base or Checkerboard) and a Size menu (Fit, Phone portrait 320 by 480,
  Phone landscape 480 by 320, Dialog 800 by 600, the registry's presets, or a Custom width and height) above the preview. With a size
  selected, the area a story is placed in is exactly that size, and the preview scrolls when it does not fit. The choices stay while
  the story, the theme or the registry changes. New public `SizePreset(name, width, height)`, exported from the package, and
  `StoryRegistry.size_presets`, the list of presets the Size menu shows after the built-in sizes; the window reads it when it is built and in
  `GalleryWindow.set_registry`, and a size whose preset is gone returns to Fit.
- The Docs tab: the preview pane has "Canvas" and "Docs" tabs. Docs shows the story module's and the story's docstrings, a table of the
  controls (type, starting value, range or options), links to the stories of the same component, and the story's source with a Copy
  button. `Story.function` is the callable the story was created with, as a read-only property.
- The story list is a tree built from the story ids, with a search field that keeps the stories whose id contains the text, a
  placeholder when nothing matches, and the shortcuts `Ctrl+F` and `/` that focus the search. `GalleryWindow.select_story(story_id)`
  opens a story, clearing the search if it hides the story, and `GalleryWindow.set_registry(registry, *, load_errors=())` shows another
  set of stories, keeping the selected story and its control values when it still exists.
- Story decorators: `decorators=` on `@story` and `Story.variant()` takes functions that wrap the story's widget, the first one outermost
  (`decorators=[padding(24), fixed_size(320, 200)]` is a 320 by 200 widget inside 24 pixels of padding). `StoryRegistry.decorators` wraps
  every story of a registry, outside the story's own, and a variant keeps its story's decorators unless it gives a list. The built-ins
  `padding`, `frame` and `fixed_size` are in `pyside6_storybook.decorators`, and `Decorator` is exported from the package. A decorator
  that fails, or does not return a widget containing the widget it received, shows an error in the preview that names it. `Story` gains
  `decorators`, and `GalleryWindow.current_preview_widget()` still returns the story's own widget. The sign-in form example uses `padding`.
- Preview layouts: `layout=` on `@story` and `Story.variant()` takes a `Layout` (`CENTERED`, `PADDED` or `FILL`) or its string value, and
  `StoryRegistry.default_layout` (`Layout.PADDED` by default) applies to stories that declare none; a variant keeps its story's layout
  unless it gives another. The preview scrolls a widget larger than the pane in `PADDED` and `CENTERED`, and `FILL` grows the widget
  with the pane. `Layout` is exported from the package. Example stories show all three (`Display/Table` fills the preview).
- `ColorControl` (a hex string default, `alpha=True` for `#RRGGBBAA`; the story receives a `QColor`), `EnumControl` (a Python or Qt enum
  member; `options` lists the named members) and `FileControl` (the story receives a `Path`, or `None` while empty; `filter=` is the
  Browse dialog's name filter), with editors in the gallery and example stories.
- Story variants: `Story.variant(name, *, args=None)` registers the same story with other starting values under the id
  `<component>/<name>`, and `Story` gains `component`, `variant_of` and `args` (a read-only mapping). `Story.default_args()` uses a variant's
  `args`, and the gallery shows variants as stories of their own.
- Control options: `label` and `description` on every control (the form label and the editor's tooltip and accessible description),
  `TextControl(multiline=True)`, `IntControl(step=..., slider=True)` and `FloatControl(step=..., decimals=..., slider=True)`. Every control
  also has a read-only `display_label`, a `coerce(value)` method that returns the value in the control's type or raises `ValueError` or
  `TypeError` naming the control, and `FloatControl` has the read-only `effective_step`, `effective_decimals` and `slider_steps`.
- In the gallery, spin boxes, sliders and combo boxes only react to the mouse wheel while they have keyboard focus, and the controls
  pane scrolls when a story has many controls.
- Story model: `story` decorator, `Story`, `StoryContext`, `StoryRegistry`, `default_registry` and the `TextControl`, `BoolControl`,
  `ChoiceControl`, `IntControl` and `FloatControl` controls.
- Gallery window with a story list, a preview, a theme switch and a controls panel.
- Built-in Light and Dark themes.
- The gallery shows a story that raises, or returns something that is not a widget, as an error in the preview with its traceback
  (starting at the story's own code) instead of failing, and lists story sources that failed to load under a "Load errors" entry.
  `run()` and the command line pass the load errors to it.
- `load_stories` imports story modules from folders (`*_story.py` and `*_stories.py` files), single files and dotted module names, and
  returns a `LoadResult` with the registry, the loaded modules and a `LoadError` for each source that failed. `LoadError.target_error` tells
  a target that does not exist apart from a story module that failed to import.
- `pyside6-storybook` command (also `python -m pyside6_storybook`): `pyside6-storybook TARGET...` opens the gallery with the stories in the
  given folders, files or modules; `--list` prints the story ids without opening a window, also without a display; `--theme` picks the
  starting theme. Story modules that fail to import are reported and the gallery opens with the rest; a target that does not exist, or no
  stories at all, exits with code 1.
- Default story sources: run without targets, `pyside6-storybook` loads the `stories` listed under `[tool.pyside6-storybook]` in
  `pyproject.toml` (with an optional `pythonpath`), then the modules advertised by installed packages under the
  `pyside6_storybook.stories` entry-point group, and only when neither is configured the built-in examples. `--list` says on standard
  error which source it used.
- Example stories built from stock Qt widgets (buttons, inputs, display widgets, the active palette and a small form), shown by
  `pyside6-storybook --examples`.

### Changed
- The Color Swatch example chooses black or white text against the swatch colour blended over the window colour, so its text reaches
  4.5:1 for opaque and translucent colours in Light and Dark (the default colour measured 4.24:1 in Dark).
- The built-in examples set accessible names on the Line Edit, Spin Box, Double Spin Box, Combo Box, Slider and Table widgets, so they
  pass the accessibility checks.
- `--theme` no longer limits its value with argparse: an unknown name prints an error and exits with code 1 (was 2) after the theme
  provider has loaded, and the valid names are the provider's. `pythonpath`, `theme_provider` and `theme` in `pyproject.toml` are read
  also when the command line names targets, so an invalid `pyproject.toml` is an error then too (it was ignored).
- The Light theme's `Highlight` and `Accent` are `#1F5FC4` (was `#2A6FDB`). Fusion draws the focus ring in a colour derived from
  `Highlight`, which was `#5391ED` and reached only 2.77:1 against the Light `Window`; the ring is now `#194C9D` (7.2:1), and
  selected text on the highlight is 6.0:1. The Dark theme's ring was already above 3:1 and its colours are unchanged.
- The Docs tab's controls table and source view get their height from their rows and lines instead of a fixed pixel height, so they
  follow the application font.
- The story list is no longer a flat list of ids: stories are grouped by the segments of their ids, and a component below the top level
  with a single story is shown as that story's row.
- The error panel shows a warning icon beside its title. The gallery now bundles Phosphor Icons (MIT) and tints them from the active
  palette, so the icon follows the theme.
- The example stories `Buttons/Push Button` and `Inputs/Line Edit` are now `Buttons/Push Button/Default` and `Inputs/Line Edit/Default`,
  each with variants.
- A control's default must have the control's value type: `BoolControl` takes only a `bool`, `IntControl` an `int` (not a `bool`),
  `FloatControl` an `int` or `float` (not a `bool`), `TextControl` and `ChoiceControl` a string. `Story.default_args()` returns each
  default passed through the control's `coerce`, so a `FloatControl` default given as `1` starts as `1.0`.
- `FloatControl` rejects a default or bound that needs more than 10 decimals, which the editor used to show rounded.
- The gallery's widgets are styleable from an application style sheet. Their object names now have the prefix `sbk` in camel case
  (`storySidebar` is `sbkStorySidebar`, `previewSurface` is `sbkPreviewSurface`, and so on; the Themes page of the
  documentation lists all 53), so a style
  sheet or a test that looked a widget up by its old name must use the new one. The widgets that an application might style, and none that
  contain a story's widget, carry the property `sbkChrome`, so `*[sbkChrome="true"] QPushButton` reaches the gallery's buttons and not
  a story's. The selected story's text stays readable when a style sheet colours the selected row.

### Fixed
- Calling `run()` again in the same process with a theme provider that sets a style sheet crashed Qt: `run()` now deletes its window
  before the provider restores the application's look.
- The package no longer installs PySide6 6.12.0 on Python 3.11. That release drops a reference to `None`, `True` or `False` on many calls
  under Python 3.11, and a long session aborted the interpreter on exit ("none_dealloc"). Python 3.12 and newer still get 6.12.0.
- The gallery could crash when the application style sheet was cleared and set again, for example by a theme that sets a style sheet:
  Qt crashes when a widget that was never shown is deleted after such a change. The gallery now polishes its widgets after building them,
  and the built-in themes polish every widget before they change the style sheet.
- Return and Enter in the story list did not open the selected story on macOS, where Qt's item views start editing on Return instead.
- Choosing the Custom canvas size, or zooming in, could make the window wider with wide fonts (the Windows default font grew it from 1100
  to 1244 pixels): the Width and Height boxes now have a row of their own, and the zoom note wraps.
- `pyside6_storybook.app.run` left a Quit event posted when it returned, so every later event loop in the same process (a second `run()`,
  or a test's wait) stopped at once.
- The Dark theme's input fields, unchecked check boxes and alternate table rows were almost invisible in the preview. The preview
  surface now uses the window background, where a stock widget sits in an application, and the Dark palette separates `Window`,
  `Base` and `AlternateBase` further; the Light theme's alternate rows are a little stronger too.

[Unreleased]: https://github.com/Youth-Research-Center/pyside6-storybook/compare/v0.1.0...main
[0.1.0]: https://github.com/Youth-Research-Center/pyside6-storybook/releases/tag/v0.1.0

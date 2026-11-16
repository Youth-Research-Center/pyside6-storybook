# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Added
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

### Fixed
- The package no longer installs PySide6 6.12.0 on Python 3.11. That release drops a reference to `None`, `True` or `False` on many calls
  under Python 3.11, and a long session aborted the interpreter on exit ("none_dealloc"). Python 3.12 and newer still get 6.12.0.
- The Dark theme's input fields, unchecked check boxes and alternate table rows were almost invisible in the preview. The preview
  surface now uses the window background, where a stock widget sits in an application, and the Dark palette separates `Window`,
  `Base` and `AlternateBase` further; the Light theme's alternate rows are a little stronger too.

# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Added
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
- The example stories `Buttons/Push Button` and `Inputs/Line Edit` are now `Buttons/Push Button/Default` and `Inputs/Line Edit/Default`,
  each with variants.
- A control's default must have the control's value type: `BoolControl` takes only a `bool`, `IntControl` an `int` (not a `bool`),
  `FloatControl` an `int` or `float` (not a `bool`), `TextControl` and `ChoiceControl` a string. `Story.default_args()` returns each
  default passed through the control's `coerce`, so a `FloatControl` default given as `1` starts as `1.0`.
- `FloatControl` rejects a default or bound that needs more than 10 decimals, which the editor used to show rounded.

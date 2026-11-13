# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Added
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
- Example stories built from stock Qt widgets (buttons, inputs, display widgets, the active palette and a small form), shown by
  `pyside6-storybook --examples`.

# pyside6-storybook

A small, Storybook-style component explorer for [PySide6](https://doc.qt.io/qtforpython-6/). Write *stories*, functions that
build one widget in one state, and browse them in a gallery window: edit each story's arguments live, switch between light and
dark themes, and see an error in place of a story that breaks instead of a crashed app.

![The gallery showing the sign-in form example: a story list on the left, the rendered widget in the middle, and the theme switch and the story's controls on the right](https://raw.githubusercontent.com/Youth-Research-Center/pyside6-storybook/main/docs/images/gallery.png)

> **Status:** early development, not yet released. The first release, 0.1.0, will be published on PyPI; until then, install it
> from GitHub as shown below. [`docs/roadmap.md`](docs/roadmap.md) describes what is planned next.

## Install

pyside6-storybook needs Python 3.11 or newer and PySide6 6.8 or newer. Its only dependency is `PySide6-Essentials`, which a
project that already depends on the full `PySide6` package satisfies.

```bash
pip install git+https://github.com/Youth-Research-Center/pyside6-storybook
```

or, as a development dependency of a project managed with [uv](https://docs.astral.sh/uv/):

```bash
uv add --dev git+https://github.com/Youth-Research-Center/pyside6-storybook
```

Then open the built-in example stories:

```bash
pyside6-storybook --examples
```

## Your first story

Create `stories/greeting_story.py` in your project:

```python
from PySide6.QtWidgets import QPushButton, QWidget

from pyside6_storybook import BoolControl, StoryContext, TextControl, story


@story(
    "Buttons/Greeting",
    controls=[TextControl("text", "Hello!"), BoolControl("enabled", default=True)],
)
def greeting_button(ctx: StoryContext) -> QWidget:
    """A push button whose text and enabled state can be edited in the gallery."""
    button = QPushButton(ctx.args["text"])
    button.setEnabled(ctx.args["enabled"])
    return button
```

and open it:

```bash
pyside6-storybook stories
```

- `@story` registers the function under an id. The parts before the last `/` group stories (here `Buttons`); the last part is the
  story's name.
- The gallery calls the function with a `StoryContext`: `ctx.args` holds the current value of each control, by name, and
  `ctx.theme` the name of the active theme. The story is built again from scratch whenever a control or the theme changes.
- The function returns the widget to show. If it raises, or returns something that is not a widget, the gallery shows the error
  and its traceback in place of the widget, and the other stories keep working.
- Discovery picks up every file named `*_story.py` or `*_stories.py` below a folder. Story files can import your application, and
  each other, like any module of your project.

## Controls

Each control is an argument of the story and an editor in the gallery's controls pane.

| Control | Editor | Value in `ctx.args` |
| --- | --- | --- |
| `TextControl(name, default)` | line edit | `str` |
| `BoolControl(name, default=...)` | check box | `bool` |
| `ChoiceControl(name, default, options)` | combo box | `str`, one of `options` |
| `IntControl(name, default, minimum, maximum)` | spin box (32-bit range) | `int` |
| `FloatControl(name, default, minimum, maximum)` | spin box with decimals | `float` |

A story without controls is fine; the controls pane then says so. The [example stories](src/pyside6_storybook/examples) use every
control type.

## Where your stories come from

`pyside6-storybook path/to/stories` loads the folders, `.py` files and dotted module names you give it; `--examples` adds the
built-in example stories. Run without targets, it looks in this order:

1. **`pyproject.toml`** in the current directory:

   ```toml
   [tool.pyside6-storybook]
   stories = ["stories"]   # folders, .py files or dotted module names, relative to this file
   pythonpath = ["src"]    # optional: folders put on sys.path first, so stories can import your application
   ```

2. **Entry points** of installed packages, each naming a module of stories:

   ```toml
   [project.entry-points."pyside6_storybook.stories"]
   my_widgets = "my_widgets.stories"
   ```

3. **The built-in examples**, only when neither of the above is configured. A configured source that fails to load is reported
   as an error; it never falls back to the examples.

A story module that fails to import is listed in the gallery under "Load errors" with its traceback, and the gallery opens with
the stories that did load.

## Command line

```text
pyside6-storybook [TARGET ...]        open the gallery with the stories in these folders, files or modules
  --examples                          also load the built-in example stories
  --theme {Light,Dark}                the theme to start in
  --list                              print the story ids and exit, without a window (works without a display)
  --version                           print the version
```

`python -m pyside6_storybook` takes the same arguments. With `--list`, standard error also says which source the stories came
from, and the exit code is 1 if any story module failed to load.

## Themes

The gallery switches between two built-in themes, Light and Dark: the Fusion style with an explicit palette, so a widget looks
the same on Windows, macOS and Linux. A theme hook that lets an application plug in its own theme manager is planned (see the
roadmap).

## Licence

MIT. See [LICENSE](LICENSE). PySide6, which pyside6-storybook depends on, is available under the LGPLv3, the GPLv3 or a
commercial Qt licence.

pyside6-storybook is an independent project. It is not affiliated with or endorsed by The Qt Company or the Storybook project.

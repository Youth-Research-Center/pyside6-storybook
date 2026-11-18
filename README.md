# pyside6-storybook

A small, Storybook-style component explorer for [PySide6](https://doc.qt.io/qtforpython-6/). Write *stories*, functions that
build one widget in one state, and browse them in a gallery window: edit each story's arguments live, switch between light and
dark themes, and see an error in place of a story that breaks instead of a crashed app.

![The gallery showing the sign-in form example: a story list on the left, the rendered widget in the middle, and the theme switch and the story's controls on the right](https://raw.githubusercontent.com/Youth-Research-Center/pyside6-storybook/main/docs/images/gallery.png)

> **Status:** early development, not yet released. The first release, 0.1.0, will be published on PyPI; until then, install it
> from GitHub as shown below.
> [`docs/roadmap.md`](https://github.com/Youth-Research-Center/pyside6-storybook/blob/main/docs/roadmap.md) describes what is planned next.

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

uv installs it into the project's `.venv` without activating that environment, so with uv, put `uv run` in front of the
`pyside6-storybook` commands in this README (or activate `.venv` first).

Then open the built-in example stories:

```bash
pyside6-storybook --examples
```

With uv:

```bash
uv run pyside6-storybook --examples
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

and open it, with `uv run` in front when you installed with uv:

```bash
pyside6-storybook stories
```

- `@story` registers the function under an id. The parts before the last `/` group stories (here `Buttons`); the last part is the
  story's name.
- The gallery calls the function with a `StoryContext`: `ctx.args` holds the current value of each control, by name, and
  `ctx.theme` the name of the active theme. The story is built again from scratch whenever a control or the theme changes.
  `ctx.tokens` holds the theme provider's design tokens (see [Themes][themes]).
- The function returns the widget to show. If it raises, or returns something that is not a widget, the gallery shows the error
  and its traceback in place of the widget, and the other stories keep working.
- Discovery picks up every file named `*_story.py` or `*_stories.py` below a folder. Story files can import your application, and
  each other, like any module of your project.

## What's in it

Everything below is documented on the [documentation site][site].

- [Writing stories][writing-stories]: `@story`, ids and groups, the `StoryContext`, variants, layout and decorators.
- [Controls][controls]: text, bool, choice, int, float, colour, enum and file controls, edited live in the gallery.
- [Finding stories][finding-stories]: folders, files and modules, `[tool.pyside6-storybook]` in `pyproject.toml`, entry points.
- [Command line][command-line]: every option of `pyside6-storybook`, and its exit codes.
- [The gallery][gallery]: the window, keyboard shortcuts, canvas sizes and zoom, the Docs tab, the action log and hot reload.
- [Themes][themes]: the built-in Light, Dark and System themes, your own themes through a theme provider, design tokens and styling.
- [Testing stories][testing]: a pytest plugin that renders every story in every theme, accessibility and contrast checks,
  screenshot snapshots and the `render_story` fixture.
- [Troubleshooting][troubleshooting]: load errors, duplicate ids, headless runs and fonts in CI.
- [API reference][reference] and [Changelog][changelog].

[site]: https://youth-research-center.github.io/pyside6-storybook/
[writing-stories]: https://youth-research-center.github.io/pyside6-storybook/writing-stories/
[controls]: https://youth-research-center.github.io/pyside6-storybook/controls/
[finding-stories]: https://youth-research-center.github.io/pyside6-storybook/finding-stories/
[command-line]: https://youth-research-center.github.io/pyside6-storybook/command-line/
[gallery]: https://youth-research-center.github.io/pyside6-storybook/gallery/
[themes]: https://youth-research-center.github.io/pyside6-storybook/themes/
[testing]: https://youth-research-center.github.io/pyside6-storybook/testing/
[troubleshooting]: https://youth-research-center.github.io/pyside6-storybook/troubleshooting/
[reference]: https://youth-research-center.github.io/pyside6-storybook/reference/
[changelog]: https://youth-research-center.github.io/pyside6-storybook/changelog/

## Licence

MIT. See [LICENSE](https://github.com/Youth-Research-Center/pyside6-storybook/blob/main/LICENSE).
PySide6, which pyside6-storybook depends on, is available under the LGPLv3, the GPLv3 or a commercial Qt licence.

The gallery's icons are [Phosphor Icons](https://phosphoricons.com) (MIT), bundled in the package. See
[THIRD_PARTY_NOTICES.md](https://github.com/Youth-Research-Center/pyside6-storybook/blob/main/THIRD_PARTY_NOTICES.md).

pyside6-storybook is an independent project. It is not affiliated with or endorsed by The Qt Company or the Storybook project.

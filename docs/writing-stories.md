# Writing stories

A story is a function that builds one widget in one state. This page covers `@story`, ids and groups, the `StoryContext`,
variants, the layout and decorators.

## A first story

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
  `ctx.tokens` holds the theme provider's design tokens (see [Design tokens](themes.md#design-tokens)).
- The function returns the widget to show. If it raises, or returns something that is not a widget, the gallery shows the error
  and its traceback in place of the widget, and the other stories keep working.
- Discovery picks up every file named `*_story.py` or `*_stories.py` below a folder. Story files can import your application, and
  each other, like any module of your project.

## Variants

A variant is the same story with other starting values: it shares the story's function and controls, and shows up in the gallery as a
story of its own. Call `.variant()` on the story that `@story` returned:

```python
from PySide6.QtWidgets import QPushButton, QWidget

from pyside6_storybook import BoolControl, StoryContext, TextControl, story


@story(
    "Inputs/Push Button/Default",
    controls=[TextControl("text", "Click me"), BoolControl("enabled", default=True)],
)
def push_button(ctx: StoryContext) -> QWidget:
    """A push button."""
    button = QPushButton(ctx.args["text"])
    button.setEnabled(ctx.args["enabled"])
    return button


push_button.variant("Disabled", args={"enabled": False})
push_button.variant("Long label", args={"text": "A button with a much longer label"})
```

- The variant's id is the story's component, which is its id without the last segment, plus the variant's name:
  `Inputs/Push Button/Disabled`. Give a story that will have variants an id whose last segment names the story, such as
  `"Inputs/Spin Box/Default"`; with `"Inputs/Spin Box"` the component would be `Inputs` and the variant `Inputs/Large`.
- `args` replaces the defaults of some controls, by control name. Each value must be one its control accepts, and each key must be
  a control of the story; otherwise `.variant()` raises a `ValueError` naming the variant and the key. The controls stay editable.
- The name must not be blank, contain `/` or equal the story's own name. Call `.variant()` on the base story, not on a variant, and
  only after `@story` registered it. A story whose id has no group (`"Button"`) cannot have variants.
- Variants appear after their story, in the order you create them. Creating the same variant twice replaces the first one.

## Layout

The preview places your widget in one of three ways. Pick one per story with `layout=`, a `Layout` member or its string value:

```python
from PySide6.QtWidgets import QPlainTextEdit, QPushButton, QWidget

from pyside6_storybook import Layout, StoryContext, story


@story("Buttons/Centered/Default", layout=Layout.CENTERED)
def centered_button(ctx: StoryContext) -> QWidget:
    """A push button at its natural size, in the middle of the preview."""
    return QPushButton("Centred")


centered_button.variant("Padded", layout=Layout.PADDED)


@story("Editors/Notes", layout="fill")
def notes(ctx: StoryContext) -> QWidget:
    """A text editor that fills the preview."""
    return QPlainTextEdit("Fills the preview")
```

- `Layout.PADDED` (the default) puts the widget at the top of the preview, inside a margin. Its width follows its size policy, so a
  push button stretches across the preview, and its height is its natural height.
- `Layout.CENTERED` gives the widget its natural size and centres it, horizontally and vertically.
- `Layout.FILL` gives the widget the whole preview inside the margin, in each direction its size policy lets it grow. In a direction
  it cannot grow (a push button is vertically fixed) it keeps its natural size and is centred. It shrinks with the window and the
  preview shows no scroll bars.
- In `PADDED` and `CENTERED` a widget larger than the preview scrolls instead of being squeezed. The natural size is the widget's
  `sizeHint()`, raised to its minimum size and capped by its maximum size. A word-wrapped `QLabel` wraps in a narrow preview instead.
- A variant has its story's layout unless you give it another with `layout=`. `layout=None` is the same as leaving it out.
- To change the layout of every story that declares none, set `default_layout` on the registry, for example
  `default_registry.default_layout = Layout.CENTERED`. An invalid layout, in `layout=` or in `default_layout`, raises a `ValueError`.
- The error shown for a story that fails, and the "Load errors" view, always fill the preview.

## Decorators

A decorator wraps the widget your story builds, to add padding, a border or a fixed size without changing the story. It is a function
that receives the widget built so far and the `StoryContext`, and returns the widget to show. Pass a list with `decorators=`:

```python
from PySide6.QtWidgets import QGroupBox, QLabel, QVBoxLayout, QWidget

from pyside6_storybook import StoryContext, story
from pyside6_storybook.decorators import fixed_size, frame, padding


def in_group_box(widget: QWidget, ctx: StoryContext) -> QWidget:
    """Show the widget inside a group box titled with the active theme."""
    box = QGroupBox(ctx.theme)
    QVBoxLayout(box).addWidget(widget)
    return box


@story("Cards/Card/Default", decorators=[padding(24), fixed_size(320, 200)])
def card(ctx: StoryContext) -> QWidget:
    """A 320 by 200 label inside 24 pixels of padding."""
    return QLabel("Card")


card.variant("Framed", decorators=[frame(), in_group_box])
```

- The built-ins are in `pyside6_storybook.decorators`: `padding(horizontal, vertical=None)` adds transparent space (`vertical` defaults to
  `horizontal`), `frame()` draws a panel border from the palette, and `fixed_size(width, height)` calls `setFixedSize` on the widget and
  adds no wrapper. Sizes and padding must be ints; padding must not be negative and sizes must be positive.
- The first decorator in a list is the outermost, like stacked Python `@decorators`: the last one is applied first, next to your widget. So
  `decorators=[padding(24), fixed_size(320, 200)]` is a 320 by 200 widget inside 24 pixels of padding.
- `StoryRegistry.decorators` is a plain list of decorators for every story of that registry, for example
  `default_registry.decorators.append(padding(8))` in your stories package's `__init__.py`. They wrap the story's own decorators, the first
  one outermost, and the list is read each time the preview is built.
- A variant has its story's decorators unless it gives a list with `decorators=`, which replaces them (an empty list removes them).
  Registry decorators always apply.
- To write one, return the widget you received after configuring it, or a new widget that contains it as a descendant: put it in a layout
  of the wrapper, as `in_group_box` does. A decorator that raises, returns something that is not a `QWidget`, or returns a widget that
  does not contain the widget it received (with the story's widget inside), shows an error in the preview that names the decorator.
- Decorators run on every rebuild, so keep them stateless, like stories. The `Decorator` type is exported for annotations.

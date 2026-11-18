# Controls

Each control is an argument of the story and an editor in the gallery's controls pane.

| Control | Editor | Value in `ctx.args` |
| --- | --- | --- |
| `TextControl(name, default, *, multiline=False)` | line edit, or a multi-line text edit | `str` |
| `BoolControl(name, default=...)` | check box | `bool` |
| `ChoiceControl(name, default, options)` | combo box | `str`, one of `options` |
| `IntControl(name, default, minimum, maximum, *, step=1, slider=False)` | spin box (32-bit range), optionally with a slider | `int` |
| `FloatControl(name, default, minimum, maximum, *, step=None, decimals=None, slider=False)` | spin box with decimals, optionally with a slider | `float` |
| `ColorControl(name, default, *, alpha=False)` | swatch button that opens a colour dialog, and a hex field | `QColor` |
| `EnumControl(name, default)` | combo box of the member names | the enum member |
| `FileControl(name, default="", *, filter="")` | path field and a "Browse…" button | `pathlib.Path`, or `None` while empty |

Every control also takes two keyword-only fields:

- `label`: the text of the form label. Without it the label is derived from `name`: `tile_type` becomes "Tile Type".
- `description`: a sentence shown as the tooltip of the label and the editor, and read out by screen readers as the editor's description.

```python
from pyside6_storybook import IntControl

IntControl("columns", 3, 1, 12, label="Number of columns", description="How many columns the grid has.", slider=True)
```

The options:

- `TextControl(multiline=True)` edits the text in a multi-line editor; Tab moves focus on instead of inserting a tab.
- `IntControl(step=...)` is the spin box's single step (arrow keys), at least 1. With `slider=True` a slider sits beside the spin box and
  moves by the same step.
- `FloatControl(step=...)` is the spin box's single step, greater than 0 and at most the range. Without it, the step is a power of ten
  near 1% of the range. `decimals` (0 to 10) is how many decimals the editor shows; without it, the fewest that show the step, the
  default and both bounds exactly, at least 2. With `slider=True`, the slider has one position per step, and its last position is
  always `maximum`, even when the step does not divide the range. A slider may have at most 10 000 steps; use a larger `step` for a
  wider range.
- `ColorControl` takes a hex string as its default: `"#RRGGBB"`, in either case. With `alpha=True` it also takes `"#RRGGBBAA"` (the CSS
  byte order, opacity last), and the dialog shows an alpha channel. Colour names and `"#RGB"` are not accepted. The story receives a
  new `QColor` on every render. In the hex field, an invalid entry reverts to the current colour.
- `EnumControl` takes a member of any Python or Qt enum as its default, which also fixes the enum class. The editor offers the named
  members in definition order; an alias is left out and the first name kept. For a flag enum, named combinations such as
  `Qt.AlignmentFlag.AlignCenter` are options, but an unnamed combination such as `AlignLeft | AlignTop` is not. `control.options` lists
  them.
- `FileControl(filter=...)` is a `QFileDialog` name filter such as `"Images (*.png *.jpg)"`. The file need not exist, and a relative path
  stays relative to the working directory.

A control checks its own values. A default must have the control's type: a `bool` is not accepted for an `IntControl` or a
`FloatControl`, an `int` is not accepted for a `BoolControl`, and a `ColorControl`'s default is a hex string, not a `QColor`. A
`FloatControl` rejects a default or bound that needs more than 10 decimals, and one that needs more decimals than `decimals` allows,
because the editor would silently round it.

In the gallery, a spin box, slider or combo box reacts to the mouse wheel only while it has keyboard focus, so scrolling the controls
pane never changes a value by accident. Click a control or press Tab to focus it. The controls pane scrolls when a story has more
controls than fit.

A story without controls is fine; the controls pane then says so. The
[example stories](https://github.com/Youth-Research-Center/pyside6-storybook/tree/main/src/pyside6_storybook/examples) use every control type
and option.

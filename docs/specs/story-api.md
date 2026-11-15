# Story API (milestone 2): design spec

Status: draft for review. Covers issues #14 (variants), #15 (colour, enum and file controls), #16 (control options), #17
(decorators) and #18 (layout). The issues hold the user-facing scope and acceptance criteria; this document fixes the design
decisions they leave open, so the five pull requests fit together.

## Goals and constraints

- **Stories written for milestone 1 keep working unchanged.** Every new parameter is keyword-only with a default, added after the
  existing ones (`AGENTS.md`). `@story(id, controls=[...])` with a function taking `StoryContext` stays the whole required API.
- **One way to give an argument a value.** A control declares an argument (name, default, editor); a variant overrides values
  with `args`. There is no second mechanism (no inferred controls, no per-variant controls).
- **The library stays small and generic.** No new runtime dependency; editors are stock Qt widgets; nothing imports an application.
- **Errors surface at registration where possible**, otherwise in the gallery's error panel, never as a crash.

## Overview of the public API after milestone 2

```python
from pyside6_storybook import (
    BoolControl, ChoiceControl, ColorControl, EnumControl, FileControl, FloatControl, IntControl, TextControl,
    Layout, StoryContext, story,
)
from pyside6_storybook.decorators import fixed_size, frame, padding

@story(
    "Inputs/Button/Default",
    controls=[TextControl("text", "Click me", label="Label"), BoolControl("enabled", default=True)],
    layout=Layout.CENTERED,
    decorators=[padding(24)],
)
def button(ctx: StoryContext) -> QWidget: ...

button.variant("Disabled", args={"enabled": False})
button.variant("Long label", args={"text": "A button with a much longer label"}, layout=Layout.PADDED)
```

New public names: `ColorControl`, `EnumControl`, `FileControl`, `Layout`, `Decorator`, and the `pyside6_storybook.decorators`
module (`padding`, `frame`, `fixed_size`). `Story` gains attributes and methods; `StoryRegistry` gains `decorators` and
`default_layout`. All are listed in `__all__` and the changelog when they land.

## 1. Controls (#15, #16)

### 1.1 Common shape

Every control stays a frozen, slotted dataclass whose first two positional fields are `name` and `default` (plus the existing
positional `options` / `minimum`, `maximum`). New fields are keyword-only.

Shared keyword-only fields on every control (#16), declared in each class with `field(default=..., kw_only=True)`:

| Field | Type | Default | Meaning |
| --- | --- | --- | --- |
| `label` | `str \| None` | `None` | Text of the form label; `None` derives it from `name` as today (`tile_type` → "Tile Type"). |
| `description` | `str` | `""` | Tooltip and accessible description of the editor (and tooltip of the label). |

A read-only property `display_label` returns `label` or the derived text, so the panel and the future Docs tab agree.

Shared method on every control:

```python
def coerce(self, value: object) -> Any:
    """Return `value` as this control's value type, or raise ValueError/TypeError naming the control."""
```

`coerce` is the single validation point. `__post_init__` validates the declared default with it; variant `args` (#14) are
validated with it at registration; the controls panel uses it to produce the values a story receives. It returns a *new* object
for mutable value types (`QColor`), so a story that mutates its argument cannot affect the next render.

| Control | Declared `default` | Value a story receives (`coerce` result) | Accepted by `coerce` |
| --- | --- | --- | --- |
| `TextControl` | `str` | `str` | `str` |
| `BoolControl` | `bool` | `bool` | `bool` only (not `0`/`1`) |
| `ChoiceControl` | `str` in `options` | `str` | a string in `options` |
| `IntControl` | `int` | `int` | `int` (not `bool`) within `minimum..maximum` |
| `FloatControl` | `float` | `float` | `int` or `float`, finite, within the range; converted to `float` |
| `ColorControl` | `str` hex | `QColor` | a hex string or a `QColor` |
| `EnumControl` | enum member | the member | a member of the default's enum class |
| `FileControl` | `str` or `Path` | `Path`, or `None` when empty | `str`, `Path` or `None` |

`Story.default_args()` keeps its name and becomes "the values the story starts with": `coerce(control.default)` for each
control, then the story's own `args` (variants) on top. Its return type stays `dict[str, object]`.

### 1.2 Options on existing controls (#16)

- `TextControl(..., multiline=False)`: `True` uses a `QPlainTextEdit` (one `valuesChanged` per keystroke, like the line edit).
- `IntControl(..., step=1, slider=False)`: `step` is the spin box's single step (`>= 1`).
- `FloatControl(..., step=None, decimals=None, slider=False)`: `None` keeps today's derivation (a power of ten near 1% of the
  range; enough decimals for the step, the default and both bounds). An explicit `decimals` must be `0..10`; an explicit `step`
  must be `> 0` and not larger than the range. The editor shows at least as many decimals as the explicit `step` needs.
- `slider=True` on `IntControl` / `FloatControl`: a `QSlider` next to the spin box. For floats the slider has
  `round((maximum - minimum) / step)` positions; a range that would need more than 10 000 positions is rejected at construction
  (`ValueError` suggesting a larger `step`). The two editors mirror each other inside `QSignalBlocker`, so one user edit emits
  exactly one `valuesChanged`. Mirroring snaps the slider to the nearest position; the spin box keeps the exact value.

### 1.3 New controls (#15)

- **`ColorControl(name, default, *, alpha=False)`.** `default` is `"#RRGGBB"`, or `"#RRGGBBAA"` when `alpha=True` (an 8-digit
  default without `alpha` is a `ValueError`). Note that `QColor("#11223344")` reads the first byte as alpha (`#AARRGGBB`), so the
  control parses the CSS order itself. The editor is a swatch button (an icon of the colour plus the hex text, so the colour is
  never conveyed by background alone and the focus ring stays the button's own) that opens `QColorDialog` (with
  `ShowAlphaChannel` when `alpha`), and a hex `QLineEdit` that commits on `editingFinished` and reverts on invalid input.
- **`EnumControl(name, default)`.** Options are the members of `type(default)`, in definition order; works for Python `Enum` and
  PySide6's Qt enums (which are Python enums). For a `Flag`, only single members are offered and a combined default (for
  example `AlignLeft | AlignTop`) is rejected. The editor is a `QComboBox` of member names; the story receives the member.
- **`FileControl(name, default="", *, filter="")`.** `filter` is a `QFileDialog` name filter (`"Images (*.png *.jpg)"`). The
  editor is a `QLineEdit` (commits on `editingFinished`) plus a "Browse…" button that opens `QFileDialog.getOpenFileName`. The
  value is a `Path` (relative paths stay relative, to the working directory) or `None` when empty. The file is not required to
  exist; a story that needs it decides what to show.

The `Control` union grows to the eight types. Dialogs are always opened through module-level functions in the editor modules
(`_ask_color`, `_ask_file`), which tests monkeypatch; no test opens a modal dialog.

### 1.4 The controls panel and editors (#16, #15)

`gui/controls_panel.py` currently builds editors in an `if`/`elif` chain. It becomes a thin form over a `gui/editors/` package,
one module per editor, each a `QWidget` subclass with the same small interface:

```python
class ControlEditor(QWidget):
    valueChanged = Signal(object)          # once per user edit, with the new value (already coerced)
    def value(self) -> object: ...
```

The panel maps control type to editor class in a dict (`AGENTS.md`: a dict over a long `if` chain), takes the starting values
(`ControlsPanel(controls, values=..., parent=...)`, keyword-only `values` defaulting to the controls' defaults), labels each row
with `display_label`, sets the label as the editor's buddy and accessible name, and applies `description`. `values()` returns
`{name: control.coerce(current)}`, so mutable values are fresh per call.

Wheel handling (#16): spin boxes, sliders and combo boxes in the panel get `Qt.FocusPolicy.StrongFocus` and an event filter that
ignores wheel events unless the editor has focus, so scrolling the controls pane never changes a value. The controls section of
the window becomes scrollable (`QScrollArea`, no horizontal scroll bar), which this needs and long control lists need anyway.

## 2. Variants (#14)

### 2.1 Ids, components and the registry link

- `Story.component`: the groups joined with `/` (`"Inputs/Button"` for `"Inputs/Button/Default"`), or `None` for an id without
  groups. The future sidebar tree and Docs tab group by it.
- A story remembers the registry that registered it (`Story.registry`, `None` until registered; set by `StoryRegistry.register`).
  `Story.variant(...)` registers into that registry; calling it on an unregistered story raises `RuntimeError`.
- `Story.variant_of`: the base `Story` for a variant, `None` otherwise. Variants of variants are not allowed (`TypeError` asking
  to call `.variant` on the base).

### 2.2 `Story.variant(name, *, args=None, layout=None, decorators=None) -> Story`

- The variant's id is `f"{component}/{name}"`. A base story without a component raises `ValueError` explaining that variants
  need an id with a group, for example `"Button/Default"`. `name` must be non-blank and contain no `/`. A name equal to the base
  story's name is a `ValueError`.
- It shares the base's render function, controls, docstring and origin (`module`, `qualname`).
- `args` overrides control defaults. Every key must be a control name and every value must pass that control's `coerce`
  (`ValueError` naming the variant, the key and the reason). The stored `Story.args` is a read-only mapping of coerced values.
- `layout` and `decorators` (sections 3 and 4): `None` inherits the base's value; anything else replaces it for this variant.
- It returns the new `Story` (so tests and helpers can use it); the return value can be ignored.

### 2.3 Registration rules

- The registry's existing rule still holds: the same id from the same origin replaces the earlier story in place (module reload);
  from a different origin it raises. A variant has its base's origin, so re-running a module replaces its variants too, and a
  variant id that collides with another function's story raises.
- Calling `button.variant("Disabled", ...)` twice in one run replaces the first (same id, same origin). This is the reload rule
  applied as-is; it is documented, not detected.
- Order: variants appear in registration order, after their base. Until the sidebar tree (milestone 3) lands, the flat list
  shows full ids, so `Inputs/Button/Default`, `Inputs/Button/Disabled` read naturally.

### 2.4 The gallery

Selecting a story builds its controls panel from `story.default_args()` (base defaults with the variant's `args` on top), so a
variant's controls start at its values and stay editable. Nothing else in the window changes for #14.

## 3. Layout (#18)

- `Layout` is a `StrEnum` with `CENTERED = "centered"`, `PADDED = "padded"`, `FILL = "fill"`. `@story(..., layout=...)` accepts a
  member, its string value, or `None`. An unknown string raises `ValueError` at registration listing the valid values.
- `None` means "the registry's default": `StoryRegistry.default_layout`, a plain attribute defaulting to `Layout.PADDED`, read at
  render time, so a project can set it once (`default_registry.default_layout = Layout.CENTERED`) before or after its stories
  register. `Story.layout` keeps what was declared (`Layout | None`); `Story.effective_layout` resolves it.
- The preview applies it:
  - `PADDED`: today's behaviour exactly. Top-aligned with the surface margins; the width follows the widget's size policy.
  - `CENTERED`: centred horizontally and vertically at the widget's size hint (respecting its size policy and minimum size).
  - `FILL`: the widget takes the whole surface inside the margins.
- The preview surface moves into a `QScrollArea` (`widgetResizable=True`). In `PADDED` and `CENTERED`, a widget larger than the pane
  scrolls; in `FILL` both scroll bars are off and the widget shrinks with the pane down to its minimum size.
- The error panel and the "Load errors" view always use `FILL`, whatever the story declares.
- Examples: at least one story per mode. The push button becomes `CENTERED`; a new `Display/Table` example (`QTableWidget`) uses
  `FILL`; the rest stay `PADDED`.

## 4. Decorators (#17)

### 4.1 Definition

```python
Decorator = Callable[[QWidget, StoryContext], QWidget]
```

A decorator receives the widget built so far and the story's context, and returns the widget to show instead. It either returns
the same widget (after configuring it) or a new wrapper that contains the received widget as a descendant.

### 4.2 Order and sources

The widget a story returns is wrapped first by the story's own `decorators`, in list order (the first is innermost), then by the
registry's decorators (`StoryRegistry.decorators`, a plain `list[Decorator]` a project may append to, for example in its stories
package `__init__.py`), also in list order. Registry decorators are read at render time, like `default_layout`. A variant's
`decorators=None` inherits the base's list; a list replaces it (registry decorators always apply).

### 4.3 Rendering

`Story.render(ctx) -> RenderedStory`, a frozen dataclass with `widget` (what the story function returned, undecorated) and `root`
(the outermost widget to place in the preview). It calls the function, checks it returned a `QWidget`, applies the decorators,
and checks after each one that it returned a `QWidget` that is, or contains, the story widget. Failures raise `StoryRenderError`
(a new exception type, internal to the library) carrying a title for the error panel and the original traceback, for example
"Inputs/Card: decorator padding(24) returned None, expected a QWidget". `Story.__call__` stays the plain function call.

The window uses `render`: it places `root` in the preview with the story's layout, keeps `widget` for
`current_preview_widget()` (the undecorated widget, as #17 requires for tests and the pytest plugin), and deletes `root` on
rebuild, which deletes everything inside it. A wrapper that dropped the story widget is caught by the containment check rather
than leaking it.

### 4.4 Built-in decorators

In `pyside6_storybook/decorators/`, one module each, re-exported from `pyside6_storybook.decorators`:

- `padding(horizontal, vertical=None)`: a transparent `QWidget` with those content margins (`vertical` defaults to `horizontal`).
  Negative values raise `ValueError`.
- `frame()`: a `QFrame` with `StyledPanel` shape, drawn from the palette, zero margins.
- `fixed_size(width, height)`: calls `setFixedSize` on the received widget and returns it (no wrapper). Non-positive sizes
  raise `ValueError`.

Each returned decorator has a readable `__repr__` (`padding(24)`), used in error titles and the future Docs tab.

## 5. Module layout

| Path | Contents |
| --- | --- |
| `controls/color_control.py`, `enum_control.py`, `file_control.py` | the three new controls (#15) |
| `controls/_options.py` | helpers shared by the controls: label derivation, float step and decimals (moved from the panel) |
| `registry/story_definition.py` | `Story` with `component`, `registry`, `variant_of`, `args`, `layout`, `decorators`, `variant()`, `render()` |
| `registry/layout.py` | `Layout` (#18) |
| `registry/rendering.py` | `RenderedStory`, `StoryRenderError`, the decorator application and checks (#17) |
| `decorators/` | `Decorator` type, `padding.py`, `frame.py`, `fixed_size.py` (#17) |
| `gui/editors/` | one module per editor, plus `_wheel.py` for the wheel filter (#16, #15) |
| `gui/controls_panel.py` | the form over the editors |
| `gui/window.py` | scrollable controls section, scrolled preview with layout modes, `render()` |

## 6. Testing

Each PR adds tests next to the code it changes and keeps `tests/test_examples.py` in step with the examples. In particular:

- Controls: `coerce` accepts and rejects per the table in 1.1; every new field's validation; `display_label`.
- Editors: driven the way a user does (typing, clicking, `setValue` on the editor); exactly one `valuesChanged` per edit,
  including slider and spin box mirroring; the wheel filter (a wheel event on an unfocused spin box leaves its value alone);
  dialogs monkeypatched.
- Variants: ids, components, `args` overrides reaching the render function and the panel, invalid `args`, the no-component and
  same-name errors, reload replacing variants without duplicates, variants of variants rejected.
- Layout: the previewed widget's geometry in each mode, and after a window resize; scroll bars for an oversized widget in
  `PADDED` and `CENTERED`, none in `FILL`; the registry default; invalid names.
- Decorators: application order with story and registry decorators; each built-in's geometry; the containment and return-type
  checks; no widget left alive after a rebuild (`shiboken6.isValid` after processing deferred deletes); `current_preview_widget()`
  is the undecorated widget; the five-line `QGroupBox` decorator from the issue works as written.
- Existing tests keep passing unchanged, except where a PR deliberately changes behaviour and says so.

## 7. Documentation

Each PR updates the README section it affects (controls table, a "Variants" and a "Layout and decorators" section), the
changelog, and `AGENTS.md` where the module layout changes. `tests/test_readme.py` keeps the README's code runnable; new README
examples get the same treatment.

## 8. Out of scope

Inferring controls from type hints; conditional controls; per-variant controls; a decorator toolbar; date, font, list and
object controls; arbitrary layouts beyond the three modes (use a decorator).

# Story API (milestone 2): design spec

Status: reviewed; ready for implementation. Covers issues #14 (variants), #15 (colour, enum and file controls), #16 (control
options), #17 (decorators) and #18 (layout). The issues hold the user-facing scope and acceptance criteria; this document fixes
the design decisions they leave open, so the five pull requests fit together. Where this spec and an issue differ, the issue has
been updated to match (#17's decorator order).

## Goals and constraints

- **Well-typed stories written for milestone 1 keep working unchanged.** Every new parameter is keyword-only with a default,
  added after the existing ones (`AGENTS.md`). `@story(id, controls=[...])` with a function taking `StoryContext` stays the whole
  required API. One deliberate tightening: control defaults must have the control's value type (1.1), which milestone 1 did not
  check; it is listed under `### Changed` in the changelog. Nothing has been released, so no user is affected.
- **One way to give an argument a value.** A control declares an argument (name, default, editor); a variant overrides values
  with `args`. No inferred controls, no per-variant controls.
- **Small and generic.** No new runtime dependency; editors are stock Qt widgets; nothing imports an application.
- **Library code takes a `StoryRegistry` as an argument** (`AGENTS.md`). Rendering, layout and decorator lookup receive the
  registry explicitly; a story's link to its registry exists only so `.variant()` knows where to register.
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

New public names, exported from the package root and listed in the changelog when they land: `ColorControl`, `EnumControl`,
`FileControl`, `Layout`, `Decorator`, and the `pyside6_storybook.decorators` module (`padding`, `frame`, `fixed_size`). `Story`
gains attributes and `variant()`; `StoryRegistry` gains `decorators` and `default_layout`. Rendering helpers (section 4.3) are
internal.

## 1. Controls (#15, #16)

### 1.1 Common shape

Every control stays a frozen, slotted dataclass whose positional fields are unchanged (`name`, `default`, and the existing
`options` / `minimum`, `maximum`). New fields are keyword-only, declared in each class with `field(default=..., kw_only=True)`.
There is **no shared base class**, and controls must not call zero-argument `super()`: in a slotted dataclass that raises
`TypeError` on Python 3.11 and 3.12. Shared logic lives in plain functions in `controls/_options.py`.

Shared keyword-only fields on every control (#16):

| Field | Type | Default | Meaning |
| --- | --- | --- | --- |
| `label` | `str \| None` | `None` | Text of the form label; `None` derives it from `name` as today (`tile_type` → "Tile Type"). |
| `description` | `str` | `""` | Tooltip and accessible description of the editor, and tooltip of the label. |

A read-only property `display_label` returns `label` or the derived text, so the panel and the future Docs tab agree.

Shared method on every control:

```python
def coerce(self, value: object) -> Any:
    """Return `value` as this control's value type, or raise ValueError/TypeError naming the control."""
```

`coerce` is the single validation point: `__post_init__` validates the declared default with it, variant `args` (#14) are
validated with it at registration, and every value handed to a story passes through it. It returns a *new* object for mutable
value types (`QColor`), so a story that mutates its argument cannot affect the next render.

| Control | Declared `default` | Value a story receives | `coerce` accepts |
| --- | --- | --- | --- |
| `TextControl` | `str` | `str` | `str` |
| `BoolControl` | `bool` | `bool` | `bool` only (not `0`/`1`) |
| `ChoiceControl` | `str` in `options` | `str` | a string in `options` |
| `IntControl` | `int` | `int` | `int` (not `bool`) within `minimum..maximum` |
| `FloatControl` | `float` | `float` | `int` (not `bool`) or `float`, finite, within the range, needing no more decimals than the editor shows (1.2); returned as `float` |
| `ColorControl` | hex `str` | `QColor` | a hex string in the control's grammar, or a valid `QColor` (1.3) |
| `EnumControl` | an option | the member | an instance of the default's enum class that is one of the options (1.3); returns that option |
| `FileControl` | `str` or `Path` | `Path`, or `None` when empty | `str`, `Path` or `None` |

`Story.default_args()` keeps its name and return type (`dict[str, object]`) and becomes "the values the story starts with":
for each control, `coerce` of the variant's `args` value if it has one, else `coerce(control.default)`. Calling `coerce` on every
call means each call returns fresh objects.

### 1.2 Options on existing controls (#16)

- `TextControl(..., multiline=False)`: `True` uses a `QPlainTextEdit` (one `valuesChanged` per keystroke, like the line edit).
- `IntControl(..., step=1, slider=False)`: `step` is the spin box's single step and must be `>= 1`.
- `FloatControl(..., step=None, decimals=None, slider=False)`:
  - `step=None` keeps today's derivation (a power of ten near 1% of the range). An explicit `step` must be `> 0` and not larger
    than the range.
  - The editor's decimals, exposed as the property `effective_decimals`: an explicit `decimals` (`0..10`), or, when `None`, the
    fewest decimals (at least 2, at most 10) that represent the step, the default and both bounds exactly (today's rule).
  - An explicit `decimals` too small for the step, the default or a bound is a `ValueError` at construction.
  - `coerce` rejects a value for which `round(value, effective_decimals)` is not close to `value`, so a variant's `args` can
    never be silently rounded by the editor (`QDoubleSpinBox.setValue(0.123)` with 2 decimals reads back `0.12`). The message
    suggests `decimals=`. This also rejects defaults and bounds that need more than 10 decimals (`1e-12`), which milestone 1
    showed rounded; the changelog lists it under `### Changed`.
  - On a zero-width range (`minimum == maximum`) the derived step is `1.0`, and an explicit `step` is always a `ValueError`.
- `slider=True` on `IntControl` / `FloatControl`: a `QSlider` beside the spin box.
  - Integers: the slider's range is `minimum..maximum` with the same `step`.
  - Floats: the slider has positions `0..n` with `n = ceil((maximum - minimum) / step - 1e-9)`; position `i` means
    `min(minimum + i * step, maximum)`, so the last position always reaches `maximum`. The tolerance absorbs floating-point error:
    without it `(0, 0.07, step=0.01)` gets 8 positions instead of 7, the last two both meaning `0.07`. A range needing more than 10 000 positions
    is a `ValueError` at construction suggesting a larger `step`.
  - The two editors mirror each other inside `QSignalBlocker`, so one user edit emits exactly one `valuesChanged`. Moving the
    slider sets the spin box to that position's value; editing the spin box moves the slider to the nearest position and keeps the
    spin box's exact value.

### 1.3 New controls (#15)

- **`ColorControl(name, default, *, alpha=False)`.**
  - Grammar, case-insensitive: exactly `#RRGGBB`, or `#RRGGBBAA` when `alpha=True`. Nothing else: no colour names, no `#RGB`,
    no `#AARRGGBB`. An 8-digit value without `alpha` is a `ValueError`.
  - The control parses the CSS byte order itself: `QColor("#11223344")` reads the first byte as alpha (`#AARRGGBB`).
  - `coerce` also accepts a `QColor`: an invalid one is a `ValueError`, and so is one with alpha below 255 when `alpha=False`
    (the message says to set `alpha=True`). It always returns a new `QColor`.
  - The editor is a swatch button and a hex `QLineEdit`:
    - The swatch button shows an icon of the colour plus the hex text, so the colour is not conveyed by background alone and the
      focus ring stays the button's own. It opens `QColorDialog`, with `ShowAlphaChannel` when `alpha`.
    - The hex field commits on `editingFinished` and reverts to the current value on invalid input. `editingFinished` fires
      again when focus leaves after Return, so the editor emits only when the value changes.
- **`EnumControl(name, default)`.**
  - The options are the enum class's named members, taken from `type(default).__members__` in definition order and de-duplicated
    by value, keeping the first name, so aliases disappear.
  - For a `Flag` this includes named combinations, so `Qt.AlignmentFlag.AlignCenter` is an option even though
    `list(Qt.AlignmentFlag)` lists only the nine single-bit members.
  - An unnamed combination (`AlignLeft | AlignTop`) is not an option: it passes `isinstance` but fails `coerce`, because `coerce`
    also checks membership in the options.
  - Plain ints and bools are rejected even for `IntEnum` and `IntFlag` classes (Qt's enums are among them): `1 in options` is
    true for `Qt.AlignmentFlag`, so the `isinstance` check against the default's class is needed as well.
  - Works for Python enums and PySide6's Qt enums, which are Python enums.
  - The editor is a `QComboBox` of option names; the story receives the member.
- **`FileControl(name, default="", *, filter="")`.**
  - `filter` is a `QFileDialog` name filter (`"Images (*.png *.jpg)"`).
  - The editor is a `QLineEdit`, which commits on `editingFinished` (emitting only when the value changes, as the hex field),
    plus a "Browse…" button that opens `QFileDialog.getOpenFileName`.
  - The value is a `Path` (relative paths stay relative to the working directory) or `None` when empty. The file need not exist.

The `Control` union grows to the eight types. Editors open dialogs through module-level functions in their modules (`_ask_color`,
`_ask_file`), which tests monkeypatch; no test opens a modal dialog.

### 1.4 The controls panel and editors (#16, #15)

`gui/controls_panel.py` currently builds editors in an `if`/`elif` chain. It becomes a thin form over a `gui/editors/` package,
one module per editor. Each editor is a `QWidget` subclass with the same small interface:

```python
class ControlEditor(QWidget):
    valueChanged = Signal(object)          # once per user edit that changes the value, with the new (coerced) value
    def value(self) -> object: ...
```

The editor's parts are children of the editor, and the editor is the child of the panel and the label's buddy.

The panel:
- maps control type to editor class in a dict (`AGENTS.md`: a dict over a long `if` chain), typed
  `dict[type, Callable[..., ControlEditor]]`: `ty` checks a `type[ControlEditor]` value against `QWidget.__init__` and rejects the
  call;
- takes the starting values with a keyword-only `values` argument, defaulting to the controls' coerced defaults:
  `ControlsPanel(controls, parent=None, *, values=None)`;
- labels each row with `display_label`, sets the label as the editor's buddy, and applies `description`;
- returns `{name: control.coerce(current)}` from `values()`, so mutable values are fresh on every call.

Accessibility of composite editors (colour, file, slider plus spin box): the editor container calls `setFocusProxy(<primary
input>)`, so the label's buddy and Tab reach the input. The primary input gets the label text as its accessible name. The
secondary parts get their own names: "Choose colour for Accent", "Browse for Image", "Opacity slider".

Wheel handling (#16, and #15 for the enum combo box): spin boxes, sliders and combo boxes in the panel get `Qt.FocusPolicy.StrongFocus` and an event filter
(`gui/editors/_wheel.py`). For a `QEvent.Wheel` on an editor without focus, the filter calls `event.ignore()` and returns `True`.
Qt then skips the editor and, since the event is not accepted, passes it to the parent, so the controls pane scrolls instead.
Tests assert both cases: an unfocused editor keeps its value and leaves the event unaccepted, and a focused one changes. Qt only
propagates spontaneous wheel events, so "the pane scrolls" cannot be unit-tested. The window's controls section becomes scrollable (`QScrollArea`, no horizontal scroll bar), which this
needs and which long control lists need anyway.

## 2. Variants (#14)

### 2.1 Ids, components and the registry link

- `Story.component`: the groups joined with `/` (`"Inputs/Button"` for `"Inputs/Button/Default"`), or `None` for an id without
  groups. The future sidebar tree and Docs tab group by it.
- `Story.__init__` gains keyword-only `layout=None` and `decorators=()` (sections 3 and 4), which `StoryRegistry.story` passes
  through. `args` and `variant_of` are not constructor parameters: `variant()` sets them on the new story.
- `StoryRegistry.register` records itself on the story (internal `_registry`). It is used only by `Story.variant()`; rendering and
  layout never read it. Calling `.variant()` on a story that was never registered raises `RuntimeError`.
- `Story.variant_of`: the base `Story` for a variant, `None` otherwise. A variant of a variant is a `TypeError` that says to call
  `.variant()` on the base.

### 2.2 `Story.variant(name, *, args=None, layout=None, decorators=None) -> Story`

- **Id.** The variant's id is `f"{component}/{name}"`.
  - A base story without a component is a `ValueError` saying that variants need an id with a group, for example
    `"Button/Default"`.
  - `name` must be non-blank and contain no `/`.
  - A name equal to the base's name is a `ValueError`.
- **Shared with the base:** the render function, controls, docstring and origin (`module`, `qualname`).
- **`args`** overrides control defaults:
  - every key must be a control name, and every value must pass that control's `coerce`; otherwise a `ValueError` names the
    variant, the key and the reason;
  - `Story.args` stores the validated values as a read-only mapping (empty for a base story), and `default_args()` coerces them
    again on every call (1.1).
- **`layout` and `decorators`** (sections 3 and 4): `None` inherits the base's value; anything else replaces it for this variant.
- **Return value:** the new `Story`; it can be ignored.

A component's id must name the component, not the story. In `"Inputs/Spin Box"` the component is `Inputs`, so
`.variant("Large")` would create `"Inputs/Large"`. The README says to give a story that will have variants an id like
`"Inputs/Spin Box/Default"`.

### 2.3 Registration rules

- The registry's existing rule still holds: the same id from the same origin replaces the earlier story in place (a module
  reload); from a different origin it raises.
  - A variant has its base's origin, so re-running a module replaces its variants too, and a variant id that collides with another
    function's story raises.
  - Calling `button.variant("Disabled", ...)` twice in one run replaces the first: the same rule, documented rather than detected.
  - A variant deleted from source stays registered until the module's stories are dropped as a whole (hot reload, milestone 3).
- Order: variants appear in registration order, after their base. Until the sidebar tree (milestone 3), the flat list shows full
  ids (`Inputs/Button/Default`, `Inputs/Button/Disabled`).

### 2.4 The gallery and the examples

Selecting a story builds its controls panel with `values=story.default_args()`, so a variant's controls start at its values and
stay editable.

Examples: two examples get variants, and their base ids gain a `/Default` segment. That is a visible id change, and
`tests/test_examples.py` changes with it.
- `Buttons/Push Button/Default`, with variants `Disabled` and `Checkable`.
- `Inputs/Line Edit/Default`, with variants `Password` and `Read-only`.

## 3. Layout (#18)

- **The `Layout` type.** A `StrEnum` with `CENTERED = "centered"`, `PADDED = "padded"`, `FILL = "fill"`.
- **On a story.** `@story(..., layout=...)` accepts a member, its string value, or `None`. Anything else raises `ValueError` at
  registration listing the valid values. `Story.layout` keeps the declared value (`Layout | None`).
- **The registry default.** `StoryRegistry.default_layout` is a property, default `Layout.PADDED`. Its setter converts with
  `Layout(value)`, so a typo raises at once. A project can set it before or after its stories register.
- **Resolving it.** The window computes a story's layout as `story.layout or self._registry.default_layout`, from the registry
  it was given.
- **The scroll area.** The preview surface moves into a `QScrollArea` (`widgetResizable=True`).
- **The widget's natural size.** For PADDED and CENTERED, the window sets the surface's minimum size to the root widget's
  natural size plus the surface margins. The natural size is the size hint, raised to the minimum size and capped by the maximum
  size. This minimum is what makes the scroll area scroll instead of squashing the widget: without it the surface's minimum size
  hint is invalid, and an 800×600 widget in a 300×200 pane was squashed to 278×178.
  A widget whose `hasHeightForWidth()` is true (a word-wrapped `QLabel`) gets only a minimum width, from its minimum size hint,
  and no minimum height, so it wraps in a narrow pane instead of scrolling sideways; the layout gives it the height its width
  needs.
- **The modes:**
  - `PADDED`: today's behaviour. Top-aligned inside the margins; the width follows the widget's horizontal size policy (a
    button stretches to the full width, as now), and the height is the natural height. A widget larger than the pane scrolls.
  - `CENTERED`: the natural size, centred horizontally and vertically, staying centred when the window is resized. A widget
    larger than the pane scrolls.
  - `FILL`: the widget gets the whole area inside the margins in every direction its size policy lets it grow. In a direction
    it cannot grow (a `QPushButton` is vertically `Fixed`), it keeps its natural size and is centred. Both scroll bars are off,
    and the widget shrinks with the pane down to its minimum size.
- **The surface's minimum.** It is reset for FILL, for the error panel, and when a story is deselected.
- **Errors.** The error panel and the "Load errors" view always use FILL, whatever the story declares.
- **Examples.** At least one story per mode: `Buttons/Push Button/*` becomes CENTERED, a new `Display/Table` example
  (`QTableWidget`) uses FILL, and the rest stay PADDED.

## 4. Decorators (#17)

### 4.1 Definition

```python
Decorator = Callable[[QWidget, StoryContext], QWidget]
```

A decorator receives the widget built so far and the story's context, and returns the widget to show instead. It either returns
the same widget after configuring it, or a new wrapper that contains the received widget as a descendant.

### 4.2 Order and sources

Decorators read like stacked Python `@decorators`: **the first in the list is the outermost**.
- The story's own `decorators` wrap the story widget: the last one in the list is applied first, closest to the widget.
- The registry's decorators (`StoryRegistry.decorators`, a plain `list[Decorator]`) wrap the result, again first-outermost. A
  project may append to it, for example in its stories package `__init__.py`; it is read at render time.
- So `@story(..., decorators=[padding(24), fixed_size(320, 200)])` gives a 320×200 card inside 24 pixels of padding, which is
  #17's acceptance example.
- A variant's `decorators=None` inherits the base's list; a list replaces it. Registry decorators always apply.

### 4.3 Rendering

Internal module `registry/rendering.py`:

```python
@dataclass(frozen=True, slots=True)
class RenderedStory:
    widget: QWidget   # what the story function returned, undecorated
    root: QWidget     # the outermost widget, to place in the preview

class StoryRenderError(Exception):
    title: str        # for the error panel
    details: str      # traceback starting at the failing user code

def render_story(story: Story, ctx: StoryContext, *, registry: StoryRegistry) -> RenderedStory: ...
```

`render_story`:
- calls the story function;
- checks the result is a `QWidget`;
- applies the story's decorators, then `registry.decorators`, in the order of 4.2;
- after each decorator, checks that it returned a `QWidget` that is, or contains, the story widget.

Failures raise `StoryRenderError(title, details) from error`. On every failure path, `render_story` first hides and calls
`deleteLater()` on every widget it created or received that is still alive and not owned by another, so nothing leaks. The
titles keep milestone 1's wording exactly, which `tests/test_window.py` asserts:

| Failure | Title |
| --- | --- |
| The story raises | `"<id> raised <Type>: <message>"` |
| The story returns a non-widget | `"<id> returned <repr>, expected a QWidget"` |
| A decorator raises | `"<id>: decorator <repr> raised <Type>: <message>"` |
| A decorator returns a non-widget | `"<id>: decorator <repr> returned <repr>, expected a QWidget"` |
| A decorator drops the widget | `"<id>: decorator <repr> returned a widget that does not contain the story's widget"` |

The details are the traceback with the library's own leading frames trimmed. Today's `_story_traceback` moves from
`gui/window.py` into this module.

The window calls `render_story(story, ctx, registry=self._registry)` and catches `StoryRenderError`:
- it logs with `logger.error(..., exc_info=error)`, so the record carries the exception as today, and shows the error panel;
- on success, it places `root` in the preview with the layout from section 3;
- it keeps `widget` for `current_preview_widget()`, the undecorated widget, as #17 requires;
- on rebuild, it deletes `root`, which deletes everything inside it.

`Story.__call__` stays the plain function call.

### 4.4 Built-in decorators

In `pyside6_storybook/decorators/`, one module each, re-exported from `pyside6_storybook.decorators`:

- `padding(horizontal, vertical=None)`: a transparent `QWidget` with those content margins; `vertical` defaults to
  `horizontal`. Negative values raise `ValueError`.
- `frame()`: a `QFrame` with the `StyledPanel` shape, drawn from the palette, with zero margins.
- `fixed_size(width, height)`: calls `setFixedSize` on the received widget and returns it, with no wrapper. Non-positive sizes
  raise `ValueError`.

Each returned decorator has a readable `__repr__` (`padding(24)`), used in error titles and the future Docs tab.

## 5. Module layout

| Path | Contents |
| --- | --- |
| `controls/color_control.py`, `enum_control.py`, `file_control.py` | the three new controls (#15) |
| `controls/_options.py` | functions shared by the controls: label derivation, float step and decimals (moved from the panel) |
| `registry/story_definition.py` | `Story` with `component`, `variant_of`, `args`, `layout`, `decorators`, `variant()` |
| `registry/layout.py` | `Layout` (#18) |
| `registry/rendering.py` | `RenderedStory`, `StoryRenderError`, `render_story`, traceback trimming (#17) |
| `registry/story_context.py` | gains the `Decorator` type beside `StoryFunction` (#17); defining it in `decorators/` would be an import cycle |
| `decorators/` | `padding.py`, `frame.py`, `fixed_size.py`; re-exports `Decorator` (#17) |
| `gui/editors/` | one module per editor, plus `_wheel.py` for the wheel filter (#16, #15) |
| `gui/controls_panel.py` | the form over the editors |
| `gui/window.py` | scrollable controls section, scrolled preview with layout modes, `render_story` |

## 6. Testing

Each PR adds tests next to the code it changes and keeps `tests/test_examples.py` in step with the examples. In particular:

- **Controls:** `coerce` accepts and rejects per the table in 1.1; every new field's validation; `display_label`; the color
  grammar and the alpha rules; enum options, including `Qt.AlignmentFlag.AlignCenter` and the rejection of an unnamed
  combination; float precision against `effective_decimals`.
- **Editors:**
  - driven the way a user does (typing, clicking, or setting a value on the editor);
  - exactly one `valuesChanged` per edit, including slider and spin box mirroring;
  - the slider reaches the maximum;
  - a wheel event on an unfocused editor leaves its value alone;
  - focus proxies and accessible names;
  - dialogs monkeypatched.
- **Variants:**
  - ids and components;
  - `args` reaching the render function and the panel;
  - invalid `args`, the no-component and same-name errors, and variants of variants;
  - reload replacing variants without duplicates.
- **Layout:**
  - the previewed widget's geometry in each mode, and again after a window resize;
  - an oversized widget scrolls in PADDED and CENTERED, keeping at least its natural size, and has no scroll bars in FILL;
  - a vertically fixed widget in FILL;
  - the registry default and its validation.
- **Decorators:**
  - application order with story and registry decorators, including #17's 320×200 inside 24 px example;
  - each built-in's geometry;
  - the five failure titles;
  - no widget left alive after a rebuild or a failure (`shiboken6.isValid` after processing deferred deletes);
  - `current_preview_widget()` is the undecorated widget;
  - the five-line `QGroupBox` decorator from the issue works as written.
- **Unchanged tests:** existing tests keep passing, except where a PR deliberately changes behaviour and says so (renamed example
  ids, the stricter defaults).

## 7. Documentation

Each PR updates:
- the README section it affects: the controls table, a "Variants" section (with the component-id advice from 2.2), and a
  "Layout and decorators" section;
- the changelog;
- `AGENTS.md`, where the module layout changes.

`tests/test_readme.py` keeps the README's code runnable; new README examples get the same treatment.

## 8. Out of scope

- Inferring controls from type hints.
- Conditional controls, and per-variant controls.
- A decorator toolbar.
- Date, font, list and object controls.
- Arbitrary layouts beyond the three modes; use a decorator.

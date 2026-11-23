# The gallery

## The window

The window has three panes: the story list on the left, the preview of the selected story in the middle, and the theme switch and
the story's controls on the right. The middle pane has two tabs: "Canvas", the rendered story, and "Docs", described below. The right
pane has two as well: "Controls" and "Actions", described under [Logging actions](#logging-actions).

The story list is a tree built from the story ids. Each `/`-separated segment but the last is a branch, and the stories are leaves,
in the order they were registered. A component below the top level that has only one story, such as
`Forms/Sign-in Form/Default`, is shown as that story's row. When both `A/B` and `A/B/C` are stories, `B` is a story row with `C`
listed under it. Source files that failed to load are listed in a "Load errors (N)" row at the end.

Selecting a story, with the mouse or the Up and Down keys, opens it at once. The search field above the tree keeps the stories whose
id contains what you type, ignoring case, together with the branches they are in, which it expands. Typing never changes the story in
the preview: a selected story that the search hides stays in the preview, and is shown selected again when it matches. Clearing the
search brings back the branches you had expanded or collapsed.

## Keyboard

The whole window works from the keyboard. Tab visits the search field, the story tree, the preview tabs, the canvas controls, the
preview, then the theme switch, the side pane tabs and the controls; Shift+Tab goes back. Every control has an accessible name, and
the preview area is named "Preview of" followed by the story id. Choose "Keyboard shortcuts" in the Help menu, or press `F1`, to see
this list in the window.

| Keys | Action |
| --- | --- |
| `Ctrl+F` or `/` | Focus the search field and select its text. `/` types a slash while a text field, spin box or editable combo box has focus. |
| `Ctrl+Alt+Down` and `Ctrl+Alt+Up` | Open the next or previous story in the list. Stories the search hides are skipped, and the branch of the story is expanded. |
| `Ctrl+T` | Switch to the next theme. |
| `F6` and `Shift+F6` | Move focus to the next or previous pane (story list, preview, side pane), at the widget that had focus there last. |
| `Ctrl++` (or `Ctrl+=`), `Ctrl+-` and `Ctrl+0` | Zoom in, zoom out and reset the zoom, while focus is in the preview pane. |
| `F1` | Show the keyboard shortcuts. |
| Down in the search field | Select the first story the search keeps. |
| Enter in the search field | Open the first story the search keeps. |
| Escape in the search field | Clear the search; when it is empty, move focus to the tree. |
| Escape in the tree | Clear the search. |
| Left and Right in the tree | Collapse and expand a branch. |

`Alt+Down` is not a window shortcut: it opens a combo box's popup, as it does in any Qt application. Rebuilding the preview, after a
control edit or a theme switch, never takes focus from the control you are using. If the focus was inside the story's own widget, it
moves to the preview area instead.

## The canvas

Above the preview, two menus and the zoom buttons change how a story is shown. None of them changes the story: it is built the same way
and receives the same arguments.

- **Background** is what the story sits on: "Window" (the default), "Base" or "Alternate Base" (a colour of the active theme, which a
  theme switch keeps up to date) or "Checkerboard" (8-pixel squares of the theme's Base and Mid colours, to judge transparency).
- **Size** is "Fit" (the default: the story is placed in the whole preview, as the story's `layout` says), one of the built-in sizes
  "Phone portrait" (320 × 480), "Phone landscape" (480 × 320) and "Dialog" (800 × 600), your own sizes (below), or "Custom…", which
  shows a Width and a Height field. With a size selected, the area the story is placed in is exactly that many pixels, so a `FILL`
  story is exactly that size and a `CENTERED` story is centred in it. The area is outlined, centred in the preview, and the preview
  scrolls when the window is smaller. The label at the right shows the size.

- **Zoom** shows the preview at 50, 67, 100, 150, 200, 300 or 400%. The buttons below the menus step to the previous or next level
  and reset to 100%; `Ctrl++` (or `Ctrl+=`), `Ctrl+-` and `Ctrl+0` do the same while focus is in the preview pane, and `Ctrl` with the
  mouse wheel, also over the story's own widgets, zooms one level per notch. Zooming keeps the centre of the visible area in place; with the wheel, the point under
  the cursor stays under it. At 100% the live widget is shown. At any other level the canvas shows an image of the
  preview scaled without smoothing, so 400% turns a one-pixel line into four sharp pixels. A zoomed preview is not interactive: return
  to 100% to click, type or open popups. The image is taken again when a control, the theme, the background or the size changes. A level
whose image would have more than 64 million device pixels is skipped for a large size.

The choices stay while you switch stories, switch themes or reload; they are not saved between runs.

To list sizes of your own, such as the screens your application supports, append `SizePreset` objects (a name, a width and a height in
pixels, each from 1 to 10 000) to `size_presets` of the registry. They follow the built-in sizes in the Size menu:

```python
from pyside6_storybook import SizePreset, default_registry

default_registry.size_presets.append(SizePreset("Tablet", 768, 1024))
default_registry.size_presets.append(SizePreset("Small laptop", 1280, 720))
```

## The Docs tab

The Docs tab describes the selected story, top to bottom:

- the docstring of the module the story is defined in, and the story function's docstring (a heading appears only for a docstring
  that exists);
- a table of the story's controls with each control's type, its starting value and its range or options (a variant shows its own
  starting values), or "No controls.";
- for a story with variants, the list "Stories of <component>": the base story and its variants, each one a link that opens that
  story, and the current one as plain text;
- the source code of the story function in a read-only view, with a "Copy" button that puts it on the clipboard. A story whose source
  cannot be read, such as one built from a `functools.partial`, shows "Source not available for this story." instead.

The tab updates when you select another story, not when you change a control.

## Logging actions

The Actions tab lists what a story reports, newest first, with the time, the action and its arguments. A story opts in signal by
signal with `ctx.log_signal`, logs every signal of a widget with `ctx.log_signals` (see [Logging every signal](#logging-every-signal)),
or logs anything with `ctx.log`:

```python
from PySide6.QtWidgets import QPushButton, QWidget

from pyside6_storybook import StoryContext, story


@story("Buttons/Counter")
def counter(ctx: StoryContext) -> QWidget:
    """A button that logs its signals."""
    button = QPushButton("Click me")
    ctx.log_signal(button.clicked)
    ctx.log_signal(button.toggled, name="toggle")
    button.clicked.connect(lambda: ctx.log("custom", "any", 1))
    return button
```

`log_signal` shows the arguments the signal delivers to a slot, so `QPushButton.clicked` reads `clicked()` and a slider's
`valueChanged` reads `valueChanged(5)`. The signal's own name is used unless you pass `name=`. Arguments are shortened to 200
characters, and the panel keeps the last 500 actions. Clear empties it, and so does selecting another story; changing a control or the
theme builds the story again and keeps the log. Under a plain `StoryContext`, such as a test builds, `log_signal`, `log_signals` and `log`
do nothing, so the story needs no check. `StoryContext.actions` is the `ActionSink` that receives the actions.

## Logging every signal

`ctx.log_signals(obj)` does what `log_signal` does for every signal that the classes of `obj` declare. For a widget those are the
signals below `QWidget`: a `QPushButton` logs `pressed`, `released`, `clicked` and `toggled`. It leaves out what every widget has
(`objectNameChanged`, `windowTitleChanged`, `customContextMenuRequested` and the like) and `updateRequest`, which fires on every repaint;
use `log_signal` to log one of those. `exclude=` takes the names of signals to skip, and a name the object has no signal of is logged
as a warning, because the signals differ between Qt versions. Call it after you configure the widget, or the emissions of the setup
(`addItems` emits `currentIndexChanged`) are logged on every render.

An item view has no selection signal of its own, so log its `selectionModel()` (`selectionChanged`, `currentChanged`) and its model
(`dataChanged`). Call `log_signals` after `setModel`, because a view's selection model belongs to the model:

```python
from PySide6.QtWidgets import QComboBox, QWidget

from pyside6_storybook import StoryContext, story


@story("Inputs/Logged Combo Box")
def logged_combo_box(ctx: StoryContext) -> QWidget:
    """A combo box that logs every signal except the ones that fire while the pointer moves over the list."""
    box = QComboBox()
    box.addItems(["Apple", "Banana", "Cherry"])
    ctx.log_signals(box, exclude=("highlighted", "textHighlighted"))
    return box
```

```python
from PySide6.QtCore import QStringListModel
from PySide6.QtWidgets import QListView, QWidget

from pyside6_storybook import StoryContext, story


@story("Views/Logged List View")
def logged_list_view(ctx: StoryContext) -> QWidget:
    """A list view that logs its selection and its model's data."""
    model = QStringListModel(["Apple", "Banana", "Cherry"])
    view = QListView()
    view.setModel(model)
    ctx.log_signals(view.selectionModel())
    ctx.log_signals(model)
    return view
```

Each connection ends when its object is deleted. A model or selection model that outlives the story's widget gets one more
connection on every render, so give it to `log_signals` only when the story creates it. A signal whose argument type PySide6 cannot
convert is not connected, and a warning names it.

## Hot reload

The gallery loads your stories again when you save a file, so an edit shows in the preview without a restart. It watches the story
files you named (and every folder below a folder target, so a new story file is noticed), the modules those stories import from your
project, and the story modules of a package or entry point. A change is acted on 300 ms after the last write, and one burst of saves
reloads once. The status bar shows "Reloaded 14:02:11", or "Reload failed 14:02:11: 1 story source failed to load".

A reload drops from `sys.modules` the story modules and their parent packages, and every other module whose file is below the working
directory or a `pythonpath` folder from `pyproject.toml` (not one in `site-packages`, `.venv`, `venv`, `node_modules` or a hidden folder),
then loads the targets again into a new registry. Everything your project owns runs again in import order, so an edited widget class is
picked up like an edited story, and a package `__init__` that appends to `default_registry.decorators` or `size_presets` ends up with
one entry, not two.

- **A good reload** replaces the story list. The selected story stays selected, and each control keeps its value when the new control of
  the same name accepts it; an enum control keeps the member of the same name in the reloaded enum class. If the story is gone, the story
  now at its position in the list is selected, or the last one. The Actions log stays for the same story, and the theme and the
  canvas settings do not change.
- **A failed reload** changes nothing: the previous stories stay, the preview shows the errors, and the status bar says so until the next
  good reload. A reload fails when it finds no story, or when a source fails that was not already failing. Changing a control or the
  theme meanwhile shows the last good story again. Fixing the file, including a story file that never imported, reloads it.

Limits: modules installed in `site-packages` are not reloaded unless they are story modules, state kept outside the project (a database
connection, a registry in a library) survives a reload, and a story file's own side effects at import time run again. A module the
project imports that failed to import is not watched until a story reloads. `--no-reload` turns it off, and code that calls
`pyside6_storybook.run(registry)` directly gets no reload.

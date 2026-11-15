# pyside6-storybook
Storybook-style component explorer for PySide6: browse widgets in isolation, edit their properties live, switch themes, and smoke-test every story with pytest.

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

`pyside6-storybook --list` prints the story ids and, on standard error, which of these sources it used.

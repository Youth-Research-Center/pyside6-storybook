# Finding stories

The gallery, the pytest plugin and `--list` find stories the same way. This page says which files count as stories and where the
default sources are configured.

## Which files are stories

Each target you name is, in this order of precedence:

- an existing **folder**: every file named `*_story.py` or `*_stories.py` below it is loaded. `test_*` files, hidden folders,
  `__pycache__` and virtual environments (a folder with a `pyvenv.cfg`) are skipped;
- an existing **`.py` file**: that file is loaded, whatever its name;
- a **dotted module name**: the module is imported, and for a package also its submodules named `*_story` or `*_stories`, in the
  package and in its regular subpackages (again skipping `test_*` files).

Story files can import your application, and each other, like any module of your project: the working directory is put on `sys.path`,
and so are the `pythonpath` folders of `pyproject.toml`, ahead of it. A file inside a package (its folder has an `__init__.py`) is
imported under its full dotted name, so relative imports work and a file reached by path and by module name is one module. A file
outside any package is imported under its own name, with its folder on `sys.path`, so siblings can import it.


## Where your stories come from

`pyside6-storybook path/to/stories` loads the folders, `.py` files and dotted module names you give it; `--examples` adds the
built-in example stories. Run without targets, it looks in this order:

1. **`pyproject.toml`** in the current directory:

   ```toml
   [tool.pyside6-storybook]
   stories = ["stories"]   # folders, .py files or dotted module names, relative to this file
   pythonpath = ["src"]    # optional: folders put on sys.path first, so stories can import your application
   theme_provider = "my_app.theming:provider"   # optional: your own themes (see [Choosing a theme provider](themes.md#choosing-a-theme-provider))
   theme = "Dark"          # optional: the theme to start in
   ```

2. **Entry points** of installed packages, each naming a module of stories:

   ```toml
   [project.entry-points."pyside6_storybook.stories"]
   my_widgets = "my_widgets.stories"
   ```

3. **The built-in examples**, only when neither of the above is configured. A configured source that fails to load is reported
   as an error; it never falls back to the examples.

`pythonpath`, `theme_provider` and `theme` are read from `pyproject.toml` also when you name targets or pass `--examples`, so a
`pyproject.toml` that is not valid is an error then too; `stories` is ignored when there are targets.

A story module that fails to import is listed in the gallery under "Load errors" with its traceback, and the gallery opens with
the stories that did load.

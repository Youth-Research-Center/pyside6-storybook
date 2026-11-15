"""Names, patterns and messages shared by the story discovery modules."""

STORY_FILE_SUFFIXES = ("_story", "_stories")
"""A discovered story module's name ends with one of these (``button_story.py``, ``inputs_stories.py``)."""

TEST_FILE_PREFIX = "test_"
"""Files that start with this are pytest modules and are never discovered, even when they end with a story suffix."""

VIRTUAL_ENVIRONMENT_MARKER = "pyvenv.cfg"
"""A folder containing this file is a virtual environment and is not searched."""

CACHE_FOLDER_NAME = "__pycache__"
"""Python's bytecode cache folder, which is not searched."""

SYNTHETIC_MODULE_PREFIX = "_pyside6_storybook_"
"""Prefix of the module name given to a story file outside any package whose own name is taken."""

NOT_FOUND_MESSAGE = "no such file, folder or module"
"""Reported for a target that is neither an existing path nor an importable module."""

CONFIG_FILE_NAME = "pyproject.toml"
"""The file in the working directory whose ``[tool.pyside6-storybook]`` table names the default story sources."""

CONFIG_TABLE = "pyside6-storybook"
"""The name of the table under ``[tool]`` in ``pyproject.toml``."""

ENTRY_POINT_GROUP = "pyside6_storybook.stories"
"""Installed packages advertise story modules under this entry-point group; each entry point names a module."""

EXAMPLES_MODULE = "pyside6_storybook.examples"
"""The package of built-in example stories."""

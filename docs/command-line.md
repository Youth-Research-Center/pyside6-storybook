# Command line

`pyside6-storybook` opens the gallery with the stories in the folders, files and modules you name. `python -m pyside6_storybook` takes
the same arguments.

```bash
pyside6-storybook [OPTIONS] [TARGET ...]
```

`TARGET` is a folder, a `.py` file or a dotted module name, and several are allowed. Without a target the command uses the default
sources (see [Finding stories](finding-stories.md#where-your-stories-come-from)).

## Options

| Option | Meaning |
| --- | --- |
| `--examples` | Also load the built-in example stories. |
| `--theme NAME` | The theme to start in (built-in: Light, Dark, System). |
| `--theme-provider MODULE:ATTRIBUTE` | Use your application's themes instead of the built-in ones (see [theme providers][providers]). |
| `--list` | Print the story ids and exit, without a window (works without a display). |
| `--no-reload` | Do not load the stories again when a file changes (see [Hot reload](gallery.md#hot-reload)). |
| `--version` | Print the version and exit. |
| `--debug-info` | Print the versions of pyside6-storybook, PySide6, Qt, Python and the platform, for a bug report, and exit. |

With `--list`, standard error also says which source the stories came from and which theme provider is used with its theme names. A
theme provider that cannot be loaded, or an unknown theme, prints an error and exits with code 1; the built-in themes are never used
instead.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Success: the gallery closed normally, `--list` found every story, or `--version` or `--debug-info` was printed. |
| `1` | An error, listed below the table. |
| `2` | A usage error: an unknown option or a missing value. |

Exit code 1 means the configuration is wrong, the theme provider cannot be loaded, the theme is unknown, no stories were found, a target
does not exist, or (with `--list`) any story module failed to load. `--help` also exits with 0.

Story modules that fail to load are reported on standard error, and the gallery still opens with the stories that did load and lists
the failures under "Load errors".

[providers]: themes.md#choosing-a-theme-provider

# Security policy

## Supported versions

Before 1.0, only the latest release gets fixes. A fix ships as a patch release (see "A patch release" in [RELEASING.md](RELEASING.md)).

## Reporting a vulnerability

Report a vulnerability privately. Do not open a public issue.

- Use GitHub's
  [private vulnerability reporting](https://github.com/Youth-Research-Center/pyside6-storybook/security/advisories/new), or write to
  mail@icm.hr.
- Include the affected version (the output of `pyside6-storybook --debug-info`), what an attacker could do, and the steps to reproduce.
- The maintainers acknowledge the report, agree on a fix and a disclosure date with you, and credit you in the advisory unless you ask
  them not to.
- No response time is promised, because the project is run by volunteers.

## Running project code is the design

The gallery (`pyside6-storybook`, with or without `--list`) and the pytest plugin import Python modules, and importing a module runs its
code. The modules come from:

- the targets you name: on the command line, in `--storybook-stories`, or in the `storybook_stories` ini key;
- `[tool.pyside6-storybook]` in the working directory's `pyproject.toml`: its `stories`, and its `theme_provider` (also
  `--theme-provider`, `--storybook-theme-provider` and `storybook_theme_provider`);
- the `pyside6_storybook.stories` entry points of every installed package, which are used when no target is configured;
- the working directory and the `pythonpath` folders, which are put first on `sys.path`, so a module there shadows an installed module of
  the same name.

Hot reload imports changed modules again. Running the gallery or the plugin in an untrusted checkout therefore runs that checkout's code,
like running its tests does, so treat it the same way. None of this is a vulnerability.

## What is in scope

- Code running that none of the sources above would load.
- The gallery making a network request. It never should.
- A published wheel or sdist that does not match the tagged source, or a weakness in the release workflow.
- A dependency problem that affects pyside6-storybook users.

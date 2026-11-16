"""Where the supported icon library keeps its SVGs inside its npm package."""

from collections.abc import Callable

DEFAULT_SOURCE = "phosphor"
KNOWN_WEIGHTS = ("thin", "light", "regular", "bold", "fill", "duotone")


def _phosphor_path(name: str, weight: str) -> str:
    suffix = "" if weight == "regular" else f"-{weight}"
    return f"assets/{weight}/{name}{suffix}.svg"


# Where each supported library keeps its SVGs inside its npm package. Adding a library means adding a layout here.
LAYOUTS: dict[str, Callable[[str, str], str]] = {"phosphor": _phosphor_path}


def upstream_path(source: str, name: str, weight: str) -> str:
    """Return the path of an icon's SVG inside the source's npm package.

    Args:
        source: Name of a source with a registered layout.
        name: The icon's name in that package.
        weight: One of ``KNOWN_WEIGHTS``.

    Returns:
        The path relative to the package root.
    """
    return LAYOUTS[source](name, weight)

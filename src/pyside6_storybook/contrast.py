"""WCAG contrast-ratio helpers. Pure Python, no Qt."""

from __future__ import annotations


def _srgb_channel_to_linear(channel: float) -> float:
    """Convert an sRGB channel value (0-1) to its linear-light equivalent."""
    if channel <= 0.03928:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4


def _relative_luminance(hex_color: str) -> float:
    """Return the WCAG relative luminance (0 is black, 1 is white) of a ``#RRGGBB`` colour."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        raise ValueError(f"Expected a 6-digit hex color, got {hex_color!r}")
    r, g, b = (int(hex_color[i : i + 2], 16) / 255.0 for i in (0, 2, 4))
    r_lin, g_lin, b_lin = (_srgb_channel_to_linear(c) for c in (r, g, b))
    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin


def contrast_ratio(fg_hex: str, bg_hex: str) -> float:
    """Return the WCAG contrast ratio between two colours.

    Args:
        fg_hex: A ``#RRGGBB`` or ``RRGGBB`` colour.
        bg_hex: A ``#RRGGBB`` or ``RRGGBB`` colour.

    Returns:
        A ratio from 1.0 (identical colours) to 21.0 (black on white).

    Raises:
        ValueError: If a colour is not six hex digits.
    """
    l1 = _relative_luminance(fg_hex)
    l2 = _relative_luminance(bg_hex)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def pick_contrasting_text(bg_hex: str) -> str:
    """Return whichever of black and white has the higher contrast against a background.

    Args:
        bg_hex: The background as ``#RRGGBB``.

    Returns:
        ``"#FFFFFF"`` or ``"#000000"``.
    """
    white_ratio = contrast_ratio("#FFFFFF", bg_hex)
    black_ratio = contrast_ratio("#000000", bg_hex)
    return "#FFFFFF" if white_ratio >= black_ratio else "#000000"


__all__ = ["contrast_ratio", "pick_contrasting_text"]

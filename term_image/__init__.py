"""
term-image

Display images in a terminal

Provides
========
    1. A library with utilities to display images in a terminal in various ways.
    2. A CLI to display individual images from a local filesystem or URLs.
    3. A TUI to browse multiple images on a local filesystem or from URLS.

It basically works by converting images into text, since that's all conventional
terminals can represent.
Colored output is achieved using ANSI 24-bit color escape codes.

AUTHOR: AnonymouX47 <anonymoux47@gmail.com>
Copyright (c) 2022
"""

from __future__ import annotations

__all__ = ("set_font_ratio", "get_font_ratio")
__author__ = "AnonymouX47"

version_info = (0, 3, 1)
__version__ = ".".join(map(str, version_info))


def get_font_ratio() -> float:
    """Returns the set libray-wide :term:`font ratio`."""
    return _font_ratio


def set_font_ratio(ratio: float) -> None:
    """Sets the library-wide :term:`font ratio`.

    Args:
        ratio: The aspect ratio (i.e `width / height`) of a character cell in the
        terminal emulator.

    This value is taken into consideration when setting image sizes in order for images
    drawn to the terminal to have a proper perceived scale.

    If you can't determine this value from your terminal's configuration,
    you might have to try different values till you get a good fit.
    Normally, this value should be between 0 and 1, but not too close to either.

    IMPORTANT:
        Changing the font ratio does not automatically affect any image whose size has
        already been set. For a change in font ratio to have any effect, it's size has
        to be set again.
    """
    from . import image

    global _font_ratio

    if not isinstance(ratio, float):
        raise TypeError(f"Font ratio must be a float (got: {type(ratio).__name__})")
    if ratio <= 0:
        raise ValueError(f"Font ratio must be positive (got: {ratio})")

    # cell-size == width * height
    # font-ratio == width / height
    # There are two pixels vertically arranged in one character cell
    # pixel-size == width * height/2
    # pixel-ratio == width / (height/2) == 2 * (width / height) == 2 * font-ratio
    _font_ratio = ratio
    image._pixel_ratio = 2 * ratio


_font_ratio = 0.5  # Default

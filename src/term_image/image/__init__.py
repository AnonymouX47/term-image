"""
.. Core Library Definitions
"""

from __future__ import annotations

__all__ = (
    "auto_style",
    "AutoImage",
    "from_file",
    "from_url",
    "ImageSource",
    "Size",
    "ImageMeta",
    "BaseImage",
    "GraphicsImage",
    "TextImage",
    "BlockImage",
    "ITerm2Image",
    "KittyImage",
    "ImageIterator",
)

from typing import Optional, Tuple, Union

import PIL

from .block import BlockImage  # noqa:F401
from .common import (  # noqa:F401
    BaseImage,
    GraphicsImage,
    ImageIterator,
    ImageMeta,
    ImageSource,
    Size,
    TextImage,
)
from .iterm2 import ITerm2Image  # noqa:F401
from .kitty import KittyImage  # noqa:F401


def auto_style() -> ImageMeta:
    """Selects the render style that best suits the current terminal emulator.

    Returns:
        An image class (a subclass of :py:class:`BaseImage`).
    """
    for cls in _styles:
        if cls.is_supported():
            break
    return cls


def AutoImage(
    image: PIL.Image.Image,
    *,
    width: Optional[int] = None,
    height: Optional[int] = None,
    scale: Tuple[float, float] = (1.0, 1.0),
) -> BaseImage:
    """Creates an image instance from a PIL image instance.

    Returns:
        An instance of the automatically selected render style (as returned by
        :py:func:`auto_style`).

    Same arguments and raised exceptions as the :py:class:`BaseImage` class constructor.
    """
    return auto_style()(image, width=width, height=height, scale=scale)


def from_file(
    filepath: str,
    **kwargs: Union[None, int, Tuple[float, float]],
) -> BaseImage:
    """Creates an image instance from an image file.

    Returns:
        An instance of the automatically selected render style (as returned by
        :py:func:`auto_style`).

    Same arguments and raised exceptions as :py:meth:`BaseImage.from_file`.
    """
    return auto_style().from_file(filepath, **kwargs)


def from_url(
    url: str,
    **kwargs: Union[None, int, Tuple[float, float]],
) -> BaseImage:
    """Creates an image instance from an image URL.

    Returns:
        An instance of the automatically selected render style (as returned by
        :py:func:`auto_style`).

    Same arguments and raised exceptions as :py:meth:`BaseImage.from_url`.
    """
    return auto_style().from_url(url, **kwargs)


# In order of preference, based on image quality and style performance/functionality.
# NOTE: 'iterm2' comes before 'kitty' because the query for 'kitty' support detection
# messes up iTerm2's window title.
_styles = (ITerm2Image, KittyImage, BlockImage)

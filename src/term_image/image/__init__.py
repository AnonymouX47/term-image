"""
.. Core Library Definitions
"""

from __future__ import annotations

__all__ = (
    "AutoImage",
    "from_file",
    "from_url",
    "ImageSource",
    "BaseImage",
    "GraphicsImage",
    "TextImage",
    "BlockImage",
    "ITerm2Image",
    "KittyImage",
    "TermImage",
    "ImageIterator",
)

from typing import Optional, Tuple, Union

import PIL

from .block import BlockImage, TermImage  # noqa:F401
from .common import (  # noqa:F401
    BaseImage,
    GraphicsImage,
    ImageIterator,
    ImageSource,
    TextImage,
)
from .iterm2 import ITerm2Image  # noqa:F401
from .kitty import KittyImage  # noqa:F401


def AutoImage(
    image: PIL.Image.Image,
    *,
    width: Optional[int] = None,
    height: Optional[int] = None,
    scale: Tuple[float, float] = (1.0, 1.0),
) -> BaseImage:
    """Convenience function for creating an image instance from a PIL image instance.

    Returns:
        An instance of a subclass of :py:class:`BaseImage`.

    Same arguments and raised exceptions as the :py:class:`BaseImage` class constructor.
    """
    return _best_style()(image, width=width, height=height, scale=scale)


def from_file(
    filepath: str,
    **kwargs: Union[None, int, Tuple[float, float]],
) -> BaseImage:
    """Convenience function for creating an image instance from an image file.

    Returns:
        An instance of a subclass of :py:class:`BaseImage`.

    Same arguments and raised exceptions as :py:meth:`BaseImage.from_file`.
    """
    return _best_style().from_file(filepath, **kwargs)


def from_url(
    url: str,
    **kwargs: Union[None, int, Tuple[float, float]],
) -> BaseImage:
    """Convenience function for creating an image instance from an image URL.

    Returns:
        An instance of a subclass of :py:class:`BaseImage`.

    Same arguments and raised exceptions as :py:meth:`BaseImage.from_url`.
    """
    return _best_style().from_url(url, **kwargs)


def _best_style():
    for cls in _styles:
        if cls.is_supported():
            break
    return cls


# In order of preference, based on image quality and style performance/functionality.
# NOTE: 'iterm2' should come before 'kitty', if not any other reason, at least because
# the query for 'kitty' support detection messes up iTerm2's window title.
_styles = (ITerm2Image, KittyImage, BlockImage)

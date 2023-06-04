"""
.. Core Library Definitions
"""

from __future__ import annotations

__all__ = (
    "auto_image_class",
    "AutoImage",
    "from_file",
    "from_url",
    "ImageSource",
    "Size",
    "BaseImage",
    "TextImage",
    "BlockImage",
    "GraphicsImage",
    "ITerm2Image",
    "KittyImage",
    "ImageIterator",
)

import os
from typing import Optional, Union

import PIL

from .block import BlockImage
from .common import (
    BaseImage,
    GraphicsImage,
    ImageIterator,
    ImageMeta,
    ImageSource,
    Size,
    TextImage,
)
from .iterm2 import ITerm2Image
from .kitty import KittyImage


def auto_image_class() -> ImageMeta:
    """Selects the image render style that best suits the current terminal emulator.

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
) -> BaseImage:
    """Creates an image instance from a PIL image instance.

    Returns:
        An instance of the automatically selected image render style (as returned by
        :py:func:`auto_image_class`).

    Same arguments and raised exceptions as the :py:class:`BaseImage` class constructor.
    """
    return auto_image_class()(image, width=width, height=height)


def from_file(
    filepath: Union[str, os.PathLike],
    **kwargs: Union[None, int],
) -> BaseImage:
    """Creates an image instance from an image file.

    Returns:
        An instance of the automatically selected image render style (as returned by
        :py:func:`auto_image_class`).

    Same arguments and raised exceptions as :py:meth:`BaseImage.from_file`.
    """
    return auto_image_class().from_file(filepath, **kwargs)


def from_url(
    url: str,
    **kwargs: Union[None, int],
) -> BaseImage:
    """Creates an image instance from an image URL.

    Returns:
        An instance of the automatically selected image render style (as returned by
        :py:func:`auto_image_class`).

    Same arguments and raised exceptions as :py:meth:`BaseImage.from_url`.
    """
    return auto_image_class().from_url(url, **kwargs)


# In order of preference, based on image quality and style performance/functionality
_styles = (KittyImage, ITerm2Image, BlockImage)

"""
Custom Exceptions
=================
"""

from __future__ import annotations


class TermImageError(Exception):
    """Exception baseclass. Raised for generic errors."""


class TermImageException(TermImageError):
    """*Deprecated since version 0.4.0:* Replaced by :py:class:`TermImageError`."""


class URLNotFoundError(FileNotFoundError, TermImageError):
    """Raised for 404 errors."""


class InvalidSizeError(ValueError, TermImageError):
    """Raised for invalid image sizes."""


class InvalidSize(InvalidSizeError):
    """*Deprecated since version 0.4.0:* Replaced by :py:class:`InvalidSizeError`."""


# Style-specific exceptions


class BaseImageError(TermImageError):
    """Raised for style-specific errors for subclasses of
    :py:class:`BaseImage <term_image.image.BaseImage>` defined outside this package.
    """


class GraphicsImageError(TermImageError):
    """Raised for errors specific to
    :py:class:`GraphicsImage <term_image.image.GraphicsImage>` and style-specific
    errors for subclasses defined outside this package.
    """


class TextImageError(TermImageError):
    """Raised for errors specific to
    :py:class:`TextImage <term_image.image.TextImage>` and style-specific
    errors for subclasses defined outside this package.
    """


class BlockImageError(TermImageError):
    """Raised for errors specific to
    :py:class:`BlockImage <term_image.image.BlockImage>` and style-specific
    errors for subclasses defined outside this package.
    """


class ITerm2ImageError(TermImageError):
    """Raised for errors specific to
    :py:class:`ITerm2Image <term_image.image.ITerm2Image>` and style-specific
    errors for subclasses defined outside this package.
    """


class KittyImageError(TermImageError):
    """Raised for errors specific to
    :py:class:`KittyImage <term_image.image.KittyImage>` and style-specific
    errors for subclasses defined outside this package.
    """


def _style_error(cls: type):
    for cls in cls.__mro__:
        if cls.__module__.startswith("term_image.image"):
            return globals()[f"{cls.__name__}Error"]

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


class StyleError(TermImageError):
    """Baseclass of style-specific exceptions.

    Never raised for errors pertaining to image classes defined in this package.
    Instead, the exception subclass specific to each image class is raised.

    Only raised for subclasses of :py:class:`BaseImage <term_image.image.BaseImage>`
    defined outside this package (which are not subclasses of any other image class
    defined in this package).

    Being the baseclass of all style-specific exceptions, it can be used be used to
    handle any style-specific error, regardless of the render style it originated from.
    """


class GraphicsImageError(StyleError):
    """Raised for errors specific to :py:class:`GraphicsImage
    <term_image.image.GraphicsImage>` and its subclasses defined outside this package.
    """


class TextImageError(StyleError):
    """Raised for errors specific to :py:class:`TextImage
    <term_image.image.TextImage>` and its subclasses defined outside this package.
    """


class BlockImageError(TextImageError):
    """Raised for errors specific to :py:class:`BlockImage
    <term_image.image.BlockImage>` and its subclasses defined outside this package.
    """


class ITerm2ImageError(GraphicsImageError):
    """Raised for errors specific to :py:class:`ITerm2Image
    <term_image.image.ITerm2Image>` and its subclasses defined outside this package.
    """


class KittyImageError(GraphicsImageError):
    """Raised for errors specific to :py:class:`KittyImage
    <term_image.image.KittyImage>` and its subclasses defined outside this package.
    """


__all__ = [
    name
    for name, obj in vars().items()
    if isinstance(obj, type) and issubclass(obj, TermImageError)
]
BaseImageError = StyleError  # Only to simplify `_style_error()`


def _style_error(cls: type):
    for cls in cls.__mro__:
        if cls.__module__.startswith("term_image.image"):
            return globals()[f"{cls.__name__}Error"]

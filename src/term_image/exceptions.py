"""
.. Custom Exceptions
"""

from __future__ import annotations


class TermImageWarning(UserWarning):
    """Package-specific warning category."""


class TermImageError(Exception):
    """Exception baseclass. Raised for generic errors."""


class URLNotFoundError(TermImageError, FileNotFoundError):
    """Raised for 404 errors."""


class InvalidSizeError(TermImageError):
    """Raised for invalid image sizes."""


class StyleError(TermImageError):
    """Baseclass of style-specific exceptions.

    Never raised for errors pertaining to image classes defined in this package.
    Instead, the exception subclass specific to each image class is raised.

    Only raised for subclasses of :py:class:`~term_image.image.BaseImage`
    defined outside this package (which are not subclasses of any other image class
    defined in this package).

    Being the baseclass of all style-specific exceptions, it can be used be used to
    handle any style-specific error, regardless of the render style it originated from.
    """


class UrwidImageError(TermImageError):
    """Raised for errors specific to :py:class:`~term_image.widget.UrwidImage`."""


__all__ = ["TermImageWarning"] + [
    name
    for name, obj in vars().items()
    if isinstance(obj, type) and issubclass(obj, TermImageError)
]

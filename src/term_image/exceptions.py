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
    """Raised for errors pertaining to the Style API."""


class UrwidImageError(TermImageError):
    """Raised for errors specific to :py:class:`~term_image.widget.UrwidImage`."""


__all__ = ["TermImageWarning"] + [
    name
    for name, obj in vars().items()
    if isinstance(obj, type) and issubclass(obj, TermImageError)
]

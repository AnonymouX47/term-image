"""
.. Custom Exceptions
"""

from __future__ import annotations


class TermImageWarning(UserWarning):
    """Package-specific warning category."""


class TermImageError(Exception):
    """Exception baseclass. Raised for generic errors."""


class InvalidSizeError(TermImageError):
    """Raised for invalid image sizes."""


class RenderError(TermImageError):
    """Raised for errors that occur **during** :term:`rendering`.

    If the direct cause of the error is an exception, it should typically be attached
    as the context of this exception i.e ``raise RenderError(...) from exc``.
    """


class StyleError(TermImageError):
    """Raised for errors pertaining to the Style API."""


class URLNotFoundError(TermImageError, FileNotFoundError):
    """Raised for 404 errors."""


class UrwidImageError(TermImageError):
    """Raised for errors specific to :py:class:`~term_image.widget.UrwidImage`."""


__all__ = ["TermImageWarning"] + [
    name
    for name, obj in vars().items()
    if isinstance(obj, type) and issubclass(obj, TermImageError)
]

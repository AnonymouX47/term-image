"""
.. Custom Exceptions
"""

from __future__ import annotations


class TermImageWarning(UserWarning):
    """Package-specific warning category."""


class TermImageError(Exception):
    """Exception baseclass. Raised for generic errors."""


class InvalidSizeError(TermImageError):
    """Raised for invalid sizes."""


class RenderError(TermImageError):
    """..."""


class StyleError(TermImageError):
    """Raised for errors pertaining to the Style API."""


class URLNotFoundError(TermImageError, FileNotFoundError):
    """Raised for 404 errors."""


class UrwidImageError(TermImageError):
    """Raised for errors specific to :py:class:`~term_image.widget.UrwidImage`."""

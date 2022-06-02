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

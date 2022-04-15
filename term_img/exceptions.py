"""
Custom Exceptions
=================
"""

from __future__ import annotations


class TermImageException(Exception):
    """Package exception baseclass"""


class URLNotFoundError(FileNotFoundError, TermImageException):
    """Raised for 404 errors"""


class InvalidSize(ValueError, TermImageException):
    """Raised when the given/set image render size is larger than the terminal size"""

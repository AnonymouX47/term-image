"""Custom Exceptions"""


class URLNotFoundError(FileNotFoundError):
    """Raised for 404 errors"""


class InvalidSize(ValueError):
    """Raised when the given/set image render size is larger than the terminal size"""

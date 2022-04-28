from __future__ import annotations

__all__ = ("TermImage",)

from .common import BaseImage


class TermImage(BaseImage):
    """Text-based image using unicode blocks and ANSI 24-bit colour escape codes.

    See :py:class:`BaseImage` for the description of the constructor.
    """

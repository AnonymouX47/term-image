from __future__ import annotations

__all__ = ("TermImage",)

from math import ceil
from operator import mul
from typing import Optional, Tuple

from .common import BaseImage


class TermImage(BaseImage):
    """Text-based image using unicode blocks and ANSI 24-bit colour escape codes.

    See :py:class:`BaseImage` for the description of the constructor.
    """

    def _get_render_size(self) -> Tuple[int, int]:
        return tuple(map(mul, self.rendered_size, (1, 2)))

    @staticmethod
    def _pixels_cols(
        *, pixels: Optional[int] = None, cols: Optional[int] = None
    ) -> int:
        return pixels if pixels is not None else cols

    @staticmethod
    def _pixels_lines(
        *, pixels: Optional[int] = None, lines: Optional[int] = None
    ) -> int:
        return ceil(pixels / 2) if pixels is not None else lines * 2

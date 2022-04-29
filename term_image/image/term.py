from __future__ import annotations

__all__ = ("TermImage",)

import io
import os
from math import ceil
from operator import mul
from typing import Optional, Tuple, Union

import PIL

from .common import _BG_FMT, _FG_FMT, _RESET, BaseImage

_LOWER_PIXEL = "\u2584"  # lower-half block element
_UPPER_PIXEL = "\u2580"  # upper-half block element


class TermImage(BaseImage):
    """Text-based image using unicode blocks and ANSI 24-bit colour escape codes.

    See :py:class:`BaseImage` for the description of the constructor.
    """

    @classmethod
    def is_supported(cls):
        if cls._supported is None:
            COLORTERM = os.environ.get("COLORTERM") or ""
            TERM = os.environ.get("TERM") or ""
            cls._supported = (
                "truecolor" in COLORTERM or "24bit" in COLORTERM or "256color" in TERM
            )

        return cls._supported

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

    def _render_image(
        self, img: PIL.Image.Image, alpha: Union[None, float, str]
    ) -> str:
        # NOTE:
        # It's more efficient to write separate strings to the buffer separately
        # than concatenate and write together.

        def update_buffer():
            if alpha:
                no_alpha = False
                if a_cluster1 == 0 == a_cluster2:
                    buf_write(_RESET)
                    buf_write(" " * n)
                elif a_cluster1 == 0:  # up is transparent
                    buf_write(_RESET)
                    buf_write(_FG_FMT % cluster2)
                    buf_write(_LOWER_PIXEL * n)
                elif a_cluster2 == 0:  # down is transparent
                    buf_write(_RESET)
                    buf_write(_FG_FMT % cluster1)
                    buf_write(_UPPER_PIXEL * n)
                else:
                    no_alpha = True

            if not alpha or no_alpha:
                buf_write(_BG_FMT % cluster2)
                if cluster1 == cluster2:
                    buf_write(" " * n)
                else:
                    buf_write(_FG_FMT % cluster1)
                    buf_write(_UPPER_PIXEL * n)

        buffer = io.StringIO()
        # Eliminate attribute resolution cost
        buf_write = buffer.write

        width, height = self._get_render_size()
        img, rgb, a = self._get_render_data(img, alpha)
        # clean up
        if img is not self._source:
            img.close()

        rgb_pairs = (
            (
                zip(rgb[x : x + width], rgb[x + width : x + width * 2]),
                (rgb[x], rgb[x + width]),
            )
            for x in range(0, len(rgb), width * 2)
        )
        a_pairs = (
            (
                zip(a[x : x + width], a[x + width : x + width * 2]),
                (a[x], a[x + width]),
            )
            for x in range(0, len(a), width * 2)
        )

        row_no = 0
        # Two rows of pixels per line
        for (rgb_pair, (cluster1, cluster2)), (a_pair, (a_cluster1, a_cluster2)) in zip(
            rgb_pairs, a_pairs
        ):
            row_no += 2
            n = 0
            for (px1, px2), (a1, a2) in zip(rgb_pair, a_pair):
                # Color-code characters and write to buffer
                # when upper and/or lower pixel color/alpha-level changes
                if not (alpha and a1 == a_cluster1 == 0 == a_cluster2 == a2) and (
                    px1 != cluster1
                    or px2 != cluster2
                    or alpha
                    and (
                        # From non-transparent to transparent
                        a_cluster1 != a1 == 0
                        or a_cluster2 != a2 == 0
                        # From transparent to non-transparent
                        or 0 == a_cluster1 != a1
                        or 0 == a_cluster2 != a2
                    )
                ):
                    update_buffer()
                    cluster1 = px1
                    cluster2 = px2
                    if alpha:
                        a_cluster1 = a1
                        a_cluster2 = a2
                    n = 0
                n += 1
            # Rest of the line
            update_buffer()
            if row_no < height:  # last line not yet rendered
                buf_write("\033[0m\n")

        buf_write(_RESET)  # Reset color after last line
        buffer.seek(0)  # Reset buffer pointer

        return buffer.getvalue()

from __future__ import annotations

__all__ = ("BlockImage", "TermImage")

import io
import os
import re
import warnings
from math import ceil
from operator import mul
from typing import Optional, Tuple, Union

import PIL

from ..utils import (
    BG_FMT,
    COLOR_RESET,
    CSI,
    FG_FMT,
    ST,
    cached,
    get_fg_bg_colors,
    query_terminal,
)
from .common import TextImage

warnings.filterwarnings("once", category=DeprecationWarning, module=__name__)

LOWER_PIXEL = "\u2584"  # lower-half block element
UPPER_PIXEL = "\u2580"  # upper-half block element


class BlockImage(TextImage):
    """A render style using unicode half blocks and ANSI 24-bit colour escape codes.

    See :py:class:`TextImage` for the description of the constructor.
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
    @cached
    def _is_on_kitty() -> bool:
        response = query_terminal(
            f"{CSI}>q".encode(), lambda s: not s.endswith(ST.encode())
        )
        match = response and re.match(
            r"\033P>\|(\w+)[( ]?([^)\033]+)\)?\033\\", response.decode(), re.ASCII
        )
        return bool(match) and match.group(1).lower() == "kitty"

    @staticmethod
    def _pixels_lines(
        *, pixels: Optional[int] = None, lines: Optional[int] = None
    ) -> int:
        return ceil(pixels / 2) if pixels is not None else lines * 2

    def _render_image(
        self,
        img: PIL.Image.Image,
        alpha: Union[None, float, str],
        *,
        frame: bool = False,
    ) -> str:
        # NOTE:
        # It's more efficient to write separate strings to the buffer separately
        # than concatenate and write together.

        def update_buffer():
            if alpha:
                no_alpha = False
                if a_cluster1 == 0 == a_cluster2:
                    buf_write(COLOR_RESET)
                    buf_write(" " * n)
                elif a_cluster1 == 0:  # up is transparent
                    buf_write(COLOR_RESET)
                    buf_write(FG_FMT % cluster2)
                    buf_write(LOWER_PIXEL * n)
                elif a_cluster2 == 0:  # down is transparent
                    buf_write(COLOR_RESET)
                    buf_write(FG_FMT % cluster1)
                    buf_write(UPPER_PIXEL * n)
                else:
                    no_alpha = True

            if not alpha or no_alpha:
                r, g, b = cluster2
                # Kitty does not render BG colors equal to the default BG color
                if self._is_on_kitty() and cluster2 == bg_color:
                    if r < 255:
                        r += 1
                    elif g < 255:
                        g += 1
                    elif b < 255:
                        b += 1
                    else:
                        r -= 1
                buf_write(BG_FMT % (r, g, b))
                if cluster1 == cluster2:
                    buf_write(" " * n)
                else:
                    buf_write(FG_FMT % cluster1)
                    buf_write(UPPER_PIXEL * n)

        buffer = io.StringIO()
        buf_write = buffer.write  # Eliminate attribute resolution cost

        bg_color = get_fg_bg_colors()[1]
        width, height = self._get_render_size()
        frame_img = img if frame else None
        img, rgb, a = self._get_render_data(img, alpha, round_alpha=True, frame=frame)
        alpha = img.mode == "RGBA"

        # clean up (ImageIterator uses one PIL image throughout)
        if frame_img is not img is not self._source:
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
                buf_write(f"{COLOR_RESET}\n")

        buf_write(COLOR_RESET)  # Reset color after last line
        buffer.seek(0)  # Reset buffer pointer

        with buffer:
            return buffer.getvalue()


class TermImage(BlockImage):
    """*Deprecated since version 0.4.0:* Replaced by :py:class:`BlockImage`."""

    def __init__(self, *args, **kwargs):
        warnings.warn(
            "`TermImage` has been deprecated and will be removed in version 1.0.0, "
            "use `BlockImage` instead.",
            DeprecationWarning,
        )
        super().__init__(*args, **kwargs)

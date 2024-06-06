from __future__ import annotations

__all__ = ("BlockImage",)

import io
import os
import re
from math import ceil
from operator import mul
from typing import Any, Optional, Tuple, Union

import PIL

from ..ctlseqs import SGR_BG_INDEXED, SGR_BG_RGB, SGR_FG_INDEXED, SGR_FG_RGB, SGR_NORMAL
from ..utils import get_fg_bg_colors
from .common import TextImage

LOWER_PIXEL = "\u2584"  # lower-half block element
UPPER_PIXEL = "\u2580"  # upper-half block element

# Constants for render methods
DIRECT = "direct"
INDEXED = "indexed"


class BlockImage(TextImage):
    """A render style using Unicode half blocks with direct-color or indexed-color
    control sequences.

    See :py:class:`TextImage` for the description of the constructor.

    |

    **Render Methods**

    :py:class:`BlockImage` provides two methods of :term:`rendering` images, namely:

    DIRECT (default)
       Renders an image using direct-color (truecolor) control sequences.

       Pros:

       * Better color reproduction.

       Cons:

       * Lesser terminal emulator support (though any terminal emulator worthy of use
         today actually does provide support).

    INDEXED
       Renders an image using indexed-color control sequences but with only the upper
       **240 colors** of the terminal's 256-color palette.

       Pros:

       * Wider terminal emulator support.

       Cons:

       * Worse color reproduction.

    The render method can be set with
    :py:meth:`set_render_method() <BaseImage.set_render_method>` using the names
    specified above.

    |

    **Style-Specific Render Parameters**

    See :py:meth:`BaseImage.draw` (particularly the *style* parameter).

    * **method** (*None | str*) → Render method override.

      * ``None`` → the current effective render method of the instance is used
      * A valid render method name (as specified in the **Render Methods** section
        above) → used instead of the current effective render method of the instance
      * *default* → ``None``

    |

    **Format Specification**

    See :ref:`format-spec`.

    ::

        [ <method> ]

    * ``method`` → render method override

      * ``D`` → **DIRECT** render method (current frame only, for animated images)
      * ``I`` → **INDEXED** render method (current frame only, for animated images)
      * *default* → Current effective render method of the image
    """

    _FORMAT_SPEC: tuple[re.Pattern] = (re.compile("[DI]"),)
    _render_methods: set[str] = {DIRECT, INDEXED}
    _default_render_method: str = DIRECT
    _render_method: str = DIRECT
    _style_args = {
        "method": (
            None,
            (
                lambda x: isinstance(x, str),
                "Render method must be a string",
            ),
            (
                lambda x: x.lower() in __class__._render_methods,
                "Unknown render method for 'block' render style",
            ),
        ),
    }

    @classmethod
    def is_supported(cls):
        if cls._supported is None:
            COLORTERM = os.environ.get("COLORTERM") or ""
            TERM = os.environ.get("TERM") or ""
            cls._supported = (
                "truecolor" in COLORTERM or "24bit" in COLORTERM or "256color" in TERM
            )

        return cls._supported

    @classmethod
    def _check_style_format_spec(cls, spec: str, original: str) -> dict[str, Any]:
        parent, (method,) = cls._get_style_format_spec(spec, original)
        args = {}
        if parent:
            args.update(super()._check_style_format_spec(parent, original))
        if method:
            args["method"] = DIRECT if method == "D" else INDEXED

        return cls._check_style_args(args)

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
        self,
        img: PIL.Image.Image,
        alpha: Union[None, float, str],
        *,
        frame: bool = False,
        method: str | None = None,
        split_cells: bool = False,
    ) -> str:
        # NOTE:
        # It's more efficient to write separate strings to the buffer separately
        # than concatenate and write together.

        def update_buffer():
            if alpha:
                no_alpha = False
                if a_cluster1 == 0 == a_cluster2:
                    buf_write(SGR_NORMAL)
                    buf_write(blank * n)
                elif a_cluster1 == 0:  # up is transparent
                    buf_write(SGR_NORMAL)
                    buf_write(sgr_fg % cluster2)
                    buf_write(lower_pixel * n)
                elif a_cluster2 == 0:  # down is transparent
                    buf_write(SGR_NORMAL)
                    buf_write(sgr_fg % cluster1)
                    buf_write(upper_pixel * n)
                else:
                    no_alpha = True

            if not alpha or no_alpha:
                if method_is_direct:
                    r, g, b = cluster2
                    # Kitty does not render BG colors equal to the default BG color
                    if is_on_kitty and cluster2 == bg_color:
                        r += r < 255 or -1
                    buf_write(sgr_bg % (r, g, b))
                else:
                    buf_write(sgr_bg % cluster2)

                if cluster1 == cluster2:
                    buf_write(blank * n)
                else:
                    buf_write(sgr_fg % cluster1)
                    buf_write(upper_pixel * n)

        buffer = io.StringIO()
        buf_write = buffer.write  # Eliminate attribute resolution cost

        render_method = (method or self._render_method).lower()
        method_is_direct = render_method == DIRECT
        if method_is_direct:
            bg_color = get_fg_bg_colors()[1]
            is_on_kitty = self._is_on_kitty()
        if split_cells:
            blank = " \0"
            lower_pixel = LOWER_PIXEL + "\0"
            upper_pixel = UPPER_PIXEL + "\0"
        else:
            blank = " "
            lower_pixel = LOWER_PIXEL
            upper_pixel = UPPER_PIXEL
        end_of_line = SGR_NORMAL + "\n"
        sgr_fg = SGR_FG_RGB if method_is_direct else SGR_FG_INDEXED
        sgr_bg = SGR_BG_RGB if method_is_direct else SGR_BG_INDEXED

        width, height = self._get_render_size()
        frame_img = img if frame else None
        img, rgb, a = self._get_render_data(
            img,
            alpha,
            round_alpha=True,
            frame=frame,
            indexed_color=not method_is_direct,
        )
        alpha = img.mode == ("RGBA" if method_is_direct else "PA")

        # clean up (ImageIterator uses one PIL image throughout)
        if frame_img is not img:
            self._close_image(img)

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

            update_buffer()  # Rest of the line
            if split_cells:
                # Set the last "\0" to be overwritten by the next byte
                buffer.seek(buffer.tell() - 1)
            if row_no < height:  # last line not yet rendered
                buf_write(end_of_line)

        buf_write(SGR_NORMAL)  # Reset color after last line

        with buffer:
            return buffer.getvalue()

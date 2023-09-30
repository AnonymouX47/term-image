""".. Widgets for urwid"""

from __future__ import annotations

__all__ = ("UrwidImage", "UrwidImageCanvas", "UrwidImageScreen")

from typing import Optional, Tuple

import urwid

from .. import ctlseqs

# These sequences are used during performance-critical operations that occur often
from ..ctlseqs import BEGIN_SYNCED_UPDATE, END_SYNCED_UPDATE, ESC_b, SGR_NORMAL_b
from ..exceptions import UrwidImageError
from ..image import BaseImage, ITerm2Image, KittyImage, Size, TextImage
from ..utils import arg_type_error, get_terminal_name_version, lock_tty, write_tty

# NOTE: Any new "private" attribute of any subclass of an urwid class should be
# prepended with "_ti" to prevent clashes with names used by urwid itself.


class UrwidImage(urwid.Widget):
    """Image widget (box/flow) for the urwid TUI framework.

    Args:
        image: The image to be rendered by the widget.
        format_spec: :ref:`Render format specifier <format-spec>`. Padding width and
          height are ignored.
        upscale: If ``True``, the image will be upscaled to fit maximally within the
          available size, if necessary, while still preserving the aspect ratio.
          Otherwise, the image is never upscaled.

    Raises:
        TypeError: An argument is of an inappropriate type.
        ValueError: An argument is of an appropriate type but has an
          unexpected/invalid value.
        term_image.exceptions.StyleError: Invalid style-specific format specifier.
        term_image.exceptions.UrwidImageError: Too many image widgets rendering images
          with the *kitty* render style.

    | Any ample space in the widget's render size is filled with spaces.
    | For animated images, the current frame (at render-time) is rendered.

    TIP:
        If *image* is of a :ref:`graphics-based <graphics-based>` render style and the
        widget is being used as or within a **flow** widget, with overlays or in any
        other case where the canvas will require vertical trimming, make sure to use a
        render method that splits images across lines such as the **LINES** render
        method for *kitty* and *iterm2* render styles.

    NOTE:
        * The `z-index` style-specific format spec field for
          :py:class:`~term_image.image.KittyImage` is ignored as this is used
          internally.
        * A **maximum** of ``2**32 - 2`` instances initialized with
          :py:class:`~term_image.image.KittyImage` instances may exist at the same time.

    IMPORTANT:
        This is defined if and only if the ``urwid`` package is available.
    """

    _sizing = frozenset((urwid.BOX, urwid.FLOW))
    ignore_focus = True

    _ti_error_placeholder = None

    # For kitty images
    _ti_disguise_state = 0
    _ti_free_z_indexes = set()

    # Progresses thus: 1, -1, 2, -2, 3, ..., 2**31 - 1, -(2**31 - 1)
    # This sequence results in shorter image escape sequences compared to starting
    # from -(2**31)
    _ti_next_z_index = 1

    def __init__(
        self, image: BaseImage, format_spec: str = "", *, upscale: bool = False
    ) -> None:
        if not isinstance(image, BaseImage):
            raise arg_type_error("image", image)

        if not isinstance(format_spec, str):
            raise arg_type_error("format_spec", format_spec)
        *fmt, alpha, style_args = image._check_format_spec(format_spec)

        if not isinstance(upscale, bool):
            raise arg_type_error("upscale", upscale)

        super().__init__()
        self._ti_image = image
        self._ti_h_align, _, self._ti_v_align, _ = fmt
        self._ti_alpha = alpha
        self._ti_style_args = style_args
        self._ti_sizing = Size.FIT if upscale else Size.AUTO

        if isinstance(image, TextImage):
            style_args["split_cells"] = True
        elif isinstance(image, KittyImage):
            style_args["z_index"] = self._ti_z_index = self._ti_get_z_index()

            # Since Konsole doesn't blend images placed at the same location and
            # z-index, unlike Kitty (and potentially others), `blend=True` is
            # better on Konsole as it reduces/eliminates flicker.
            if get_terminal_name_version()[0] != "konsole":
                # To clear directly overlapped images when urwid redraws a line without
                # a change in image position
                style_args["blend"] = False

    def __del__(self) -> None:
        if hasattr(self, "_ti_z_index"):
            __class__._ti_free_z_indexes.add(self._ti_z_index)

    image = property(
        lambda self: self._ti_image,
        doc="""
        The image rendered by the widget

        :type: BaseImage

        GET:
            Returns the image instance rendered by the widget.
        """,
    )

    def render(self, size: Tuple[int, int], focus: bool = False) -> urwid.Canvas:
        image = self._ti_image

        if len(size) == 2:  # box
            image.set_size(self._ti_sizing, frame_size=size)
        elif len(size) == 1:  # flow
            if self._ti_sizing is Size.FIT:
                image.set_size(size[0])
            else:
                fit_size = self._ti_image._valid_size(size[0])
                ori_size = self._ti_image._valid_size(Size.ORIGINAL)
                image._size = (
                    ori_size
                    if ori_size[0] <= fit_size[0] and ori_size[1] <= fit_size[1]
                    else fit_size
                )
            size = (size[0], image._size[1])
        else:  # fixed
            raise UrwidImageError("Not a fixed widget")

        try:
            render = image._format_render(
                image._renderer(
                    image._render_image, self._ti_alpha, **self._ti_style_args
                ),
                self._ti_h_align,
                size[0],
                self._ti_v_align,
                size[1],
            )
        except Exception:
            if type(self)._ti_error_placeholder is None:
                raise
            canv = type(self)._ti_error_placeholder.render(size, focus)
        else:
            canv = UrwidImageCanvas(render, size, image._size)

        return canv

    def rows(self, size: Tuple[int], focus: bool = False) -> int:
        fit_size = self._ti_image._valid_size(size[0])
        if self._ti_sizing is Size.FIT:
            n_rows = fit_size[1]
        else:
            ori_size = self._ti_image._valid_size(Size.ORIGINAL)
            n_rows = (
                ori_size[1]
                if ori_size[0] <= fit_size[0] and ori_size[1] <= fit_size[1]
                else fit_size[1]
            )

        return n_rows

    @classmethod
    def set_error_placeholder(cls, widget: Optional[urwid.Widget]) -> None:
        """Sets the widget to be rendered in place of an image when rendering fails.

        Args:
            widget: The placeholder widget or ``None`` to remove the placeholder.

        Raises:
            TypeError: *widget* is not an urwid widget.

        If set, any exception raised during rendering is **suppressed** and the
        placeholder is rendered in place of the image.
        """
        if not isinstance(widget, urwid.Widget):
            raise arg_type_error("widget", widget)

        cls._ti_error_placeholder = widget

    @staticmethod
    def _ti_get_z_index() -> int:
        if __class__._ti_free_z_indexes:
            return __class__._ti_free_z_indexes.pop()

        z_index = __class__._ti_next_z_index
        if z_index == 2**31:
            raise UrwidImageError("Too many image widgets with the kitty render style")
        __class__._ti_next_z_index = -z_index if z_index > 0 else -z_index + 1

        return z_index

    def _ti_change_disguise(self) -> None:
        """See :py:meth`UrwidImageCanvas._ti_change_disguise`."""
        self._ti_disguise_state = (self._ti_disguise_state + 1) % 3


class UrwidImageCanvas(urwid.Canvas):
    """Image canvas for the urwid TUI framework.

    Args:
        render: The rendered image.
        size: The canvas size. Also, the size of the rendered (and formatted) image.
        image_size: The size with which the image was rendered (excluding padding).

    NOTE:
        The canvas outputs blanks (spaces) for :ref:`graphics-based <graphics-based>`
        images when horizontal trimming is required (e.g when a widget is laid over
        an image). This is temporary as horizontal trimming will be implemented in the
        future.

        This canvas is intended to be rendered by :py:class:`UrwidImage` (or a subclass
        of it) only. Otherwise, the output isn't guaranteed to be as expected.

    WARNING:
        The constructor of this class performs NO argument validation at all for the
        sake of performance. If instantiating this class directly, make sure to pass
        appropriate arguments or create subclass, override the constructor and perform
        the validation.

    IMPORTANT:
        This is defined if and only if the ``urwid`` package is available.
    """

    _ti_disguise_state = 0

    def __init__(
        self, render: str, size: Tuple[int, int], image_size: Tuple[int, int]
    ) -> None:
        super().__init__()
        self.size = size
        self._ti_image_size = image_size

        # On the last row of the screen, urwid inserts the second to the last
        # character after writing the last (though placed before it i.e inserted),
        # thereby messing up an escape sequence occurring at the end.
        # See `urwid.raw_display.Screen._last_row()`.
        # Any line of the image could potentially be the last on the screen as a result
        # of trimming.
        self._ti_lines = [line + b"\0\0" for line in render.encode().split(b"\n")]

    def cols(self) -> int:
        return self.size[0]

    def content(self, trim_left=0, trim_top=0, cols=None, rows=None, attr_map=None):
        size = self.size
        image_size = self._ti_image_size
        visible_rows = rows or size[1]
        trim_bottom = size[1] - trim_top - visible_rows
        visible_cols = cols or size[0]
        trim_right = size[0] - trim_left - visible_cols

        widget = self.widget_info[0]
        try:
            image = widget._ti_image
            h_align = widget._ti_h_align
            v_align = widget._ti_v_align
        except AttributeError:  # the canvas wasn't rendered by `UrwidImage`
            for line in self._ti_lines[trim_top : -trim_bottom or None]:
                yield [(None, "U", line)]
            return

        if isinstance(image, TextImage):
            if trim_left == 0 == trim_right:
                for line in self._ti_lines[trim_top : -trim_bottom or None]:
                    yield [(None, "U", line.replace(b"\0", b"")), (None, "U", b"\0\0")]
                return

            pad = size[1] - image_size[1]
            if v_align == "^":
                pad_top = 0
                pad_bottom = pad
            elif v_align == "_":
                pad_top = pad
                pad_bottom = 0
            else:
                pad_top = pad // 2
                pad_bottom = pad - pad_top

            (
                new_pad_top,
                trim_image_top,
                trim_image_bottom,
                new_pad_bottom,
            ) = self._ti_calc_trim(
                size[1], image_size[1], trim_top, pad_top, trim_bottom, pad_bottom
            )
            image_is_empty = image_size[1] in (trim_image_top, trim_image_bottom)
            image_is_partial = trim_image_top != image_size[1] != trim_image_bottom

            # Adding "\0\0" for consistency with output without horizontal trim
            padding_line = b" " * visible_cols + b"\0\0"

            if not image_is_empty:
                pad = size[0] - image_size[0]
                if h_align == "<":
                    pad_left = 0
                    pad_right = pad
                elif h_align == ">":
                    pad_left = pad
                    pad_right = 0
                else:
                    pad_left = pad // 2
                    pad_right = pad - pad_left

                (
                    new_pad_left,
                    trim_image_left,
                    trim_image_right,
                    new_pad_right,
                ) = self._ti_calc_trim(
                    size[0], image_size[0], trim_left, pad_left, trim_right, pad_right
                )
                image_line_is_full = trim_image_left == 0 == trim_image_right
                image_line_is_partial = (
                    trim_image_left != image_size[0] != trim_image_right
                )
                pad_right += 2  # For "\0\0"

                left_padding = (
                    ((None, "U", b" " * new_pad_left),) if new_pad_left else ()
                )
                right_padding = (
                    ((None, "U", b" " * new_pad_right),) if new_pad_right else ()
                )
                color_reset = (
                    ((None, "U", SGR_NORMAL_b),)
                    if image_size[0] > trim_image_right > 0
                    else ()
                )
                last_row_workaround = ((None, "U", b"\0\0"),)

            if image_is_empty:
                image_lines = []
            else:
                image_lines = self._ti_lines[pad_top : -pad_bottom or None]
                if image_is_partial:
                    image_lines = image_lines[
                        trim_image_top : -trim_image_bottom or None
                    ]

            # top padding
            for _ in range(new_pad_top):
                yield [(None, "U", padding_line)]

            # image
            for line in image_lines:
                first_color = ()
                if image_line_is_full:
                    image_line = line[pad_left:-pad_right].replace(b"\0", b"")
                elif image_line_is_partial:
                    line = line[pad_left:-pad_right].split(b"\0")
                    image_line = b"".join(
                        line[trim_image_left : -trim_image_right or None]
                    )
                    # Exclude non-colored images when the time comes
                    if not line[trim_image_left].startswith(ESC_b):
                        for cell in line[trim_image_left - 1 :: -1]:
                            if cell.startswith(ESC_b):
                                first_color = (
                                    (None, "U", cell[: cell.rindex(b"m") + 1]),
                                )
                                break
                image_line = (
                    (*first_color, (None, "U", image_line))
                    if image_line_is_full or image_line_is_partial
                    else ()
                )

                yield [
                    *left_padding,
                    *image_line,
                    *color_reset,
                    *right_padding,
                    *last_row_workaround,
                ]

            # bottom padding
            for _ in range(new_pad_bottom):
                yield [(None, "U", padding_line)]
        elif trim_left or trim_right:
            line = b" " * visible_cols
            for _ in range(visible_rows):
                yield [(None, "U", line)]
        else:
            disguise = (
                b"\b "
                * (self._ti_disguise_state + widget._ti_disguise_state)
                * (
                    isinstance(image, KittyImage)
                    or isinstance(image, ITerm2Image)
                    and get_terminal_name_version()[0] == "konsole"
                )
            )
            for line in self._ti_lines[trim_top : -trim_bottom or None]:
                yield [(None, "U", line + disguise)]

    def rows(self) -> int:
        return self.size[1]

    @classmethod
    def _ti_change_disguise(cls) -> None:
        """Changes the hidden text embedded on every line, such that every line of the
        canvas is different in every state.

        The reason for this is, ``urwid`` will not redraw lines that have not changed
        since the last screen update. So this is to trick ``urwid`` into taking every
        line containing a part of an image as different in each state.

        This is used to force redraws of all images on screen, particularly when
        graphics-based images are cleared and their positions have not change so
        much.
        """
        cls._ti_disguise_state = (cls._ti_disguise_state + 1) % 3

    @staticmethod
    def _ti_calc_trim(
        size: int,
        image_size: int,
        trim_side1: int,
        pad_side1: int,
        trim_side2: int,
        pad_side2: int,
    ) -> Tuple[int, int, int, int]:
        """Calculates the new padding size on both sides after trimming and size to be
        trimmed off the rendered image from both ends, all **along the same axis**.

        Args:
            size: Canvas size.
            image_size: Size with which the image was rendered (excluding padding).
            trim_side1: Size to trim off the canvas (image with padding) from one size.
            pad_side1: Padding size on one side of the image.
            trim_side2: Size to trim off the canvas (image with padding) from the
              opposite size.
            pad_side2: Padding size on the opposite side of the image.

        Returns:
            A 4-tuple containing the following dimensions, in the given order:

            - new_pad_side1: The trimmed padding size on one side.
            - trim_image_side1: The size to be trimmed off the image on one side.
            - trim_image_side2: The size to be trimmed off the image on the opposite
              side.
            - new_pad_side2: The trimmed padding size on the opposite side.

        The dimensions given as arguments must be along the **same axis** (vertical or
        horizontal).
        """
        image_end = size - pad_side2
        if trim_side1 >= image_end:  # within side2 padding
            new_pad_side1 = 0
            trim_image_side1 = image_size
            new_pad_side2 = size - trim_side1
        elif trim_side1 >= pad_side1:  # within the image
            new_pad_side1 = 0
            trim_image_side1 = trim_side1 - pad_side1
            new_pad_side2 = pad_side2
        else:  # within side1 padding
            new_pad_side1 = pad_side1 - trim_side1
            trim_image_side1 = 0
            new_pad_side2 = pad_side2

        image_end = size - pad_side1
        if trim_side2 >= image_end:  # within side1 padding
            new_pad_side2 = 0
            trim_image_side2 = image_size
            new_pad_side1 -= trim_side2 - image_end
        elif trim_side2 >= pad_side2:  # within the image
            new_pad_side2 = 0
            trim_image_side2 = trim_side2 - pad_side2
        else:  # within side2 padding
            new_pad_side2 -= trim_side2
            trim_image_side2 = 0

        return new_pad_side1, trim_image_side1, trim_image_side2, new_pad_side2


class UrwidImageScreen(urwid.raw_display.Screen):
    """A screen that supports drawing images.

    It monitors images of some :ref:`graphics-based <graphics-based>` render styles
    and clears them off the screen when necessary (e.g at startup, when scrolling,
    upon terminal resize and at exit).

    See the baseclass for further description.

    IMPORTANT:
        This is defined if and only if the ``urwid`` package is available.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ti_screen_canv = None
        self._ti_image_cviews = frozenset()

    def clear(self):
        self.clear_images()
        return super().clear()

    def clear_images(self, *widgets: UrwidImage, now: bool = False) -> None:
        """Clears on-screen images of :ref:`graphics-based <graphics-based>`
        styles **that support/require such an operation**.

        Args:
            widgets: Image widgets to clear.

              All on-screen images rendered by each of the widgets are cleared,
              provided the widget was initialized with a
              :py:class:`term_image.image.KittyImage` instance.

              If none is given, all images (of styles **that support/require such an
              operation**) on-screen are cleared.

            now: If ``True`` the images are cleared immediately.
              Otherwise, they're cleared when next the output buffer is flushed,
              such as at the next screen redraw.
        """
        # Also takes care of iterm2 images on Konsole
        if not (KittyImage.forced_support or KittyImage.is_supported()):
            return

        if widgets:
            # Better to send the delete commands in a batch than individually
            kitty_widgets = []
            for index, widget in enumerate(widgets):
                if not isinstance(widget, UrwidImage):
                    raise arg_type_error(f"widgets[{index}]", widget)

                if isinstance(widget._ti_image, KittyImage):
                    kitty_widgets.append(widget)
                    widget._ti_change_disguise()

            if kitty_widgets:
                if now:
                    write_tty(
                        b"".join(
                            ctlseqs.KITTY_DELETE_Z_INDEX_b % widget._ti_z_index
                            for widget in kitty_widgets
                        )
                    )
                else:
                    self.write(
                        "".join(
                            ctlseqs.KITTY_DELETE_Z_INDEX % widget._ti_z_index
                            for widget in kitty_widgets
                        )
                    )
        else:
            if now:
                write_tty(ctlseqs.KITTY_DELETE_ALL_b)
            else:
                self.write(ctlseqs.KITTY_DELETE_ALL)
            UrwidImageCanvas._ti_change_disguise()

    # `@lock_tty` prevents queries during a synced update.
    # Otherwise, responses would be delayed until the synced update ends and that might
    # be after the query has timed out.
    @lock_tty
    def draw_screen(self, maxres, canvas):
        """See the description of the baseclass' method.

        Synchronizes output on terminal emulators that support the feature to
        reduce/eliminate image flickering and screen tearing.
        """
        self.write(BEGIN_SYNCED_UPDATE)
        try:
            if canvas is not self._ti_screen_canv:
                self._ti_screen_canv = canvas
                self._ti_clear_images()
            return super().draw_screen(maxres, canvas)
        finally:
            self.write(END_SYNCED_UPDATE)
            self.flush()

    @lock_tty
    def flush(self):
        """See the baseclass' method for the description."""
        return super().flush()

    @lock_tty
    def get_available_raw_input(self):
        """See the baseclass' method for the description."""
        return super().get_available_raw_input()

    @lock_tty
    def write(self, data):
        """See the baseclass' method for the description."""
        return super().write(data)

    def _start(self, *args, **kwargs):
        ret = super()._start(*args, **kwargs)
        self.clear_images()
        return ret

    def _stop(self):
        self.clear_images()
        return super()._stop()

    def _ti_clear_images(self):
        if not (
            KittyImage.forced_support
            or KittyImage.is_supported()
            or ITerm2Image.is_supported()
            and get_terminal_name_version()[0] == "konsole"
        ):
            return

        screen_canv = self._ti_screen_canv

        if not isinstance(screen_canv, urwid.CompositeCanvas):
            if self._ti_image_cviews:
                self.clear_images()
                self._ti_image_cviews.clear()
            return

        def process_shard_tails():
            nonlocal col

            while col in shard_tails:
                *trim, cols, rows, canv = shard_tails[col]
                if rows > n_rows:
                    shard_tails[col] = (*trim, cols, rows - n_rows, canv)
                else:
                    del shard_tails[col]
                col += cols

        image_cviews = set()
        shard_tails = {}
        row = 1

        for n_rows, cviews in screen_canv.shards:
            col = 1
            for cview in cviews:
                process_shard_tails()
                *trim, cols, rows, _, canv = cview

                if isinstance(canv, UrwidImageCanvas):
                    try:
                        widget = canv.widget_info[0]
                    except TypeError:
                        pass
                    else:
                        if (
                            isinstance(widget._ti_image, KittyImage)
                            or isinstance(widget._ti_image, ITerm2Image)
                            and get_terminal_name_version()[0] == "konsole"
                        ):
                            image_cviews.add((canv, row, col, *trim, cols, rows))

                if rows > n_rows:
                    shard_tails[col] = (*trim, cols, rows - n_rows, canv)
                col += cols
            process_shard_tails()
            row += n_rows

        kitty_widgets = []
        for canv, *_ in self._ti_image_cviews - image_cviews:
            widget = canv.widget_info[0]
            if isinstance(widget._ti_image, KittyImage):
                kitty_widgets.append(widget)
            else:
                self.clear_images()
                # Multiple `clear_images()`s messes up the canvas disguise
                # A single `clear_images()` takes care of all images anyways
                break
        else:
            if kitty_widgets:
                self.clear_images(*kitty_widgets)

        self._ti_image_cviews = frozenset(image_cviews)

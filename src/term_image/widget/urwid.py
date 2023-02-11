""".. Widgets for urwid"""

from __future__ import annotations

__all__ = ("UrwidImage", "UrwidImageCanvas")

from typing import List, Optional, Tuple

import urwid

from ..image import BaseImage, ITerm2Image, KittyImage, Size

# NOTE: Any new "private" attribute of any subclass of an urwid class should be
# prepended with "_ti" to prevent clashes with names used by urwid itself.


class UrwidImage(urwid.Widget):
    """Image widget (box/flow) for the urwid TUI framework.

    Args:
        image: The image to be rendered by the widget.
        format: Image :ref:`format specifier <format-spec>`. Padding width and height
          are ignored.
        upscale: If ``True``, the image will be upscaled to fit the available size, if
          neccessary. Otherwise, the image is never upscaled and any ample space is
          padded up.

    For animated images, the current frame (at render-time) is rendered.

    NOTE:
        If using an image widget with a :ref:`graphics-based <graphics-based>`
        render style as or within a **flow** widget, make sure to use a render method
        that splits images across lines such as the **LINES** render method for *kitty*
        and *iterm2* styles.

        If *image* is of *iterm2* render style, prevent the widget from reaching the
        **last line** of the screen as **Wezterm** doesn't work properly in this case
        (it scrolls the screen).

    IMPORTANT:
        This is defined if and only if the ``urwid`` package is available.
    """

    _sizing = frozenset((urwid.BOX, urwid.FLOW))
    _selectable = True
    ignore_focus = True

    _ti_error_placeholder = None

    def __init__(
        self, image: BaseImage, format: str = "", *, upscale: bool = False
    ) -> None:
        if not isinstance(image, BaseImage):
            raise TypeError(f"Invalid type for 'image' (got: {type(image).__name__})")

        if not isinstance(format, str):
            raise TypeError(f"Invalid type for 'format' (got: {type(format).__name__})")
        *fmt, alpha, style_args = image._check_format_spec(format)

        if not isinstance(upscale, bool):
            raise TypeError(
                f"Invalid type for 'upscale' (got: {type(upscale).__name__})"
            )

        super().__init__()
        self._ti_image = image
        self._ti_h_align, _, self._ti_v_align, _ = fmt
        self._ti_alpha = alpha
        self._ti_style_args = style_args
        self._ti_sizing = Size.FIT if upscale else Size.AUTO

    image = property(
        lambda self: self._ti_image,
        doc="""
        The image rendered by the widget.

        :rtype: BaseImage
        """,
    )

    @staticmethod
    def clear():
        """Clears all on-screen images of :ref:`graphics-based <graphics-based>` styles
        that support such operation.
        """
        for cls in (KittyImage, ITerm2Image):
            cls.clear()
        UrwidImageCanvas._ti_change_disguise()

    def keypress(self, size: Tuple[int, int], key: str) -> str:
        return key

    def render(self, size: Tuple[int, int], focus: bool = False) -> UrwidImageCanvas:
        image = self._ti_image

        if len(size) == 2:
            image.set_size(self._ti_sizing, maxsize=size)
        elif len(size) == 1:
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
        else:
            raise ValueError("Not a packed widget")

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
            lines = render.encode().split(b"\n")

            # On the last row of the screen, urwid inserts the second to the last
            # character after writing the last (though placed before it i.e inserted),
            # thereby messing up an escape sequence occurring at the end.
            # See `urwid.raw_display.Screen._last_row()`
            lines = [line + b"\0\0" for line in lines]

            canv = UrwidImageCanvas(lines, size)

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
            widget: The placholder widget or ``None`` to remove the placeholder.

        If set, any exception raised during rendering is **suppressed** and the
        placeholder is rendered in place of the image.
        """
        if not isinstance(widget, urwid.Widget):
            raise TypeError("Invalid type for 'widget' (got: {type(widget).__name__})")

        cls._ti_error_placeholder = widget


class UrwidImageCanvas(urwid.Canvas):
    """Image canvas for the urwid TUI framework.

    Args:
        lines: Lines of a rendered image.
        size: The canvas size. Also, the size of the rendered image.

    WARNING:
        The constructor of this class performs NO argument validation at all for the
        sake of performance. If instantiating this class directly, make sure to pass
        appropriate arguments or create subclass, override the constructor and perform
        the validation.

    IMPORTANT:
        This is defined if and only if the ``urwid`` package is available.
    """

    _ti_disguise_state = 0

    def __init__(self, lines: List[bytes], size: Tuple[int, int]) -> None:
        super().__init__()
        self.size = size
        self._ti_lines = lines

    def cols(self) -> int:
        return self.size[0]

    def content(self, trim_left=0, trim_top=0, cols=None, rows=None, attr_map=None):
        visible_rows = rows or self.size[1]
        trim_bottom = self.size[1] - trim_top - visible_rows

        try:
            image = self.widget_info[0]._ti_image
        except AttributeError:  # the canvas wasn't rendered by `UrwidImage`
            disguise = False
        else:
            disguise = (
                isinstance(image, KittyImage)
                or isinstance(image, ITerm2Image)
                and ITerm2Image._TERM == "konsole"
            )

        for line in self._ti_lines[trim_top : -trim_bottom or None]:
            yield [(None, "U", line + b"\b " * disguise * self._ti_disguise_state)]

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

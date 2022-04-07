"""Custom widget definitions and UI components assembly"""

import logging as _logging
from math import ceil
from operator import floordiv, mul, sub
from os.path import basename
from shutil import get_terminal_size
from typing import List, Optional, Tuple

import urwid

from .. import logging
from ..config import _nav, cell_width, expand_key, nav
from ..image import _ALPHA_THRESHOLD, TermImage
from . import keys, main as tui_main
from .render import grid_render_queue, image_render_queue

command = urwid.Widget._command_map._command_defaults.copy()
for action, (key, _) in _nav.items():
    val = command.pop(key)
    command[nav[action][0]] = val
urwid.Widget._command_map._command = command
del command


class GridListBox(urwid.ListBox):
    def __init__(self, grid: urwid.GridFlow):
        self._grid = grid
        self._prev_ncell = 1
        self._prev_cell_width = grid.cell_width
        self._grid_path = None
        self._ncontent = 0

        return super().__init__(self._grid_contents((grid.cell_width,)))

    def rows(self, size: Tuple[int, int], focus: bool = False) -> int:
        return self._grid.rows(size[:1], focus)

    def render(self, size: Tuple[int, int], focus: bool = False) -> urwid.Canvas:
        # 0, if maxcol < cell_width (maxcol = size[0]).
        # Otherwise, number of cells per row.
        ncell = sum(
            map(
                floordiv,
                # No of whole (cell_width + h_sep), columns left after last h_sep
                divmod(size[0], self._grid.cell_width + self._grid.h_sep),
                # if one cell_width can fit into the remaining space
                (1, self._grid.cell_width),
            )
        )

        # The path takes care of "same directory"
        # The number of cells takes care of deletions in that directory.
        grid_path = tui_main.grid_path
        ncontent = len(self._grid.contents)

        if (
            self._grid_path != grid_path  # Different grids
            or self._ncontent != ncontent  # Different no of cells
            or not (ncell or self._prev_ncell)  # maxcol is and was < cell_width
            or ncell != self._prev_ncell  # Number of cells per row changed
            or self._prev_cell_width != self._grid.cell_width  # cell_width changed
        ):
            # When maxcol < cell_width, the grid contents are not `Columns` widgets.
            # Instead, they're what would normally be the contents of the `Columns`.
            # If the grid is empty, then the `GridListBox` only contains a `Divider`

            # Old and new grids are both non-empty
            both_non_empty = len(self._grid.contents) and (
                len(self.body) > 1 or isinstance(self.body[0], urwid.Columns)
            )
            # Conditions for transferring row focus position
            transfer_row_focus = (
                self._grid_path == grid_path
                and both_non_empty
                and ncell
                and self._prev_ncell
            )

            if transfer_row_focus:
                col_focus_position = self.focus.focus_position

            self.body[:] = self._grid_contents(size[:1])
            if self._grid_path == grid_path:
                # Ensure focus-position is not out-of-bounds
                self.focus_position = min(len(self.body) - 1, self.focus_position)
            else:
                self.focus_position = 0

            if transfer_row_focus:
                self.focus.focus_position = min(
                    len(self.focus.contents) - 1, col_focus_position
                )
            elif isinstance(self.focus, urwid.Columns):
                self.focus.focus_position = 0

            self._grid_path = grid_path
            self._ncontent = ncontent
            self._prev_ncell = ncell
            self._prev_cell_width = self._grid.cell_width

        return super().render(size, focus)

    def _grid_contents(self, size: Tuple[int, int]) -> List[urwid.Widget]:
        # The display widget is a `Divider` when the grid is empty
        if not self._grid.contents:
            return [self._grid.generate_display_widget(size)]

        contents = [
            content[0] if isinstance(content[0], urwid.Divider)
            # `.original_widget` gets rid of an unnecessary padding
            else content[0].original_widget
            for content in self._grid.generate_display_widget(size).contents
        ]

        for content in contents:
            if not isinstance(content, urwid.Divider):
                content._selectable = True

        return contents


class Image(urwid.Widget):
    _sizing = frozenset(["box"])
    _selectable = True
    no_cache = ["render", "rows"]

    _faulty_image = urwid.SolidFill("?")
    _large_image = urwid.SolidFill("!")
    _placeholder = urwid.SolidFill(".")

    _force_render = False
    _force_render_contexts = {"image", "full-image", "full-grid-image"}
    _forced_anim_size_hash = None

    _frame = _frame_changed = _frame_size_hash = None

    _faulty = False
    _canv = None
    _rendering_image_info = (None,) * 3

    _grid_cache = {}

    _alpha = f"{_ALPHA_THRESHOLD}"[1:]  # Updated from `.tui.init()`

    def __init__(self, image: TermImage):
        self._image = image

    def keypress(self, size: Tuple[int, int], key: str) -> str:
        return key

    def rows(self, size: Tuple[int, int], focus: bool = False) -> int:
        # Incompetent implementation due to the lack of *maxrows*
        size = self._image._valid_size(
            size[0],
            None,
            maxsize=get_terminal_size(),  # Omit 2-line allowance
            ignore_oversize=True,  # For the sake of vertically-oriented images
        )
        rows = ceil(size[1] / 2)
        return rows

    def render(self, size: Tuple[int, int], focus: bool = False) -> urwid.Canvas:
        context = tui_main.get_context()
        image = self._image

        # Forced render

        if mul(*image._original_size) > tui_main.MAX_PIXELS and not (
            self._canv
            and self._canv.size == size
            or (self, size, self._alpha) == __class__._rendering_image_info
        ):
            if self._force_render:
                # `.main.animate_image()` deletes `_force_render` when done with an
                # image to avoid the cost of attribute creation and deletion per frame
                if image._is_animated:
                    if image._seek_position == 0:
                        self._forced_anim_size_hash = hash(size)
                    elif hash(size) != self._forced_anim_size_hash:
                        self._force_render = False
                        if context in self._force_render_contexts:
                            keys.enable_actions(context, "Force Render")
                        return __class__._large_image.render(size, focus)
                else:
                    del self._force_render
            else:
                if context in self._force_render_contexts:
                    keys.enable_actions(context, "Force Render")
                return __class__._large_image.render(size, focus)

        if context in self._force_render_contexts:
            keys.disable_actions(context, "Force Render")

        # Grid cells

        if (
            view.original_widget is image_grid_box
            and context != "full-grid-image"
            # Grid render cell width adjusts when _maxcols_ < _cell_width_
            # `+2` cos `LineSquare` subtracts the columns for surrounding lines
            and size[0] + 2 == image_grid.cell_width
        ):
            canv = __class__._grid_cache.get(basename(image._source))
            if not canv:
                grid_render_queue.put(
                    (
                        (
                            image._source
                            if logging.MULTI and tui_main.GRID_RENDERERS > 0
                            else image
                        ),
                        size,
                        self._alpha,
                    )
                )
                __class__._grid_cache[basename(image._source)] = ...
                canv = __class__._placeholder.render(size, focus)
            elif canv is ...:
                canv = __class__._placeholder.render(size, focus)
            return canv

        # Size augmentation and setting

        if len(size) == 1:
            size = image._valid_size(
                None,
                None,
                maxsize=(size[0], get_terminal_size()[1]),
            )
            size = (size[0], ceil(size[1] / 2))
        image.set_size(maxsize=size)

        # Rendering

        if hasattr(self, "_animator"):
            if self._frame_changed:
                self._frame = next(self._animator)
                self._frame_changed = False
                self._frame_size_hash = hash(size)
            elif hash(size) != self._frame_size_hash:
                # If size changed, re-render the current frame the usual way,
                # with the new size
                self._frame = f"{image:1.1{self._alpha}}"
                self._frame_size_hash = hash(size)
            canv = ImageCanvas(
                self._frame.encode().split(b"\n"), size, image.rendered_size
            )
        elif view.original_widget is image_grid_box and context != "full-grid-image":
            # When the grid render cell width adjusts; when _maxcols_ < _cell_width_
            try:
                canv = ImageCanvas(
                    f"{image:1.1{self._alpha}}".encode().split(b"\n"),
                    size,
                    image.rendered_size,
                )
            except Exception:
                canv = __class__._faulty_image.render(size, focus)
        elif self._canv and self._canv.size == size:
            canv = self._canv
        else:
            if (self, size, self._alpha) != __class__._rendering_image_info:
                image_render_queue.put((self, size, self._alpha))
            canv = __class__._placeholder.render(size)

        return canv


class ImageCanvas(urwid.Canvas):
    cacheable = False

    def __init__(
        self, lines: List[bytes], size: Tuple[int, int], image_size: Tuple[int, int]
    ):
        super().__init__()
        self.size = size
        self.lines = lines
        self._image_size = image_size

    def cols(self) -> int:
        return self.size[0]

    def rows(self) -> int:
        return self.size[1]

    def content(self, trim_left=0, trim_top=0, cols=None, rows=None, attr_map=None):
        diff_x, diff_y = map(sub, self.size, self._image_size)
        pad_up = diff_y // 2
        pad_down = diff_y - pad_up
        pad_left = diff_x // 2
        pad_right = diff_x - pad_left

        cols = cols or self.cols()
        rows = rows or self.rows()

        fill = b" " * cols
        pad_left = b" " * pad_left
        pad_right = b" " * pad_right

        # Upper padding reduces when the top is trimmed
        for _ in range(pad_up - trim_top):
            yield [(None, "U", fill)]

        # If top is not trimmed (_trim_top_ == 0), render all lines
        # If top is trimmed (_trim_top_ > 0),
        # - and _rows_ > _pad_down_, render the last (_rows_ - _pad_down_) lines
        # - and _rows_ <= _pad_down_, do not render any line (i.e lines[len:])
        for line in self.lines[
            trim_top and (-max(0, rows - pad_down) or len(self.lines)) :
        ]:
            yield [(None, "U", pad_left + line + pad_right)]

        # render full lower padding if _rows_ >= _pad_down_,
        # otherwise only _rows_ rows of padding
        for _ in range(min(rows, pad_down)):
            yield [(None, "U", fill)]


class LineSquare(urwid.LineBox):
    no_cache = ["render", "rows"]

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)

        # Prevents `Image.rows()` from being called,
        # in order to get the correct no of rows for a `<LinesSquare <Image>>` widget
        original_middle = self._wrapped_widget.contents[1]
        new_middle = LineSquareMiddleColumns(
            [x[0] for x in original_middle[0].contents],
            box_columns=(0, 2),
            focus_column=original_middle[0].focus_position,
        )
        new_middle.contents[0] = (new_middle.contents[0][0], ("given", 1, True))
        new_middle.contents[2] = (new_middle.contents[2][0], ("given", 1, True))
        self._wrapped_widget.contents[1] = (new_middle, original_middle[1])

    def rows(self, size: Tuple[int, int], focus: bool = False) -> int:
        return ceil(size[0] / 2)

    def render(self, size: Tuple[int, int], focus: bool = False) -> urwid.Canvas:
        return super().render((size[0], ceil(size[0] / 2)), focus)


# To prevent `Image.rows()` from being called,
# in order to get the correct no of rows for a `<LinesSquare <Image>>` widget
class LineSquareMiddleColumns(urwid.Columns):
    no_cache = ["render", "rows"]

    def rows(self, size: Tuple[int, int], focus: bool = False) -> int:
        return ceil(size[0] / 2) - 2


class MenuEntry(urwid.Text):
    _selectable = True

    def keypress(self, size: Tuple[int, int], key: str) -> str:
        return key


class MenuListBox(urwid.ListBox):
    def keypress(self, size: Tuple[int, int], key: str) -> Optional[str]:
        ret = super().keypress(size, key)
        return key if any(key == v[0] for v in nav.values()) else ret


class NoSwitchColumns(urwid.Columns):
    _command_map = urwid.ListBox._command_map.copy()
    for key in (nav["Left"][0], nav["Right"][0]):
        _command_map._command.pop(key)


class PlaceHolder(urwid.SolidFill):
    _selectable = True  # Prevents _image_box_ from being completely un-selectable

    def keypress(self, size: Tuple[int, int], key: str) -> str:
        return key


logger = _logging.getLogger(__name__)

placeholder = PlaceHolder(" ")
menu = MenuListBox(urwid.SimpleFocusListWalker([]))
menu_box = urwid.LineBox(menu, "List", "left")
image_grid = urwid.GridFlow(
    [],
    cell_width,
    2,
    1,
    "left",
)
image_box = urwid.LineBox(placeholder, "Image", "left")
image_grid_box = urwid.LineBox(urwid.Padding(GridListBox(image_grid)), "Image", "left")
view = urwid.AttrMap(
    image_box,
    "unfocused box",
    "focused box",
)
viewer = NoSwitchColumns(
    [
        (
            20,
            urwid.AttrMap(menu_box, "unfocused box", "focused box"),
        ),
        view,
    ]
)
banner = urwid.LineBox(
    urwid.AttrMap(
        urwid.Filler(urwid.Text(("red on green", "Term-Img"), "center")),
        "red on green",
    ),
)
loading = urwid.Text("", "center")
notifications = urwid.Pile([])
notif_bar = urwid.Columns([(3, urwid.Filler(loading)), notifications])
pile = urwid.Pile([(4, banner), viewer, (2, notif_bar)], 1)

info_bar = urwid.Text("")
key_bar = urwid.Filler(urwid.Text([[("mine", "cool"), " "]] * 19 + [("mine", "cool")]))
expand = urwid.Filler(urwid.Text(f"\u25B2 [{expand_key[1]}]", align="right"), "middle")
bottom_bar = urwid.Columns([key_bar, (len(expand.original_widget.text), expand)], 2)

main = urwid.Pile([pile, (1, bottom_bar)], 0)

confirmation = urwid.Text("", "center")
confirmation_overlay = urwid.Overlay(
    urwid.LineBox(
        urwid.Filler(confirmation),
        "",
        "center",
        None,
        "\u2554",
        "\u2550",
        "\u2551",
        "\u2557",
        "\u255a",
        "\u2551",
        "\u2550",
        "\u255d",
    ),
    placeholder,
    "center",
    ("relative", 25),
    "middle",
    ("relative", 25),
    50,
    3,
)

overlay = urwid.Overlay(
    urwid.LineBox(
        urwid.ListBox([placeholder]),
        "Help",
        "center",
        "default bold",
        "\u2554",
        "\u2550",
        "\u2551",
        "\u2557",
        "\u255a",
        "\u2551",
        "\u2550",
        "\u255d",
    ),
    placeholder,
    "center",
    ("relative", 50),
    "middle",
    ("relative", 75),
    100,
    5,
)

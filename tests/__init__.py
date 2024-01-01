import os
from contextlib import contextmanager

import term_image


def get_cell_size():
    return cell_size


def set_cell_size(size):
    global cell_size

    cell_size = size
    term_image.AutoCellRatio.is_supported = None


@contextmanager
def reset_cell_size_ratio():
    cell_ratio = term_image._cell_ratio
    cell_size = get_cell_size()
    try:
        yield
    finally:
        term_image._cell_ratio = cell_ratio
        set_cell_size(cell_size)


def get_terminal_size():
    return os.terminal_size((80, 30))


def get_terminal_name_version():
    return terminal_name_version


def set_terminal_name_version(name: str, version: str = ""):
    global terminal_name_version

    terminal_name_version = (name, version)


def get_fg_bg_colors(*, hex=False):
    return (
        tuple(rgb and "#" + "".join(f"{x:02x}" for x in rgb) for rgb in fg_bg)
        if hex
        else fg_bg
    )


def set_fg_bg_colors(fg=None, bg=None):
    global fg_bg
    fg_bg = (fg, bg)


def _is_on_kitty():
    return is_on_kitty


def toggle_is_on_kitty():
    global is_on_kitty
    is_on_kitty = not is_on_kitty


term_image._utils.get_terminal_size = get_terminal_size

terminal_name_version = ("", "")
term_image._utils.get_terminal_name_version = get_terminal_name_version

cell_size = None
term_image.get_cell_size = get_cell_size
term_image._utils.get_cell_size = get_cell_size

fg_bg = [(0, 0, 0), (0, 0, 0)]
term_image._utils.get_fg_bg_colors = get_fg_bg_colors

import term_image.image  # noqa: E402

term_image.image.GraphicsImage._supported = True

is_on_kitty = False
term_image.image.TextImage._is_on_kitty = staticmethod(_is_on_kitty)

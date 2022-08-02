import term_image


def get_cell_size():
    return cell_size


def set_cell_size(size):
    global cell_size

    cell_size = size
    term_image._auto_font_ratio = None


def get_terminal_size():
    return (80, 30)


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


term_image.utils.get_terminal_size = get_terminal_size

cell_size = None
term_image.get_cell_size = get_cell_size
term_image.utils.get_cell_size = get_cell_size

fg_bg = [(0, 0, 0), (0, 0, 0)]
term_image.utils.get_fg_bg_colors = get_fg_bg_colors

import term_image.image  # noqa: E402

term_image.image.GraphicsImage._supported = True

is_on_kitty = False
term_image.image.TextImage._is_on_kitty = staticmethod(_is_on_kitty)

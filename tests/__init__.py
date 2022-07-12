import term_image


def get_cell_size():
    return cell_size


def set_cell_size(size):
    global cell_size

    cell_size = size
    term_image._auto_font_ratio = None


def get_terminal_size():
    return (80, 30)


term_image.utils.get_terminal_size = get_terminal_size

cell_size = None
term_image.get_cell_size = get_cell_size
term_image.utils.get_cell_size = get_cell_size

import term_image.image  # noqa: E402

term_image.image.GraphicsImage._supported = True

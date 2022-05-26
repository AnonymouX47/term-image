import term_image


def get_cell_size():
    return cell_size


def set_cell_size(size):
    global cell_size

    cell_size = size
    term_image._auto_font_ratio = None


cell_size = None
term_image.get_cell_size = get_cell_size

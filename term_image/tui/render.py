"""Definitions for deferred image rendering"""

from __future__ import annotations

import logging as _logging
from multiprocessing import Queue as mp_Queue
from os.path import split
from queue import Empty, Queue
from typing import Union

from .. import get_font_ratio, logging, notify, set_font_ratio
from ..logging_multi import Process


def manage_image_renders():
    from .main import update_screen
    from .widgets import Image, ImageCanvas, image_box

    multi = logging.MULTI
    image_render_in = (mp_Queue if multi else Queue)()
    image_render_out = (mp_Queue if multi else Queue)()
    renderer = (Process if multi else logging.Thread)(
        target=render_images,
        args=(image_render_in, image_render_out, get_font_ratio()),
        kwargs=dict(multi=multi, out_extras=False, log_faults=True),
        name="ImageRenderer",
        redirect_notifs=True,
    )
    renderer.start()
    faulty_image = Image._faulty_image
    last_image_w = image_box.original_widget
    # To prevent an `AttributeError` with the first deletion, while avoiding `hasattr()`
    last_image_w._canv = None

    while True:
        image_w, size, alpha = image_render_queue.get()
        if not image_w:
            break
        if image_w is not image_box.original_widget:
            continue

        # Stored at this point to prevent an incorrect *rendered_size* for the
        # Imagecanvas, since the image's size might've changed by the time the canvas is
        # being created.
        rendered_size = image_w._image.rendered_size

        Image._rendering_image_info = (image_w, size, alpha)
        image_render_in.put(
            (
                image_w._image._source if multi else image_w._image,
                size,
                alpha,
                image_w._faulty,
            )
        )
        notify.start_loading()
        render = image_render_out.get()
        Image._rendering_image_info = (None,) * 3

        if image_w is image_box.original_widget:
            del last_image_w._canv
            if render:
                image_w._canv = ImageCanvas(
                    render.encode().split(b"\n"), size, rendered_size
                )
            else:
                image_w._canv = faulty_image.render(size)
                # Ensures a fault is logged only once per `Image` instance
                if not image_w._faulty:
                    image_w._faulty = True
            update_screen()
            last_image_w = image_w
        notify.stop_loading()

    image_render_in.put((None,) * 4)
    renderer.join()


def manage_grid_renders(n_renderers: int):
    """Manages grid cell rendering.

    Intended to be executed in a separate thread of the main process.

    If multiprocessing is enabled and *n_renderers* > 0, it spwans *n_renderers*
    subprocesses to render the cells and handles their proper termination.
    Otherwise, it starts a single new thread to render the cells.
    """
    from . import main
    from .main import grid_active, grid_change, quitting, update_screen
    from .widgets import Image, ImageCanvas, image_grid

    multi = logging.MULTI and n_renderers > 0
    grid_render_in = (mp_Queue if multi else Queue)()
    grid_render_out = (mp_Queue if multi else Queue)()
    renderers = [
        (Process if multi else logging.Thread)(
            target=render_images,
            args=(
                grid_render_in,
                grid_render_out,
                get_font_ratio(),
            ),
            kwargs=dict(multi=multi, out_extras=True, log_faults=False),
            name="GridRenderer" + f"-{n}" * multi,
        )
        for n in range(n_renderers if multi else 1)
    ]
    for renderer in renderers:
        renderer.start()

    cell_width = grid_path = None  # Silence flake8's F821
    faulty_image = Image._faulty_image
    grid_cache = Image._grid_cache
    new_grid = False

    while True:
        while not (
            grid_active.wait(0.1) or quitting.is_set() or not grid_render_out.empty()
        ):
            pass
        if quitting.is_set():
            break

        if new_grid or grid_change.is_set():  # New grid
            grid_cache.clear()
            grid_change.clear()  # Signal "cache cleared"
            if not new_grid:  # The starting `None` hasn't been gotten
                while grid_render_queue.get():
                    pass
            while not grid_render_in.empty():
                grid_render_in.get()
                notify.stop_loading()
            while not grid_render_out.empty():
                grid_render_out.get()
                notify.stop_loading()
            cell_width = image_grid.cell_width
            grid_path = main.grid_path
            new_grid = False

        if grid_change.is_set():
            continue

        if grid_active.is_set():
            try:
                image_info = grid_render_queue.get(timeout=0.02)
            except Empty:
                pass
            else:
                if not image_info:  # Start of a new grid
                    new_grid = True
                    continue
                grid_render_in.put(image_info)
                notify.start_loading()

        if grid_change.is_set():
            continue

        try:
            image_path, image, size, rendered_size = grid_render_out.get(timeout=0.02)
        except Empty:
            pass
        else:
            dir, entry = split(image_path)
            # The directory and cell-width checks are to filter out any remnants that
            # were still being rendered at the other end
            if (
                not grid_change.is_set()
                and dir == grid_path
                and size[0] + 2 == cell_width
            ):
                grid_cache[entry] = (
                    ImageCanvas(image.encode().split(b"\n"), size, rendered_size)
                    if image
                    else faulty_image.render(size)
                )
                if grid_active.is_set():
                    update_screen()
            notify.stop_loading()

    while not grid_render_in.empty():
        grid_render_in.get()
    for renderer in renderers:
        grid_render_in.put((None,) * 3)
    for renderer in renderers:
        renderer.join()


def render_images(
    input: Union[Queue, mp_Queue],
    output: Union[Queue, mp_Queue],
    font_ratio: float,
    *,
    multi: bool,
    out_extras: bool,
    log_faults: bool,
):
    """Renders images.

    Args:
        multi: True if being executed in a subprocess and False if in a thread.
        out_extras: If True, image details other than the render output are passed out.
    Intended to be executed in a subprocess or thread.
    """
    from ..image import TermImage

    if multi:
        set_font_ratio(font_ratio)

    while True:
        if log_faults:
            image, size, alpha, faulty = input.get()
        else:
            image, size, alpha = input.get()

        if not image:  # Quitting
            break

        if multi:
            image = TermImage.from_file(image)
        image.set_size(maxsize=size)

        # Using `TermImage` for padding will use more memory since all the
        # spaces will be in the render output string, and theoretically more time
        # with all the checks and string splitting & joining.
        # While `ImageCanvas` is better since it only stores the main image render
        # string (as a list though) then generates and yields the complete lines
        # **as needed**. Trimmed padding lines are never generated at all.
        try:
            output.put(
                (image._source, f"{image:1.1{alpha}}", size, image.rendered_size)
                if out_extras
                else f"{image:1.1{alpha}}"
            )
        except Exception as e:
            output.put(
                (image._source, None, size, image.rendered_size) if out_extras else None
            )
            # *faulty* ensures a fault is logged only once per `Image` instance
            if log_faults:
                if not faulty:
                    logging.log_exception(
                        f"Failed to load or render {image._source!r}",
                        logger,
                    )
                notify.notify(str(e), level=notify.ERROR)


logger = _logging.getLogger(__name__)
grid_render_queue = Queue()
image_render_queue = Queue()

"""Definitions for deferred image rendering"""

import logging as _logging
from multiprocessing import Process, Queue as mp_Queue
from os.path import split
from queue import Empty, Queue
from threading import Thread
from typing import Union

from .. import get_font_ratio, logging, notify, set_font_ratio
from ..logging_multi import redirect_logs


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
        (Process if multi else Thread)(
            target=render_grid_images,
            args=(
                grid_render_in,
                grid_render_out,
                get_font_ratio(),
                multi,
            ),
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
        grid_render_in.put((None, None, None))
    for renderer in renderers:
        renderer.join()


def render_grid_images(
    input: Union[Queue, mp_Queue],
    output: Union[Queue, mp_Queue],
    font_ratio: float,
    multi: bool,
):
    """Renders grid cells.

    Intended to be executed in a subprocess or thread.
    *multi* should be True if being executed in a subprocess and False if in a thread.
    """
    from ..image import TermImage

    if multi:
        redirect_logs(logger)
        set_font_ratio(font_ratio)

    logger.debug("Starting")
    try:
        while True:
            image, size, alpha = input.get()
            if not image:  # Quitting
                break

            if multi:
                image = TermImage.from_file(image)
            image.set_size(maxsize=size)
            try:
                output.put(
                    (image._source, f"{image:1.1{alpha}}", size, image.rendered_size)
                )
            except Exception:
                output.put((image._source, None, size, image.rendered_size))
    except KeyboardInterrupt:
        logger.debug("Interrupted")
    except Exception:
        logging.log_exception("Aborted", logger)
    else:
        logger.debug("Exiting")


logger = _logging.getLogger(__name__)
grid_render_queue = Queue()

"""Definitions for deferred image rendering"""

from __future__ import annotations

import logging as _logging
from multiprocessing import Event as mp_Event, Queue as mp_Queue
from os.path import split
from queue import Empty, Queue
from threading import Event
from typing import Optional, Union

from .. import cli, logging, notify
from ..logging_multi import Process
from ..utils import clear_queue


def manage_anim_renders() -> bool:
    from .main import ImageClass, update_screen
    from .widgets import ImageCanvas, image_box

    def next_frame() -> None:
        if image_box.original_widget is image_w and (
            not forced or image_w._ti_force_render
        ):
            frame, repeat, frame_no, size, rendered_size = frame_render_out.get()
            if frame:
                canv = ImageCanvas(frame.encode().split(b"\n"), size, rendered_size)
                image_w._ti_image._seek_position = frame_no
                image_w._ti_frame = (canv, repeat, frame_no)
            else:
                image_w._ti_anim_finished = True
        else:
            frame_render_in.put((..., None, None))
            clear_queue(frame_render_out)  # In case output is full
            frame = None

        if not frame:
            try:
                del image_w._ti_frame
                if forced:
                    # See "Forced render" section of `.widgets.Image.render()`
                    del image_w._ti_force_render
                    del image_w._ti_forced_anim_size_hash
            except AttributeError:
                pass

        update_screen()
        return bool(frame)

    frame_render_in = (mp_Queue if logging.MULTI else Queue)()
    frame_render_out = (mp_Queue if logging.MULTI else Queue)(20)
    ready = (mp_Event if logging.MULTI else Event)()
    renderer = (Process if logging.MULTI else logging.Thread)(
        target=render_frames,
        args=(
            frame_render_in,
            frame_render_out,
            ready,
            ImageClass,
            anim_style_specs.get(cli.args.style, ""),
            REPEAT,
            ANIM_CACHED,
        ),
        name="FrameRenderer",
    )
    renderer.start()

    image_w = None  # Silence flake8's F821
    frame_duration = None
    while True:
        try:
            data, size, forced = anim_render_queue.get(timeout=frame_duration)
        except Empty:
            if not next_frame():
                frame_duration = None
        else:
            if not data:
                break

            notify.start_loading()

            ready.clear()
            frame_render_in.put((..., None, None))
            clear_queue(frame_render_out)  # In case output is full
            ready.wait()
            clear_queue(frame_render_out)  # multiprocessing queues are not so reliable

            if isinstance(data, tuple):
                frame_render_in.put((data, size, image_w._ti_alpha))
                if not next_frame():
                    frame_duration = None
                try:
                    del image_w._ti_canv  # Set in `.widgets.Image.render()`
                except AttributeError:
                    pass
            else:
                image_w = data
                frame_render_in.put(
                    (image_w._ti_image._source, size, image_w._ti_alpha)
                )
                frame_duration = FRAME_DURATION or image_w._ti_image._frame_duration
                # Ensures successful deletion when the displayed image has changed
                image_w._ti_frame = None
                if not next_frame():
                    frame_duration = None
                del image_w._ti_anim_starting

            notify.stop_loading()

    clear_queue(frame_render_in)
    frame_render_in.put((None,) * 3)
    clear_queue(frame_render_out)  # In case output is full
    renderer.join()
    clear_queue(anim_render_queue)


def manage_image_renders():
    from .main import ImageClass, update_screen
    from .widgets import Image, ImageCanvas, image_box

    multi = logging.MULTI
    image_render_in = (mp_Queue if multi else Queue)()
    image_render_out = (mp_Queue if multi else Queue)()
    renderer = (Process if multi else logging.Thread)(
        target=render_images,
        args=(
            image_render_in,
            image_render_out,
            ImageClass,
            image_style_specs.get(cli.args.style, ""),
        ),
        kwargs=dict(multi=multi, out_extras=False, log_faults=True),
        name="ImageRenderer",
        redirect_notifs=True,
    )
    renderer.start()
    faulty_image = Image._ti_faulty_image
    last_image_w = image_box.original_widget
    # To prevent an `AttributeError` with the first deletion, while avoiding `hasattr()`
    last_image_w._ti_canv = None

    while True:
        image_w, size, alpha = image_render_queue.get()
        if not image_w:
            break
        if image_w is not image_box.original_widget:
            continue

        # Stored at this point to prevent an incorrect *rendered_size* for the
        # Imagecanvas, since the image's size might've changed by the time the canvas is
        # being created.
        rendered_size = image_w._ti_image.rendered_size

        Image._ti_rendering_image_info = (image_w, size, alpha)
        image_render_in.put(
            (
                image_w._ti_image._source if multi else image_w._ti_image,
                size,
                alpha,
                image_w._ti_faulty,
            )
        )
        notify.start_loading()
        render = image_render_out.get()
        Image._ti_rendering_image_info = (None,) * 3

        if image_w is image_box.original_widget:
            del last_image_w._ti_canv
            if render:
                image_w._ti_canv = ImageCanvas(
                    render.encode().split(b"\n"), size, rendered_size
                )
            else:
                image_w._ti_canv = faulty_image.render(size)
                # Ensures a fault is logged only once per `Image` instance
                if not image_w._ti_faulty:
                    image_w._ti_faulty = True
            update_screen()
            last_image_w = image_w
        notify.stop_loading()

    clear_queue(image_render_in)
    image_render_in.put((None,) * 4)
    renderer.join()
    clear_queue(image_render_queue)


def manage_grid_renders(n_renderers: int):
    """Manages grid cell rendering.

    Intended to be executed in a separate thread of the main process.

    If multiprocessing is enabled and *n_renderers* > 0, it spwans *n_renderers*
    subprocesses to render the cells and handles their proper termination.
    Otherwise, it starts a single new thread to render the cells.
    """
    from . import main
    from .main import ImageClass, grid_active, grid_change, quitting, update_screen
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
                ImageClass,
                grid_style_specs.get(cli.args.style, ""),
            ),
            kwargs=dict(multi=multi, out_extras=True, log_faults=False),
            name="GridRenderer" + f"-{n}" * multi,
        )
        for n in range(n_renderers if multi else 1)
    ]
    for renderer in renderers:
        renderer.start()

    cell_width = grid_path = None  # Silence flake8's F821
    faulty_image = Image._ti_faulty_image
    grid_cache = Image._ti_grid_cache
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
            for q in (grid_render_in, grid_render_out):
                while True:
                    try:
                        q.get(timeout=0.005)
                        notify.stop_loading()
                    except Empty:
                        break
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

    clear_queue(grid_render_in)
    for renderer in renderers:
        grid_render_in.put((None,) * 3)
    for renderer in renderers:
        renderer.join()
    clear_queue(grid_render_queue)


def render_frames(
    input: Union[Queue, mp_Queue],
    output: Union[Queue, mp_Queue],
    ready: Union[Event, mp_Event],
    ImageClass: type,
    style_spec: str,
    repeat: int,
    cached: Union[bool, int],
):
    """Renders animation frames.

    Intended to be executed in a subprocess or thread.
    """
    from ..image import ImageIterator

    image = animator = None  # Silence flake8's F821
    block = True
    while True:
        try:
            data, size, alpha = input.get(block)
        except Empty:
            try:
                output.put(
                    (
                        next(animator),
                        animator._loop_no,
                        image.tell(),
                        size,
                        image.rendered_size,
                    )
                )
            except StopIteration:
                output.put((None,) * 5)
                block = True
        else:
            if not data:
                break

            if data is ...:
                try:
                    animator.close()
                except AttributeError:  # First time
                    pass
                clear_queue(output)
                ready.set()
                block = True
            elif isinstance(data, tuple):
                new_repeat, frame_no = data
                animator = ImageIterator(
                    image, new_repeat, f"1.1{alpha}{style_spec}", cached
                )
                next(animator)
                animator.seek(frame_no)
                image.set_size(maxsize=size)
                block = False
            else:
                # A new image is always created to ensure the seek position of the image
                # in MainProcess::MainThread is always correct, since frames should be
                # rendered ahead.
                image = ImageClass.from_file(data)
                animator = ImageIterator(
                    image, repeat, f"1.1{alpha}{style_spec}", cached
                )
                image.set_size(maxsize=size)
                block = False

    clear_queue(output)


def render_images(
    input: Union[Queue, mp_Queue],
    output: Union[Queue, mp_Queue],
    ImageClass: type,
    style_spec: str,
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
    while True:
        if log_faults:
            image, size, alpha, faulty = input.get()
        else:
            image, size, alpha = input.get()

        if not image:  # Quitting
            break

        if multi:
            image = ImageClass.from_file(image)
        image.set_size(maxsize=size)

        # Using `BaseImage` for padding will use more memory since all the
        # spaces will be in the render output string, and theoretically more time
        # with all the checks and string splitting & joining.
        # While `ImageCanvas` is better since it only stores the main image render
        # string (as a list though) then generates and yields the complete lines
        # **as needed**. Trimmed padding lines are never generated at all.
        try:
            output.put(
                (
                    image._source,
                    f"{image:1.1{alpha}{style_spec}}",
                    size,
                    image.rendered_size,
                )
                if out_extras
                else f"{image:1.1{alpha}{style_spec}}"
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

    clear_queue(output)


logger = _logging.getLogger(__name__)
anim_render_queue = Queue()
grid_render_queue = Queue()
image_render_queue = Queue()

# Updated from `.tui.init()`
anim_style_specs = {"kitty": "+W", "iterm2": "+Wm1"}
grid_style_specs = {"kitty": "+L", "iterm2": "+L"}
image_style_specs = {"kitty": "+W", "iterm2": "+W"}

# Set from `.tui.init()`
# # Corresponsing to command-line args
ANIM_CACHED: Union[None, bool, int] = None
FRAME_DURATION: Optional[float] = None
REPEAT: Optional[int] = None

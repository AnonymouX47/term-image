"""Term-Image's Terminal User Interface"""

from __future__ import annotations

import argparse
import logging as _logging
import os
from pathlib import Path
from typing import Iterable, Iterator, Tuple, Union

import urwid

from .. import logging
from ..config import max_notifications
from . import main
from .main import process_input, scan_dir_grid, scan_dir_menu, sort_key_lexi
from .render import image_render_queue, manage_grid_renders, manage_image_renders
from .widgets import Image, info_bar, main as main_widget, notif_bar, pile


def init(
    args: argparse.Namespace,
    images: Iterable[Tuple[str, Union[Image, Iterator]]],
    contents: dict,
) -> None:
    """Initializes the TUI"""
    global is_launched

    if not logging.QUIET and max_notifications:
        pile.contents.append((notif_bar, ("given", max_notifications)))
    if args.debug:
        main_widget.contents.insert(
            -1, (urwid.AttrMap(urwid.Filler(info_bar), "input"), ("given", 1))
        )

    main.ANIM_CACHED = not args.cache_no_anim and (
        args.cache_all_anim or args.anim_cache
    )
    main.DEBUG = args.debug
    main.FRAME_DURATION = args.frame_duration
    main.GRID_RENDERERS = args.grid_renderers
    main.MAX_PIXELS = args.max_pixels
    main.NO_ANIMATION = args.no_anim
    main.REPEAT = args.repeat
    main.RECURSIVE = args.recursive
    main.SHOW_HIDDEN = args.all
    main.loop = Loop(main_widget, palette, unhandled_input=process_input)
    main.update_pipe = main.loop.watch_pipe(lambda _: None)

    images.sort(
        key=lambda x: sort_key_lexi(Path(x[0] if x[1] is ... else x[1]._image._source))
    )
    main.displayer = main.display_images(".", images, contents, top_level=True)

    # daemon, to avoid having to check if the main process has been interrupted
    menu_scanner = logging.Thread(target=scan_dir_menu, name="MenuScanner", daemon=True)
    grid_scanner = logging.Thread(target=scan_dir_grid, name="GridScanner", daemon=True)
    grid_render_manager = logging.Thread(
        target=manage_grid_renders,
        args=(args.grid_renderers,),
        name="GridRenderManager",
        daemon=True,
    )
    image_render_manager = logging.Thread(
        target=manage_image_renders,
        name="ImageRenderManager",
        daemon=True,
    )

    main.loop.screen.clear()
    main.loop.screen.set_terminal_properties(2**24)

    Image._alpha = (
        "#" if args.no_alpha else "#" + (args.alpha_bg or f"{args.alpha:f}"[1:])
    )

    logger = _logging.getLogger(__name__)
    logging.log("Launching TUI", logger, direct=False)
    main.set_context("menu")
    is_launched = True
    menu_scanner.start()
    grid_scanner.start()
    grid_render_manager.start()
    image_render_manager.start()

    try:
        print("\033[?1049h", end="", flush=True)  # Switch to the alternate buffer
        next(main.displayer)
        main.loop.run()
        grid_render_manager.join()
        image_render_queue.put((None,) * 3)
        image_render_manager.join()
        logging.log("Exited TUI normally", logger, direct=False)
    except (KeyboardInterrupt, Exception):
        main.interrupted.set()  # Signal interruption to other threads.
        raise
    finally:
        # urwid fails to restore the normal buffer on some terminals
        print("\033[?1049l", end="", flush=True)  # Switch back to the normal buffer
        main.displayer.close()
        is_launched = False
        os.close(main.update_pipe)


class Loop(urwid.MainLoop):
    def start(self):
        # Properly set expand key visbility at initialization
        self.unhandled_input("resized")
        return super().start()

    def process_input(self, keys):
        if "window resize" in keys:
            # Adjust bottom bar upon window resize
            keys.append("resized")
        return super().process_input(keys)


is_launched = False

palette = [
    ("default", "", "", "", "#ffffff", ""),
    ("default bold", "", "", "", "#ffffff, bold", ""),
    ("inactive", "", "", "", "#7f7f7f", ""),
    ("white on black", "", "", "", "#ffffff", "#000000"),
    ("black on white", "", "", "", "#000000", "#ffffff"),
    ("mine", "", "", "", "#ff00ff", "#ffff00"),
    ("focused entry", "", "", "", "standout", ""),
    ("unfocused box", "", "", "", "#7f7f7f", ""),
    ("focused box", "", "", "", "#ffffff", ""),
    ("green fg", "", "", "", "#00ff00", ""),
    ("red on green", "", "", "", "#ff0000,bold", "#00ff00"),
    ("key", "", "", "", "#ffffff", "#5588ff"),
    ("disabled key", "", "", "", "#7f7f7f", "#5588ff"),
    ("error", "", "", "", "bold", "#ff0000"),
    ("warning", "", "", "", "#ff0000, bold", ""),
    ("input", "", "", "", "standout", ""),
]

"""Term-Image's Terminal User Interface"""

from __future__ import annotations

import argparse
import logging as _logging
import os
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, Tuple, Union

import urwid

from .. import logging
from ..config import max_notifications
from ..utils import CSI, lock_tty
from . import main, render
from .main import process_input, scan_dir_grid, scan_dir_menu, sort_key_lexi
from .widgets import Image, ImageCanvas, info_bar, main as main_widget, notif_bar, pile


def init(
    args: argparse.Namespace,
    style_args: Dict[str, Any],
    images: Iterable[Tuple[str, Union[Image, Iterator]]],
    contents: dict,
    ImageClass: type,
) -> None:
    """Initializes the TUI"""
    global is_launched

    if not logging.QUIET and max_notifications:
        pile.contents.append((notif_bar, ("given", max_notifications)))
    if args.debug:
        main_widget.contents.insert(
            -1, (urwid.AttrMap(urwid.Filler(info_bar), "input"), ("given", 1))
        )

    main.DEBUG = args.debug
    main.GRID_RENDERERS = args.grid_renderers
    main.MAX_PIXELS = args.max_pixels
    main.NO_ANIMATION = args.no_anim
    main.RECURSIVE = args.recursive
    main.SHOW_HIDDEN = args.all
    main.ImageClass = ImageClass
    main.loop = Loop(main_widget, palette, unhandled_input=process_input)
    main.update_pipe = main.loop.watch_pipe(lambda _: None)

    render.ANIM_CACHED = not args.cache_no_anim and (
        args.cache_all_anim or args.anim_cache
    )
    render.FRAME_DURATION = args.frame_duration
    render.REPEAT = args.repeat

    images.sort(
        key=lambda x: sort_key_lexi(
            Path(x[0] if x[1] is ... else x[1]._ti_image._source)
        )
    )
    main.displayer = main.display_images(".", images, contents, top_level=True)

    # `z_index=None` is pretty glitchy for animations with WHOLE method
    if args.style == "kitty" and ImageClass._KITTY_VERSION:
        render.anim_style_specs["kitty"] = "+L"
    for name in ("anim", "grid", "image"):
        specs = getattr(render, f"{name}_style_specs")
        if args.style == "kitty":
            # Kitty blends images at the same z-index
            if ImageClass._KITTY_VERSION:
                specs["kitty"] += "z"
            # Would've been removed if it had the default value
            if "compress" in style_args:
                specs["kitty"] += f"c{style_args['compress']}"
        elif args.style == "iterm2" and "compress" in style_args:
            specs["iterm2"] += f"c{style_args['compress']}"

    Image._ti_alpha = (
        "#"
        if args.no_alpha
        else (
            "#" + f"{args.alpha:f}"[1:]
            if args.alpha_bg is None
            else "#" + (args.alpha_bg or "#")
        )
    )
    Image._ti_grid_style_spec = render.grid_style_specs.get(args.style, "")

    # daemon, to avoid having to check if the main process has been interrupted
    menu_scanner = logging.Thread(target=scan_dir_menu, name="MenuScanner", daemon=True)
    grid_scanner = logging.Thread(target=scan_dir_grid, name="GridScanner", daemon=True)
    grid_render_manager = logging.Thread(
        target=render.manage_grid_renders,
        args=(args.grid_renderers,),
        name="GridRenderManager",
        daemon=True,
    )
    image_render_manager = logging.Thread(
        target=render.manage_image_renders,
        name="ImageRenderManager",
        daemon=True,
    )
    anim_render_manager = logging.Thread(
        target=render.manage_anim_renders,
        name="AnimRenderManager",
        daemon=True,
    )

    urwid.raw_display.Screen.get_available_raw_input = lock_tty(
        urwid.raw_display.Screen.get_available_raw_input
    )
    main.loop.screen.clear()
    main.loop.screen.set_terminal_properties(2**24)

    logger = _logging.getLogger(__name__)
    logging.log("Launching TUI", logger, direct=False)
    main.set_context("menu")
    is_launched = True
    menu_scanner.start()
    grid_scanner.start()
    grid_render_manager.start()
    image_render_manager.start()
    anim_render_manager.start()

    try:
        print(f"{CSI}?1049h", end="", flush=True)  # Switch to the alternate buffer
        next(main.displayer)
        main.loop.run()
        grid_render_manager.join()
        render.image_render_queue.put((None,) * 3)
        image_render_manager.join()
        render.anim_render_queue.put((None,) * 3)
        anim_render_manager.join()
        logging.log("Exited TUI normally", logger, direct=False)
    finally:
        # urwid fails to restore the normal buffer on some terminals
        print(f"{CSI}?1049l", end="", flush=True)  # Switch back to the normal buffer
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
            main.ImageClass._clear_images() and ImageCanvas.change()
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

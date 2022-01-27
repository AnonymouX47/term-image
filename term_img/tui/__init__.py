"""Term-Img's Terminal User Interface"""

import argparse
import logging
from typing import Iterable, Iterator, Tuple, Union

import urwid

from .main import process_input
from .widgets import Image, info_bar, main as main_widget
from . import main
from .. import cli


def init(
    args: argparse.Namespace,
    images: Iterable[Tuple[str, Union[Image, Iterator]]],
    contents: dict,
) -> None:
    """Initializes the TUI"""
    from ..logging import log

    global is_launched

    if cli.args.debug:
        main_widget.contents.insert(
            -1, (urwid.AttrMap(urwid.Filler(info_bar), "input"), ("given", 1))
        )

    main.FRAME_DURATION = args.frame_duration
    main.MAX_PIXELS = args.max_pixels
    main.NO_ANIMATION = args.no_anim
    main.RECURSIVE = args.recursive
    main.SHOW_HIDDEN = args.all
    main.displayer = main.display_images(".", iter(images), contents, top_level=True)
    main.loop = Loop(main_widget, palette, unhandled_input=process_input)

    main.loop.screen.clear()
    main.loop.screen.set_terminal_properties(2 ** 24)

    Image._alpha = (
        "#" if args.no_alpha else "#" + (args.alpha_bg or f"{args.alpha:f}"[1:])
    )

    logger = logging.getLogger(__name__)
    log("Launching TUI", logger, direct=False)
    main.set_context("menu")
    is_launched = True

    try:
        next(main.displayer)
        main.loop.run()
        log("Exited TUI normally", logger, direct=False)
    finally:
        main.displayer.close()
        is_launched = False


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

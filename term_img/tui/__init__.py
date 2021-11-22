"""Term-Img's Terminal User Interface"""

from __future__ import annotations

import argparse
from typing import Iterable, Iterator, Tuple, Union

from . import main
from .widgets import Image


def init(
    args: argparse.Namespace,
    images: Iterable[Tuple[str, Union[Image, Iterator]]],
    contents: dict,
) -> None:
    """Initializes the TUI"""
    main.recursive = args.recursive
    main.show_hidden = args.all
    main.displayer = main.display_images(".", iter(images), contents, top_level=True)
    next(main.displayer)
    main.loop.run()

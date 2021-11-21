"""Main UI"""

from __future__ import annotations

import os
from typing import Generator, Iterator, Tuple, Union

import urwid
from PIL import Image, UnidentifiedImageError

from .keys import keys
from .widgets import info_bar, image_box, main, menu, view, viewer
from ..image import TermImage


def display_images(
    dir: str,
    images: Iterator[Tuple[str, Union[TermImage, Iterator]]],
    contents: dict,
    prev_dir: str = "..",
    *,
    top_level: bool = False,
) -> None:
    """Display images in _dir_ (and sub-directories, if '--recursive' is set)
    as yielded by `scan_dir(dir)`.

    Args:
        - dir: Path to directory containing images.
        - images: An iterator yielding the images in _dir_ and/or similar iterators
            for sub-directories of _dir_.
        - contents: Tree of directories containing readable images
            (as produced by `check_dir(dir)`).
        - prev_dir: Path to set as working directory after displaying images in _dir_
            (default:  parent directory of _dir_).
        - top_level: Specifies if _dir_ is the top level (For internal use only).
    """
    global depth
    images = sorted(
        images,
        key=lambda x: x[0].upper() if isinstance(x[1], TermImage) else x[0].lower(),
    )
    os.chdir(dir)
    depth += 1

    if not top_level:
        print("|  " * depth + "..")
    for entry, value in images:
        if isinstance(value, TermImage):  # Image file
            print("|  " * depth + entry)
        else:  # Directory
            print("|  " * (depth - 1) + "|--" * (not top_level) + f"{entry}/:")
            if not value.gi_frame:  # The directory has been visited earlier
                if top_level or os.path.islink(entry):
                    # Return to Top-Level Directory, OR
                    # Return to the link's parent rather than the linked directory's
                    # parent
                    value = scan_dir(entry, contents[entry], os.getcwd())
                else:
                    value = scan_dir(entry, contents[entry])
            if top_level or os.path.islink(entry):  # broken symlinks already eliminated
                # Return to Top-Level Directory, OR
                # Return to the link's parent rather than the linked directory's parent
                display_images(entry, value, contents[entry], os.getcwd())
            else:
                display_images(entry, value, contents[entry])
    depth -= 1
    if not top_level:
        os.chdir(prev_dir)


def _process_input(key):
    info_bar.original_widget.set_text(f"{key!r} {info_bar.original_widget.text}")

    found = False
    if key in keys["global"]:
        keys["global"][key]()
        found = True
    else:
        found = keys[context].get(key, lambda: False)() is None

    if key[0] == "mouse press":  # strings also support subscription
        # change context if the pane in focus changed.
        if context in {"image", "image-grid"} and viewer.focus_position == 0:
            set_context("menu")
        elif context == "menu":
            if viewer.focus_position == 1:
                set_context(
                    "image" if view.original_widget is image_box else "image-grid"
                )
            else:  # Update image view
                displayer.send(menu.focus_position)

    return bool(found)


def scan_dir(
    dir: str, contents: dict, prev_dir: str = ".."
) -> Generator[Tuple[str, Union[TermImage, Generator]], None, None]:
    """Scan _dir_ (and sub-directories, if '--recursive' is set) for readable images
    using a directory tree of the form produced by `check_dir(dir)`.

    Args:
        - dir: Path to directory to be scanned.
        - contents: Tree of directories containing readable images
            (as produced by `check_dir(dir)`).
        - prev_dir: Path to set as working directory after scannning _dir_
            (default:  parent directory of _dir_).

    Yields:
        - A `TermImage` instance for each image in _dir_.
        - A similar generator for sub-directories (if '--recursive' is set).

    - If '--hidden' is set, hidden (.*) images and subdirectories are considered.
    """
    os.chdir(dir)
    for entry in os.listdir():
        if entry.startswith(".") and not show_hidden:
            continue
        if os.path.isfile(entry):
            try:
                Image.open(entry)
            except UnidentifiedImageError:
                # Reporting will apply to every non-image file :(
                pass
            except Exception as e:
                print(
                    f"{os.path.realpath(entry)!r} could not be read: "
                    f"{type(e).__name__}: {e}"
                )
            else:
                yield entry, TermImage.from_file(entry)
        elif recursive and entry in contents:
            if os.path.islink(entry):  # check_dir() already eliminates broken symlinks
                # Return to the link's parent rather than the linked directory's parent
                yield (
                    entry,
                    scan_dir(entry, contents[entry], os.getcwd()),
                )
            else:
                yield entry, scan_dir(entry, contents[entry])

    os.chdir(prev_dir)


def set_context(new_context):
    global context
    context = new_context


class MyLoop(urwid.MainLoop):
    def start(self):
        # Properly set expand key visbility at initialization
        self.unhandled_input("resized")
        return super().start()

    def process_input(self, keys):
        if "window resize" in keys:
            # Adjust bottom bar upon window resize
            keys.append("resized")
        return super().process_input(keys)


context = "menu"
depth = -1
menu_list = []

palette = [
    ("default", "", "", "", "#ffffff", "#000000"),
    ("white on black", "", "", "", "#ffffff", "#000000"),
    ("black on white", "", "", "", "#000000", "#ffffff"),
    ("mine", "", "", "", "#ff00ff", "#ffff00"),
    ("focused entry", "", "", "", "standout", ""),
    ("unfocused box", "", "", "", "#7f7f7f", ""),
    ("focused box", "", "", "", "#ffffff", ""),
    ("green fg", "", "", "", "#00ff00", ""),
    ("red on green", "", "", "", "#ff0000,bold", "#00ff00"),
]

loop = MyLoop(main, palette, unhandled_input=_process_input)
loop.screen.clear()
loop.screen.set_terminal_properties(2 ** 24)

# Placeholders; Set from `..tui.init()`
displayer = None
recursive = None
show_hidden = None

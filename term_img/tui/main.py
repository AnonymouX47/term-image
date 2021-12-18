"""Main UI"""

from __future__ import annotations

import os
from os.path import basename, isfile, islink, realpath
from typing import Generator, Iterable, Iterator, Tuple, Union

import PIL
import urwid

from .keys import _display_context_keys, keys
from .widgets import (
    info_bar,
    Image,
    image_box,
    image_grid,
    image_grid_box,
    LineSquare,
    main,
    menu,
    MenuEntry,
    _placeholder,
    view,
    viewer,
)
from ..image import TermImage


def display_images(
    dir: str,
    items: Iterator[Tuple[str, Union[Image, Iterator]]],
    contents: dict,
    prev_dir: str = "..",
    *,
    top_level: bool = False,
) -> Generator[None, int, None]:
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
    # global depth

    items = sorted(
        items,
        key=(
            (
                lambda x: (
                    basename(x[0]).upper()
                    if isinstance(x[1], Image)
                    else basename(x[0]).lower()
                )
            )
            if top_level
            else (lambda x: x[0].upper() if isinstance(x[1], Image) else x[0].lower())
        ),
    )
    _update_menu(items, top_level)
    pos = 0

    os.chdir(dir)
    # depth += 1

    while True:
        if pos == -1:  # Cursor on top menu item ("..")
            if top_level:  # noqa: F821
                # Ensure ".." is not selectable at top level
                # Possible when `Home` action is invoked
                pos = 0
                menu.focus_position = 1
                continue
            image_box._w.contents[1][0].contents[1] = (
                _placeholder,
                ("weight", 1, False),
            )
            image_box.set_title("Image")
            view.original_widget = image_box

        elif pos == -2:  # Implements "menu::Open" action
            if prev_pos == -1:  # noqa: F821
                # prev_pos can never be -1 at top level; See `pos == -1` branch above
                break

            if not value.gi_frame:  # noqa: F821
                # The directory has been visited earlier
                value = scan_dir(
                    entry,  # noqa: F821
                    contents[entry],  # noqa: F821
                    # Return to Top-Level Directory, OR
                    # Return to the link's parent rather than the linked directory's
                    # parent
                    os.getcwd() if top_level or islink(entry) else "..",  # noqa: F821
                )

            yield from display_images(
                entry,  # noqa: F821
                value,  # noqa: F821
                contents[entry],  # noqa: F821
                # Return to Top-Level Directory, OR
                # Return to the link's parent rather than the linked directory's parent
                os.getcwd() if top_level or islink(entry) else "..",  # noqa: F821
            )

            # Restore menu and image view for the previous directory and menu item
            _update_menu(items, top_level, prev_pos)  # noqa: F821
            pos = prev_pos  # noqa: F821
            continue  # Skip `yield`

        elif pos == -3:  # Implements "menu::Back" action
            if not top_level:  # noqa: F821
                break
            # Since the execution context is not exited, ensure pos
            # (and indirectly, prev_pos) always corresponds to a valid menu position.
            # By implication, this prevents an `IndexError` when coming out of
            # a directory that was entered from a context where prev_pos < -1
            pos = prev_pos  # noqa: F821

        else:
            entry, value = items[pos]
            if isinstance(value, Image):
                image_box._w.contents[1][0].contents[1] = (value, ("weight", 1, False))
                image_box.set_title(entry)
                view.original_widget = image_box
            else:  # Directory
                image_grid.contents[:] = [
                    (
                        urwid.AttrMap(LineSquare(val), "unfocused box", "focused box"),
                        image_grid.options(),
                    )
                    for _, val in scan_dir(
                        entry,
                        contents[entry],
                        # Return to Top-Level Directory, OR
                        # Return to the link's parent rather than the linked directory's
                        # parent
                        os.getcwd() if top_level or islink(entry) else "..",
                    )
                    if isinstance(val, Image)  # Exclude directories from the grid
                ]
                image_grid_box.set_title(f"{realpath(entry)}/")
                image_grid_box.base_widget.focus_position = 0
                image_grid_box.base_widget.render((1, 1))  # Force a re-render
                view.original_widget = image_grid_box
                Image._grid_cache.clear()

        prev_pos = pos
        pos = yield
        while pos == prev_pos:
            pos = yield
        info_bar.original_widget.set_text(f"pos={pos} {info_bar.original_widget.text}")

    # depth -= 1
    if not top_level:
        os.chdir(prev_dir)


def get_context():
    return _context


def get_prev_context():
    return _prev_context


def _process_input(key):
    info_bar.original_widget.set_text(f"{key!r} {info_bar.original_widget.text}")

    found = False
    if key in keys["global"]:
        keys["global"][key]()
        found = True
    else:
        found = keys[_context].get(key, lambda: False)() is None

    if key[0] == "mouse press":  # strings also support subscription
        # change context if the pane in focus changed.
        if _context in {"image", "image-grid"} and viewer.focus_position == 0:
            set_context("menu")
            displayer.send(menu.focus_position - 1)
        elif _context == "menu":
            if viewer.focus_position == 1:
                set_context(
                    "image" if view.original_widget is image_box else "image-grid"
                )
            else:  # Update image view
                displayer.send(menu.focus_position - 1)

    return bool(found)


def scan_dir(
    dir: str, contents: dict, prev_dir: str = ".."
) -> Generator[Tuple[str, Union[Image, Generator]], None, None]:
    """Scan _dir_ (and sub-directories, if '--recursive' is set) for readable images
    using a directory tree of the form produced by `check_dir(dir)`.

    Args:
        - dir: Path to directory to be scanned.
        - contents: Tree of directories containing readable images
            (as produced by `check_dir(dir)`).
        - prev_dir: Path to set as working directory after scannning _dir_
            (default:  parent directory of _dir_).

    Yields:
        - A `term_img.widgets.Image` instance for each image in _dir_.
        - A similar generator for sub-directories (if '--recursive' is set).

    - If '--hidden' is set, hidden (.*) images and subdirectories are considered.
    """
    os.chdir(dir)
    for entry in os.listdir():
        if entry.startswith(".") and not show_hidden:
            continue
        if isfile(entry):
            try:
                PIL.Image.open(entry)
            except PIL.UnidentifiedImageError:
                # Reporting will apply to every non-image file :(
                pass
            except Exception as e:
                print(
                    f"{realpath(entry)!r} could not be read: "
                    f"{type(e).__name__}: {e}"
                )
            else:
                yield entry, Image(TermImage.from_file(entry))
        elif recursive and entry in contents:
            if islink(entry):  # check_dir() already eliminates broken symlinks
                # Return to the link's parent rather than the linked directory's parent
                yield (
                    entry,
                    scan_dir(entry, contents[entry], os.getcwd()),
                )
            else:
                yield entry, scan_dir(entry, contents[entry])

    os.chdir(prev_dir)


def set_context(new_context):
    global _context, _prev_context

    _prev_context = _context
    _context = new_context
    _display_context_keys(new_context)


def _update_menu(
    items: Iterable[Tuple[str, Union[Image, Iterator]]],
    top_level: bool = False,
    pos: int = 0,
) -> None:
    global menu_list
    menu_list = items

    menu.body[:] = [
        urwid.Text(("inactive", ".."))
        if top_level
        else urwid.AttrMap(MenuEntry(".."), "default", "focused entry")
    ] + [
        urwid.AttrMap(
            MenuEntry(
                basename(entry) + "/" * isinstance(value, Generator),
                "left",
                "clip",
            ),
            "default",
            "focused entry",
        )
        for entry, value in items
    ]
    menu.focus_position = pos + 1


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


_context = "menu"  # To avoid a NameError the first time set_context() is called.
set_context("menu")
depth = -1
menu_list = []

palette = [
    ("default", "", "", "", "#ffffff", ""),
    ("inactive", "", "", "", "#7f7f7f", ""),
    ("white on black", "", "", "", "#ffffff", "#000000"),
    ("black on white", "", "", "", "#000000", "#ffffff"),
    ("mine", "", "", "", "#ff00ff", "#ffff00"),
    ("focused entry", "", "", "", "standout", ""),
    ("unfocused box", "", "", "", "#7f7f7f", ""),
    ("focused box", "", "", "", "#ffffff", ""),
    ("green fg", "", "", "", "#00ff00", ""),
    ("red on green", "", "", "", "#ff0000,bold", "#00ff00"),
    ("keys", "", "", "", "#ffffff", "#5588ff"),
    ("keys block", "", "", "", "#5588ff", ""),
    ("error", "", "", "", "", "#ff0000"),
]

loop = MyLoop(main, palette, unhandled_input=_process_input)
loop.screen.clear()
loop.screen.set_terminal_properties(2 ** 24)

# Placeholders; Set from `..tui.init()`
displayer = None
max_pixels = None
recursive = None
show_hidden = None

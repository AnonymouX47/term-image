"""Main UI"""

import logging as _logging
import os
from operator import mul
from os.path import abspath, basename, isfile, islink
from queue import Queue
from threading import Event
from typing import Dict, Generator, Iterable, List, Optional, Tuple, Union

import PIL
import urwid

from .. import logging, notify
from ..config import context_keys, expand_key
from ..image import ImageIterator, TermImage
from .keys import (
    disable_actions,
    display_context_keys,
    enable_actions,
    keys,
    menu_nav,
    no_globals,
    set_image_grid_actions,
    set_image_view_actions,
    set_menu_actions,
    set_menu_count,
)
from .render import grid_render_queue
from .widgets import (
    Image,
    LineSquare,
    MenuEntry,
    image_box,
    image_grid,
    image_grid_box,
    info_bar,
    menu,
    placeholder,
    view,
    viewer,
)


def animate_image(image: Image, forced_render: bool = False) -> None:
    """Changes frames of an animated image"""
    if NO_ANIMATION or (
        mul(*image._image._original_size) > MAX_PIXELS and not forced_render
    ):
        return

    def next_frame(*_) -> None:
        nonlocal last_alarm

        loop.remove_alarm(last_alarm)
        if image_box.original_widget is image and (
            not forced_render or image._force_render
        ):
            image._frame_changed = True
            last_alarm = loop.set_alarm_in(frame_duration, next_frame)
        else:
            # When you switch back and forth between an animated image and another
            # image rapidly, all within one frame duration and the other image ends up
            # as the current image, the last alarm from the first animation of the
            # image in question and the first alarm from the second animation both
            # meet the other image as the current one when they're triggered.
            # So, they both try to clean up but the second alarm one meets nothing
            # since the previous alarm had already cleaned up.
            try:
                image._animator.close()
                del (
                    image._animator,
                    image._frame,
                    image._frame_changed,
                    image._frame_size_hash,
                )
            except AttributeError:
                pass

            # The above issue shouldn't apply to forced renders since no new
            # animation is started until forced and that can't happen until the current
            # forced animation is over.
            # Going back to the image with the forced animation within one frame
            # duration simply continues the ongoing animation.
            #
            # Also, see "Forced render" section of `.widgets.Image.render()`.
            if forced_render:
                del image._force_render
                del image._forced_anim_size_hash

    frame_duration = FRAME_DURATION or image._image._frame_duration
    image._animator = ImageIterator(image._image, -1, f"1.1{image._alpha}")._animator

    # `Image.render()` checks for this. It has to be set here since `ImageIterator`
    # doesn't set it until the first `next()` is called.
    image._image._seek_position = 0

    # Only needs to be set once for an animated image, not per frame
    # See `Image.render()`
    if forced_render:
        image._force_render = True

    image._frame_changed = True
    last_alarm = loop.set_alarm_in(frame_duration, next_frame)


def display_images(
    dir: str,
    items: List[Tuple[str, Union[Image, type(...)]]],
    contents: Dict[str, Union[bool, Dict[str, Union[bool, dict]]]],
    prev_dir: str = "..",
    *,
    top_level: bool = False,
) -> Generator[None, int, bool]:
    """Displays images in _dir_ (and sub-directories, if '--recursive' is set)
    as yielded by ``scan_dir(dir)``.

    Args:
        - dir: Path to directory containing images.
        - items: An iterable of ``(entry, value)`` pairs, such as yielded by
          ``scan_dir(dir)`` i.e:

          - ``(str, Image)`` for images in *dir*, and
          - ``(str, Ellipsis)`` for sub-directories of *dir*

        - contents: Tree of directories containing readable images
          (such as returned by `check_dir(dir)`)
        - prev_dir: Path to set as working directory after displaying images in *dir*
          (default:  parent directory of *dir*)
        - top_level: Specifies if *dir* is the top level (For internal use only)

    Returns:
        The empty status of the (current) directory being exited i.e ``True`` if empty,
        otherwise ``False``.

    Receives:
        Via .send(), either:
          - a menu item position (-1 and above)
          - a flag denoting a certain action
    """
    global grid_list, grid_path, last_non_empty_grid_path

    os.chdir(dir)

    # For `.tui.keys.set_menu_actions()`, called by `update_menu()`
    menu_is_complete = top_level or grid_scan_done.is_set()
    menu_scan_done.set() if menu_is_complete else menu_scan_done.clear()

    update_menu(items, top_level)
    next_menu.put((items, contents, menu_is_complete))

    entry = prev_pos = value = None  # Silence linter's `F821`
    pos = 0 if top_level else -1

    while True:
        if pos == -1:  # Cursor on top menu item ("..")
            if top_level:
                if items:
                    # Ensure ".." is not selectable at top level
                    # Possible when "Home" action is invoked
                    pos = 0
                    menu.focus_position = 1
                    continue
                else:
                    set_context("global")
            grid_active.clear()  # Grid not in view
            image_box._w.contents[1][0].contents[1] = (
                placeholder,
                ("weight", 1, False),
            )
            image_box.original_widget = placeholder  # For image animation
            image_box.set_title("Image")
            view.original_widget = image_box

        elif pos == OPEN:  # Implements "menu::Open" action (for non-image entries)
            if prev_pos == -1:
                # prev_pos can never be -1 at top level (See `pos == -1` branch above),
                # and even if it could `pos == BACK` still guards against it.
                pos = BACK
                continue

            # Ensure menu scanning is halted before WD is changed to prevent
            # `FileNotFoundError`s
            if not menu_scan_done.is_set():
                menu_acknowledge.clear()
                menu_change.set()
                menu_acknowledge.wait()
                menu_change.clear()

            # Ensure grid scanning is halted to avoid updating `grid_list` which is
            # used as the next `menu_list` as is and to prevent `FileNotFoundError`s
            if not grid_scan_done.is_set():
                grid_acknowledge.clear()
                grid_active.clear()  # Grid not in view
                grid_acknowledge.wait()

            # To restore the menu on the way back
            menu_is_complete = menu_scan_done.is_set()

            logger.debug(f"Going into {abspath(entry)}/")
            empty = yield from display_images(
                entry,
                grid_list,
                contents[entry],
                # Return to Top-Level Directory, OR
                # to the link's parent instead of the linked directory's parent
                os.getcwd() if top_level or islink(entry) else "..",
            )
            # Menu change already signaled by the BACK action from the exited directory

            # For `.tui.keys.set_menu_actions()`, called by `update_menu()`
            menu_scan_done.set() if menu_is_complete else menu_scan_done.clear()

            if empty:  # All entries in the exited directory have been deleted
                del items[prev_pos]
                del contents[entry]
                pos = min(prev_pos, len(items) - 1)
                # Restore the menu and view pane for the previous (this) directory,
                # while removing the empty directory entry.
                update_menu(items, top_level, pos)
                logger.debug(f"Removed empty directory entry '{entry}/' from the menu")
                notify.notify(f"Removed empty directory entry '{entry}/' from the menu")
            else:
                # Restore the menu and view pane for the previous (this) directory
                update_menu(items, top_level, prev_pos)
                pos = prev_pos

            next_menu.put((items, contents, menu_is_complete))
            continue  # Skip `yield`

        elif pos == BACK:  # Implements "menu::Back" action
            if not top_level:
                # Ensure menu scanning is halted before WD is changed to prevent
                # `FileNotFoundError`s
                if not menu_scan_done.is_set():
                    menu_acknowledge.clear()
                    menu_change.set()
                    menu_acknowledge.wait()
                    menu_change.clear()

                # Ensure grid scanning is halted before WD is changed to prevent
                # `FileNotFoundError`s
                if grid_active.is_set() and not grid_scan_done.is_set():
                    grid_acknowledge.clear()
                    grid_active.clear()  # Grid not in view
                    grid_acknowledge.wait()

                break

            # Since the execution context is not exited at the top-level, ensure pos
            # (and indirectly, prev_pos) always corresponds to a valid menu position.
            # By implication, this prevents an `IndexError` or rendering the wrong image
            # when coming out of a directory that was entered when prev_pos < -1.
            pos = prev_pos

        elif pos == DELETE:
            del items[prev_pos]
            pos = min(prev_pos, len(items) - 1)
            update_menu(items, top_level, pos)
            yield  # Displaying next image immediately will mess up confirmation overlay
            if DEBUG:
                info_bar.set_text(f"delete_pos={pos} {info_bar.text}")
            continue

        else:
            entry, value = items[pos]
            if isinstance(value, Image):
                grid_active.clear()  # Grid not in view
                image_box._w.contents[1][0].contents[1] = (value, ("weight", 1, False))
                image_box.set_title(entry)
                view.original_widget = image_box
                image_box.original_widget = value  # For image animation
                if value._image._is_animated:
                    animate_image(value)
            else:  # Directory
                grid_acknowledge.clear()
                grid_active.set()  # Grid is in view

                next_grid.put((entry, contents[entry]))
                # No need to wait for acknowledgement since this is a new list instance
                grid_list = []
                # Absolute paths work fine with symlinked images and directories,
                # as opposed to real paths, especially in path comparisons
                # e.g in `.tui.render.manage_grid_renders()`.
                grid_path = abspath(entry)

                if contents[entry]["/"] and grid_path != last_non_empty_grid_path:
                    grid_render_queue.put(None)  # Mark the start of a new grid
                    grid_change.set()
                    # Wait till GridRenderManager clears the cache
                    while grid_change.is_set():
                        pass
                    last_non_empty_grid_path = grid_path
                image_grid_box.set_title(grid_path + "/")
                view.original_widget = image_grid_box
                image_grid_box.base_widget._invalidate()

                if contents[entry]["/"]:
                    enable_actions("menu", "Switch Pane")
                else:
                    disable_actions("menu", "Switch Pane")

                # Wait for GridScanner to clear grid contents.
                # Not waiting could result in an `IndexError` raised by
                # `GridFlow.focus_position` in `GridFlow.generate_display_widget()`
                # when it meets the grid non-empty but it's then cleared by
                # GridScanner in the course of generating the display widget.
                grid_acknowledge.wait()

        prev_pos = pos
        pos = yield
        while pos == prev_pos:
            pos = yield
        if DEBUG:
            info_bar.set_text(f"pos={pos} {info_bar.text}")

    if not top_level:
        logger.debug(f"Going back to {abspath(prev_dir)}/")
        os.chdir(prev_dir)

    return menu_scan_done.is_set() and not items


def get_context() -> None:
    """Returns the current context"""
    return _context


def get_prev_context(n: int = 1) -> None:
    """Return the nth previous context (1 <= n <= 3)"""
    return _prev_contexts[n - 1]


def process_input(key: str) -> bool:
    if DEBUG:
        info_bar.set_text(f"{key!r} {info_bar.text}")

    found = False
    if key in keys["global"]:
        if (
            _context not in no_globals
            or _context == "global"
            or key in {"resized", expand_key[0]}
        ):
            func, state = keys["global"][key]
            func() if state else print("\a", end="", flush=True)
            found = True

    elif key[0] == "mouse press":  # strings also support subscription
        # change context if the pane in focus changed.
        if _context in {"image", "image-grid"} and viewer.focus_position == 0:
            set_context("menu")
            menu_nav()
            found = True
        elif _context == "menu":
            if viewer.focus_position == 1:
                if not context_keys["menu"]["Switch Pane"][4]:
                    # Set focus back to the menu if "menu::Switch Pane" is disabled
                    viewer.focus_position = 0
                else:
                    if view.original_widget is image_box:
                        set_context("image")
                        set_image_view_actions()
                    else:
                        set_context("image-grid")
                        set_image_grid_actions()
            else:  # Update image view
                menu_nav()
            found = True

    else:
        func, state = keys[_context].get(key, (None, None))
        if state:
            func()
        elif state is False:
            print("\a", end="", flush=True)
        found = state is not None

    return bool(found)


def scan_dir(
    dir: str,
    contents: Dict[str, Union[bool, Dict[str, Union[bool, dict]]]],
    *,
    notify_errors: bool = False,
) -> Generator[Tuple[str, Union[Image, type(...)]], None, int]:
    """Scans *dir* (and sub-directories, if '--recursive' was set) for readable images
    using a directory tree of the form produced by ``.cli.check_dir(dir)``.

    Args:
        - dir: Path to directory to be scanned.
        - contents: Tree of directories containing readable images
          (as produced by ``.cli.check_dir(dir)``).
        - notify_errors: Determines if a notification showing the number of unreadable
          files will be displayed.

    Yields:
        A tuple ``(entry, value)``, where *entry* is ``str`` (the item name)
        and *value* is:

          - ``.tui.widgets.Image``, for images in *dir*, and
          - `Ellipsis` for sub-directories of *dir* (if '--recursive' is set).

    Returns:
        The number of unreadable files in *dir*.

    - If '--all' was set, hidden (.*) images and subdirectories are included.
    - Items are grouped into images and directories, sorted lexicographically and
      case-insensitively. Any preceding '.'s (dots) are ignored when sorting.
    - If a dotted entry has the same main-name as another entry, the dotted one comes
      first.
    """
    entries = os.listdir(dir)
    entries.sort(
        key=sort_key_lexi,
    )
    errors = 0
    full_dir = dir + os.sep
    for entry in entries:
        result = scan_dir_entry(entry, contents, full_dir + entry)
        if result == HIDDEN:
            continue
        if result == UNREADABLE:
            errors += 1
        if result == IMAGE:
            yield entry, Image(TermImage.from_file(full_dir + entry))
        elif result == DIR:
            yield entry, ...
    if notify_errors and errors:
        notify.notify(
            f"{errors} file(s) could not be read in {abspath(dir)!r}! Check the logs.",
            level=notify.ERROR,
        )

    return errors


def scan_dir_entry(
    entry: str,
    contents: Dict[str, Union[bool, Dict[str, Union[bool, dict]]]],
    entry_path: Optional[str] = None,
) -> int:
    """Scans a single directory entry and returns a flag indicating its kind."""
    if entry.startswith(".") and not SHOW_HIDDEN:
        return HIDDEN
    if isfile(entry_path or entry):
        if not contents["/"]:
            return -1
        try:
            PIL.Image.open(entry_path or entry)
        except PIL.UnidentifiedImageError:
            # Reporting will apply to every non-image file :(
            pass
        except Exception:
            logging.log_exception(
                f"{abspath(entry_path or entry)!r} could not be read", logger
            )
            return UNREADABLE
        else:
            return IMAGE
    if RECURSIVE and entry in contents:
        # `.cli.check_dir()` already eliminates bad symlinks
        return DIR

    return -1


def scan_dir_grid() -> None:
    """Scans a given directory (and it's sub-directories, if '--recursive'
    was set) for readable images using a directory tree of the form produced by
    ``.cli.check_dir(dir)``.

    This is designed to be executed in a separate thread, while certain grid details
    are passed in using the ``next_grid`` queue.

    For each valid entry, a tuple ``(entry, value)``, like in ``scan_dir``, is appended
    to ``.tui.main.grid_list`` and adds a corresponding entry to the grid widget
    (for image entries only), then updates the screen.

    Grouping and sorting are the same as for ``scan_dir()``.
    """
    grid_contents = image_grid.contents
    while True:
        dir, contents = next_grid.get()
        image_grid.contents.clear()
        grid_acknowledge.set()  # Cleared grid contents
        grid_scan_done.clear()
        notify.start_loading()

        entries = os.listdir(dir)
        entries.sort(key=lambda x: sort_key_lexi(x, os.path.join(dir, x)))

        for entry in entries:
            entry_path = os.path.join(dir, entry)
            result = scan_dir_entry(entry, contents, entry_path)
            if result == HIDDEN:
                continue
            if result == IMAGE:
                val = Image(TermImage.from_file(entry_path))
                grid_list.append((entry, val))
                grid_contents.append(
                    (
                        urwid.AttrMap(LineSquare(val), "unfocused box", "focused box"),
                        image_grid.options(),
                    )
                )
                image_grid_box.base_widget._invalidate()
                update_screen()
            elif result == DIR:
                grid_list.append((entry, ...))

            if not next_grid.empty():
                break
            if not grid_active.is_set():
                grid_acknowledge.set()
                break
        else:
            grid_scan_done.set()
            # There is a possibility that `grid_scan_done` is read as "cleared"
            # in-between the end of the last iteration an here :)
            if not grid_active.is_set():
                grid_acknowledge.set()
        notify.stop_loading()


def scan_dir_menu() -> None:
    """Scans the current working directory (and it's sub-directories, if '--recursive'
    was set) for readable images using a directory tree of the form produced by
    ``.cli.check_dir(dir)``.

    This is designed to be executed in a separate thread, while certain menu details
    are passed in using the ``next_menu`` queue.

    For each valid entry, a tuple ``(entry, value)``, like in ``scan_dir``, is appended
    to ``.tui.main.menu_list`` and adds a corresponding entry to the menu widget,
    then updates the screen.

    Grouping and sorting are the same as for ``scan_dir()``.
    """
    menu_body = menu.body
    while True:
        items, contents, menu_is_complete = next_menu.get()
        if menu_is_complete:
            continue
        notify.start_loading()

        entries = os.listdir()
        entries.sort(key=sort_key_lexi)
        entries = iter(entries)
        last_entry = items[-1][0] if items else None
        if last_entry:
            for entry in entries:
                if entry == last_entry:
                    break

        errors = 0
        for entry in entries:
            result = scan_dir_entry(entry, contents)
            if result == HIDDEN:
                continue
            if result == UNREADABLE:
                errors += 1
            if result == IMAGE:
                items.append((entry, Image(TermImage.from_file(entry))))
                menu_body.append(
                    urwid.AttrMap(
                        MenuEntry(entry, "left", "clip"),
                        "default",
                        "focused entry",
                    )
                )
                set_menu_count()
                update_screen()
            elif result == DIR:
                items.append((entry, ...))
                menu_body.append(
                    urwid.AttrMap(
                        MenuEntry(entry + "/", "left", "clip"),
                        "default",
                        "focused entry",
                    )
                )
                set_menu_count()
                update_screen()

            if menu_change.is_set():
                menu_acknowledge.set()
                break
        else:
            menu_scan_done.set()
            # There is a possibility that `menu_scan_done` is read as "cleared"
            # in-between the end of the last iteration an here :)
            if menu_change.is_set():
                menu_acknowledge.set()
            if errors:
                notify.notify(
                    f"{errors} file(s) could not be read in {os.getcwd()!r}! "
                    "Check the logs.",
                    level=notify.ERROR,
                )
        notify.stop_loading()


def set_context(new_context) -> None:
    """Sets the current context and updates the Key/Action bar"""
    global _context

    if DEBUG:
        info_bar.set_text(f"{_prev_contexts} {info_bar.text}")
    _prev_contexts[1:] = _prev_contexts[:2]  # Right-shift older contexts
    _prev_contexts[0] = _context
    _context = new_context
    display_context_keys(new_context)
    if DEBUG:
        info_bar.set_text(f"{new_context!r} {_prev_contexts} {info_bar.text}")


def set_prev_context(n: int = 1) -> None:
    """Set the nth previous context as the current context (1 <= n <= 3)"""
    global _context

    if DEBUG:
        info_bar.set_text(f"{_prev_contexts} {info_bar.text}")
    _context = _prev_contexts[n - 1]
    display_context_keys(_context)
    _prev_contexts[:n] = []
    _prev_contexts.extend(["menu"] * n)
    if DEBUG:
        info_bar.set_text(f"{_prev_contexts} {info_bar.text}")


def sort_key_lexi(name, path=None):
    """Lexicographic sort key function.

    Compatible with ``list.sort()`` and ``sorted()``.
    """
    # The first part groups into files and directories
    # The seconds sorts within the group
    # The third, between hidden and non-hidden of the same name
    #   - '\0' makes the key for the non-hidden longer without affecting it's order
    #     relative to other entries.
    return (
        "\0" + name.lstrip(".").casefold() + "\0" * (not name.startswith("."))
        if isfile(path or name)
        else "\1" + name.lstrip(".").casefold() + "\0" * (not name.startswith("."))
    )


def update_menu(
    items: Iterable[Tuple[str, Union[Image, Generator]]],
    top_level: bool = False,
    pos: int = -1,
) -> None:
    global menu_list, at_top_level
    menu_list, at_top_level = items, top_level

    menu.body[:] = [
        urwid.Text(("inactive", ".."))
        if top_level
        else urwid.AttrMap(MenuEntry(".."), "default", "focused entry")
    ] + [
        urwid.AttrMap(
            MenuEntry(
                (basename(entry) if at_top_level else entry) + "/" * (value is ...),
                "left",
                "clip",
            ),
            "default",
            "focused entry",
        )
        for entry, value in items
    ]
    menu.focus_position = pos + 1 + (at_top_level and pos == -1)
    set_menu_actions()
    set_menu_count()


def update_screen():
    """Triggers a screeen redraw.

    Meant to be called from threads other than the thread in which the MainLoop is
    running.
    """
    if not (interrupted.is_set() or quitting.is_set()):
        os.write(update_pipe, b" ")


logger = _logging.getLogger(__name__)
quitting = Event()

# For grid scanning/display
grid_acknowledge = Event()
grid_active = Event()
grid_change = Event()
grid_list = None
grid_path = None
grid_scan_done = Event()
last_non_empty_grid_path = None
next_grid = Queue(1)

# For menu scanning/listing
menu_acknowledge = Event()
menu_change = Event()
menu_scan_done = Event()
next_menu = Queue(1)

# For Context Management
_prev_contexts = ["menu"] * 3
_context = "menu"  # To avoid a NameError the first time set_context() is called.

# FLAGS for `display_images()`
OPEN = -2
BACK = -3
DELETE = -4

# FLAGS for `scan_dir*()`
HIDDEN = 0
UNREADABLE = 1
IMAGE = 2
DIR = 3

# Placeholders

# # Set by `update_menu()`
menu_list = None
at_top_level = None

# # Set from `.__main__.main()`
interrupted = None

# # Set from `..tui.init()`
displayer = None
loop = None
update_pipe = None

# # # Corresponsing to command-line args
DEBUG = None
FRAME_DURATION = None
GRID_RENDERERS = None
MAX_PIXELS = None
NO_ANIMATION = None
RECURSIVE = None
SHOW_HIDDEN = None

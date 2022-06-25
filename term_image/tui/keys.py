"""Definitions of key functions"""

from __future__ import annotations

import logging as _logging
import os
from os.path import abspath, basename
from time import sleep
from types import FunctionType
from typing import Tuple

import urwid

from .. import __version__, logging
from ..config import context_keys, expand_key
from ..utils import get_terminal_size
from . import main
from .widgets import (
    ImageCanvas,
    bottom_bar,
    confirmation,
    confirmation_overlay,
    expand,
    image_box,
    image_grid,
    image_grid_box,
    key_bar,
    main as main_widget,
    menu,
    menu_box,
    overlay,
    pile,
    placeholder,
    view,
    viewer,
)

# Action Status Modification


def disable_actions(context: str, *actions: str) -> None:
    keyset = context_keys[context]
    for action in actions:
        keyset[action][4] = False
        keys[context][keyset[action][0]][1] = False
        display_context_keys(context)


def enable_actions(context: str, *actions: str) -> None:
    keyset = context_keys[context]
    for action in actions:
        keyset[action][4] = True
        keys[context][keyset[action][0]][1] = True
        display_context_keys(context)


def hide_actions(context: str, *actions: str) -> None:
    keyset = context_keys[context]
    for action in actions:
        keyset[action][3] = False
        display_context_keys(context)
    disable_actions(context, *actions)


def show_actions(context: str, *actions: str) -> None:
    keyset = context_keys[context]
    for action in actions:
        keyset[action][3] = True
        display_context_keys(context)
    enable_actions(context, *actions)


# Main


def display_context_help(context: str) -> None:
    """Displays the help menu for a particular context, showing all visible actions
    and their descriptions.
    """
    global _prev_view_widget

    actions = (
        *context_keys[context].items(),
        *(() if context in no_globals else context_keys["global"].items()),
    )

    separator = (1, urwid.Filler(urwid.Text("\u2502" * 3)))
    contents = [
        (
            3,
            urwid.Columns(
                [
                    (
                        "weight",
                        3,
                        urwid.Filler(
                            urwid.Text(("default bold", f"{action}"), "center")
                        ),
                    ),
                    separator,
                    (
                        "weight",
                        2,
                        urwid.Filler(
                            urwid.Text(("default bold", f"{symbol} ({key})"), "center")
                        ),
                    ),
                    separator,
                    (
                        "weight",
                        5,
                        urwid.Filler(
                            urwid.Text(("default bold", f"{description}"), "center")
                        ),
                    ),
                ],
                min_width=5,
            ),
        )
        for action, (key, symbol, description, visible, _) in actions
        if visible
    ]

    line = urwid.SolidFill("\u2500")
    divider = urwid.Columns(
        [
            ("weight", 3, line),
            (1, urwid.Filler(urwid.Text("\u253c"))),
            ("weight", 2, line),
            (1, urwid.Filler(urwid.Text("\u253c"))),
            ("weight", 5, line),
        ],
        min_width=5,
    )
    for index in range(1, (len(contents) - 1) * 2, 2):
        contents.insert(index, (1, divider))

    contents.insert(
        0,
        (
            1,
            urwid.Columns(
                [
                    ("weight", 3, line),
                    (1, urwid.Filler(urwid.Text("\u252c"))),
                    ("weight", 2, line),
                    (1, urwid.Filler(urwid.Text("\u252c"))),
                    ("weight", 5, line),
                ],
                min_width=5,
            ),
        ),
    )

    contents.extend(
        [
            (
                1,
                urwid.Columns(
                    [
                        ("weight", 3, line),
                        (1, urwid.Filler(urwid.Text("\u2534"))),
                        ("weight", 2, line),
                        (1, urwid.Filler(urwid.Text("\u2534"))),
                        ("weight", 5, line),
                    ],
                    min_width=5,
                ),
            ),
            (
                3,
                urwid.LineBox(
                    urwid.Filler(
                        urwid.Text(("default bold", f"Version {__version__}"), "center")
                    )
                ),
            ),
        ]
    )

    overlay.top_w.original_widget.body[0] = urwid.Pile(contents)
    overlay.bottom_w = view if main.get_context() == "full-image" else pile
    main_widget.contents[0] = (overlay, ("weight", 1))
    main.set_context("overlay")

    # `Image` widgets don't support overlay.
    # Always reset by or "overlay::Close"
    _prev_view_widget = view.original_widget
    view.original_widget = urwid.LineBox(
        placeholder, _prev_view_widget.title_widget.text.strip(" "), "left"
    )


def display_context_keys(context: str) -> None:
    """Updates the Key/Action bar with the actions in the given context.

    Includes "global" actions for all contexts except those in `no_globals`.
    """
    actions = (
        *context_keys[context].items(),
        *(() if context in no_globals else context_keys["global"].items()),
    )

    # The underscores and blocks (U+2588) are to prevent wrapping amidst keys
    key_bar.original_widget.set_text(
        [
            [
                ("key" if enabled else "disabled key", action.replace(" ", "\u2800")),
                ("key", "\u2800"),
                ("key" if enabled else "disabled key", f"[{symbol}]"),
                " ",
            ]
            for action, (_, symbol, _, visible, enabled) in actions
            if visible
        ]
    )
    resize()


def register_key(*args: Tuple[str, str]) -> FunctionType:
    """Returns a decorator to register a function to some context actions

    Args: `(context, action)` tuple(s), each specifying an _action_ and it's _context_.

    Returns: A decorator that registers a function to some context actions.

    Each _context_ and _action_ must be valid.
    If no argument is passed, the wrapper simply does nothing.
    """

    def register(func: FunctionType) -> None:
        """Register _func_ to the key corresponding to each `(context, action)` pair
        recieved by the call to `register_key()` that returns it
        """
        for context, action in args:
            # All actions are enabled by default
            keys[context][context_keys[context][action][0]] = [func, True]

        return func

    return register


def set_confirmation(
    msg: str,
    bottom_widget: urwid.widget,
    confirm: FunctionType,
    cancel: FunctionType,
    confirm_args: tuple = (),
    cancel_args: tuple = (),
) -> None:
    """Setup a confirmation dialog

    Args:
      - msg: The message to be displayed in the dialog.
      - bottom_widget: The widget on which the confirmation dialog will be overlayed.
      - confirm: A function to be called for the "Confirm" action of the
        confirmation context.
      - cancel: A function to be called for the "Cancel" action of the
        confirmation context.
      - confirm_args: Optional positional arguments to be passed to _confirm_.
      - cancel_args: Optional positional arguments to be passed to _cancel_.

    This function must be called by any context action using the confirmation dialog.
    """
    global _confirm, _cancel, _prev_view_widget

    _confirm = (confirm, confirm_args)
    _cancel = (cancel, cancel_args)
    confirmation.set_text(msg)
    main.set_context("confirmation")

    # `Image` widgets don't support overlay.
    # Always reset by or "confirmation::Cancel"
    # but _confirm()_ must reset `view.original_widget` on it's own.
    _prev_view_widget = view.original_widget
    view.original_widget = urwid.LineBox(
        placeholder, _prev_view_widget.title_widget.text.strip(" "), "left"
    )

    confirmation_overlay.bottom_w = bottom_widget
    main_widget.contents[0] = (confirmation_overlay, ("weight", 1))

    main.ImageClass._clear_images()


# Context Actions

# {<context>: [<func>, <state>], ...}
keys = {context: {} for context in context_keys}


# global
@register_key(("global", "Quit"))
def quit():
    main.quitting.set()
    raise urwid.ExitMainLoop()


@register_key(("global", "Key Bar"))
def expand_collapse_keys():
    if expand._ti_shown:
        if key_bar._ti_collapsed and key_bar_rows() > 1:
            expand.original_widget.set_text(f"\u25BC [{expand_key[1]}]")
            main_widget.contents[-1] = (
                bottom_bar,
                ("given", key_bar_rows()),
            )
            key_bar._ti_collapsed = False
            main.ImageClass._clear_images() and ImageCanvas.change()
        elif not key_bar._ti_collapsed:
            expand.original_widget.set_text(f"\u25B2 [{expand_key[1]}]")
            main_widget.contents[-1] = (bottom_bar, ("given", 1))
            key_bar._ti_collapsed = True
            main.ImageClass._clear_images() and ImageCanvas.change()


@register_key(("global", "Help"))
def help():
    display_context_help(main.get_context())
    main.ImageClass._clear_images()


def resize():
    cols = get_terminal_size()[0]
    rows = key_bar.original_widget.rows((cols,))
    if expand._ti_shown:
        if rows == 1:
            bottom_bar.contents.pop()
            expand._ti_shown = False
    elif rows > 1:
        bottom_bar.contents.append(
            (expand, ("given", len(expand.original_widget.text), False))
        )
        expand._ti_shown = True

    if not key_bar._ti_collapsed:
        new_rows = key_bar_rows()
        if main_widget.contents[-1][1][1] != new_rows:
            main.ImageClass._clear_images()
        main_widget.contents[-1] = (
            bottom_bar,
            ("given", new_rows),
        )


def key_bar_rows():
    # Consider columns occupied by the expand key and the divider
    cols = (
        get_terminal_size()[0]
        - (len(expand.original_widget.text) + 2) * expand._ti_shown
    )
    return key_bar.original_widget.rows((cols,))


keys["global"].update({"resized": [resize, True]})


# menu
@register_key(
    ("menu", "Prev"),
    ("menu", "Next"),
    ("menu", "Page Up"),
    ("menu", "Page Down"),
    ("menu", "Top"),
    ("menu", "Bottom"),
)
def menu_nav():
    main.displayer.send(menu.focus_position - 1)
    if not main.at_top_level or main.menu_list:
        set_menu_actions()
        set_menu_count()


def set_menu_actions():
    pos = menu.focus_position - 1
    if pos == -1:
        disable_actions("menu", "Switch Pane", "Delete", "Prev", "Page Up", "Top")
    elif main.menu_list[pos][1] is ...:
        disable_actions("menu", "Delete")
        enable_actions("menu", "Prev", "Page Up", "Top")
    else:
        enable_actions("menu", "Switch Pane", "Delete", "Prev", "Page Up", "Top")

    if main.at_top_level:
        if pos == 0:
            # "Top" is not disabled to ensure ".." is never selected
            # See `pos == -1` in `.main.display_images()`
            disable_actions("menu", "Prev", "Page Up")
        disable_actions("menu", "Back")
    else:
        enable_actions("menu", "Back")

    if main.menu_scan_done.is_set() and pos == len(main.menu_list) - 1:
        disable_actions("menu", "Next", "Page Down", "Bottom")
    else:
        enable_actions("menu", "Next", "Page Down", "Bottom")


def set_menu_count():
    length = len(main.menu_list) if main.menu_scan_done.is_set() else "..."
    menu_box.set_title(f"{menu.focus_position} of {length}")


@register_key(("menu", "Open"))
def open():
    if menu.focus_position == 0 or main.menu_list[menu.focus_position - 1][1] is ...:
        main.displayer.send(main.OPEN)
    else:
        main.set_context("full-image")
        main_widget.contents[0] = (view, ("weight", 1))
        set_image_view_actions()

    main.ImageClass._clear_images()


@register_key(("menu", "Back"))
def back():
    main.displayer.send(main.BACK)
    main.ImageClass._clear_images()


# image
@register_key(("image", "Maximize"))
def maximize():
    main.set_context("full-image")
    main_widget.contents[0] = (view, ("weight", 1))
    set_image_view_actions()

    main.ImageClass._clear_images()


# image-grid
@register_key(("image-grid", "Size-"))
def cell_width_dec():
    if image_grid.cell_width > 30:
        image_grid.cell_width -= 2
        main.grid_render_queue.put(None)  # Mark the start of a new grid
        main.grid_change.set()
        # Wait till GridRenderManager clears the cache
        while main.grid_change.is_set():
            pass
        main.ImageClass._clear_images()


@register_key(("image-grid", "Size+"))
def cell_width_inc():
    if image_grid.cell_width < 50:
        image_grid.cell_width += 2
        main.grid_render_queue.put(None)  # Mark the start of a new grid
        main.grid_change.set()
        # Wait till GridRenderManager clears the cache
        while main.grid_change.is_set():
            pass
        main.ImageClass._clear_images()


@register_key(("image-grid", "Open"))
def maximize_cell():
    main.set_context("full-grid-image")
    row = image_grid_box.base_widget.focus
    image_w = (
        row.focus
        if isinstance(row, urwid.Columns)  # when maxcol >= cell_width
        else row
    ).original_widget.original_widget  # The Image is in a LineSquare in an AttrMap

    image_box._w.contents[1][0].contents[1] = (image_w, ("weight", 1, True))
    image_box.set_title(basename(image_w._ti_image._source))
    main_widget.contents[0] = (image_box, ("weight", 1))

    image_box.original_widget = image_w  # For image animation
    if image_w._ti_image._is_animated:
        main.animate_image(image_w)

    main.ImageClass._clear_images()


def set_image_grid_actions():
    # The grid for a non-empty directory might be empty at the start of scanning
    if image_grid.contents:
        enable_actions("image-grid", "Open", "Size-", "Size+")
    else:
        disable_actions("image-grid", "Open", "Size-", "Size+")


# full-grid-image
@register_key(("full-grid-image", "Force Render"))
def force_render_maximized_cell():
    # Will re-render immediately after processing input, since caching has been disabled
    # for `Image` widgets.
    image_w = image_box._w.contents[1][0].contents[1][0]
    if image_w._ti_image._is_animated:
        main.animate_image(image_w, True)
    else:
        image_w._ti_force_render = True


# full-image, full-grid-image
@register_key(("full-image", "Restore"), ("full-grid-image", "Back"))
def restore():
    # For image animation
    if (
        main.get_context() == "full-grid-image"
        and image_box.original_widget._ti_image._is_animated
    ):
        image_box.original_widget = placeholder

    main.set_prev_context()
    main_widget.contents[0] = (pile, ("weight", 1))
    if main.get_context() == "menu":
        set_menu_actions()
    elif main.get_context() == "image":
        set_image_view_actions()

    main.ImageClass._clear_images()


# image, full-image
@register_key(("image", "Prev"), ("full-image", "Prev"))
def prev_image():
    if (
        menu.focus_position > 1
        # Don't scroll through directory items in image views
        and main.menu_list[menu.focus_position - 2][1] is not ...  # Previous item
    ):
        menu.focus_position -= 1
        main.displayer.send(menu.focus_position - 1)

    set_image_view_actions()
    set_menu_count()


@register_key(("image", "Next"), ("full-image", "Next"))
def next_image():
    # `menu_list` is one item less than `menu` (at it's beginning), hence no `len - 1`
    if menu.focus_position < len(main.menu_list):
        menu.focus_position += 1
        main.displayer.send(menu.focus_position - 1)

    set_image_view_actions()
    set_menu_count()


@register_key(("image", "Force Render"), ("full-image", "Force Render"))
def force_render():
    # Will re-render immediately after processing input, since caching has been disabled
    # for `Image` widgets.
    image_w = main.menu_list[menu.focus_position - 1][1]
    if image_w._ti_image._is_animated:
        main.animate_image(image_w, True)
    else:
        image_w._ti_force_render = True


def set_image_view_actions(context: str = None):
    context = context or main.get_context()
    if (
        menu.focus_position < 2
        # Previous item is a directory
        or main.menu_list[menu.focus_position - 2][1] is ...
    ):
        disable_actions(context, "Prev")
    else:
        enable_actions(context, "Prev")

    if (
        # Last item
        main.menu_scan_done.is_set()
        and menu.focus_position == len(main.menu_list)
    ):
        disable_actions(context, "Next")
    else:
        enable_actions(context, "Next")


# menu, image, full-image
@register_key(
    ("menu", "Delete"),
    ("image", "Delete"),
    ("full-image", "Delete"),
)
def delete():
    entry = main.menu_list[menu.focus_position - 1][0]
    set_confirmation(
        ("warning", "Permanently delete this image?"),
        view if main.get_context() == "full-image" else pile,
        _confirm_delete,
        _cancel_delete,
        (entry,),
    )


def _confirm_delete(entry):
    try:
        os.remove(entry)
    except OSError:
        successful = False
        logging.log_exception(f"Unable to delete {abspath(entry)!r}", logger)
        confirmation.set_text(("warning", "Unable to delete! Check the logs for info."))
    else:
        successful = True
        main.displayer.send(main.DELETE)
        confirmation.set_text(f"Successfully deleted {abspath(entry)}")
        confirmation.set_text(("green fg", "Successfully deleted!"))
    main.loop.draw_screen()
    sleep(1)

    if successful:
        next(main.displayer)  # Render next image view
        if not main.menu_list or main.menu_list[menu.focus_position - 1][1] is ...:
            # All menu entries have been deleted OR selected menu item is a directory
            main_widget.contents[0] = (pile, ("weight", 1))
            viewer.focus_position = 0
            # "confirmation:Confirm" calls `set_prev_context()`
            main._prev_contexts[0] = (
                "global" if main.at_top_level and not main.menu_list else "menu"
            )
        else:
            _cancel_delete()
    else:
        view.original_widget = _prev_view_widget
        _cancel_delete()


def _cancel_delete():
    main_widget.contents[0] = (
        view if main.get_prev_context() == "full-image" else pile,
        ("weight", 1),
    )
    if main.get_prev_context() in {"image", "full-image"}:
        set_image_view_actions(main.get_prev_context())


# menu, image, image-grid
@register_key(
    ("menu", "Switch Pane"),
    ("image", "Switch Pane"),
    ("image-grid", "Switch Pane"),
)
def switch_pane():
    if main.get_context() != "menu":
        main.set_context("menu")
        viewer.focus_position = 0
        set_menu_actions()
    else:
        viewer.focus_position = 1
        if view.original_widget is image_box:
            main.set_context("image")
            set_image_view_actions()
        else:
            main.set_context("image-grid")
            set_image_grid_actions()


# confirmation
@register_key(("confirmation", "Confirm"))
def confirm():
    # `_confirm()` must [re]set `view.original_widget`
    _confirm[0](*_confirm[1])
    main.set_prev_context()


@register_key(("confirmation", "Cancel"))
def cancel():
    _cancel[0](*_cancel[1])
    view.original_widget = _prev_view_widget
    main.set_prev_context()


# overlay
@register_key(("overlay", "Close"))
def close():
    main_widget.contents[0] = (
        view if main.get_prev_context() == "full-image" else pile,
        ("weight", 1),
    )
    view.original_widget = _prev_view_widget
    main.set_prev_context()


logger = _logging.getLogger(__name__)
no_globals = {"global", "confirmation", "full-grid-image", "overlay"}
key_bar._ti_collapsed = True
expand._ti_shown = True

# The annotations below are put in comments for compatibility with Python 3.7
# as it doesn't allow names declared as `global` within functions to be annotated.

# Use in the "confirmation" context. Set by `set_confirmation()`
_confirm = None  #: Optional[Tuple[FunctionType, Tuple[Any]]]
_cancel = None  #: Optional[Tuple[FunctionType, Tuple[Any]]]

# Used for overlays
_prev_view_widget = None  #: Optional[urwid.Widget]

"""Definitions of key functions"""

import logging as _logging
import os
from os.path import abspath, basename
from shutil import get_terminal_size
from time import sleep
from types import FunctionType, GeneratorType
from typing import Tuple

import urwid

from .config import context_keys, expand_key
from .widgets import (
    bottom_bar,
    confirmation,
    confirmation_overlay,
    Image,
    image_box,
    image_grid,
    image_grid_box,
    key_bar,
    main as main_widget,
    menu,
    expand,
    pile,
    _placeholder,
    view,
    viewer,
)
from . import main
from .. import logging

# Action Status Modification


def disable_actions(context: str, *actions: str):
    keyset = context_keys[context]
    for action in actions:
        keyset[action][4] = False
        keys[context][keyset[action][0]][1] = False
        display_context_keys(context)


def enable_actions(context: str, *actions: str):
    keyset = context_keys[context]
    for action in actions:
        keyset[action][4] = True
        keys[context][keyset[action][0]][1] = True
        display_context_keys(context)


def hide_actions(context: str, *actions: str):
    keyset = context_keys[context]
    for action in actions:
        keyset[action][3] = False
        display_context_keys(context)
    disable_actions(context, *actions)


def show_actions(context: str, *actions: str):
    keyset = context_keys[context]
    for action in actions:
        keyset[action][3] = True
        display_context_keys(context)
    enable_actions(context, *actions)


# Main


def display_context_keys(context: str) -> None:
    actions = (
        *context_keys[context].items(),
        *(() if context in no_globals else context_keys["global"].items()),
    )

    # The underscores and blocks (U+2588) are to prevent wrapping amidst keys
    key_bar.original_widget.set_text(
        [
            [
                ("key" if enabled else "disabled key", f"{action.replace(' ', '_')}"),
                ("key block", "\u2588"),
                ("key" if enabled else "disabled key", f"[{symbol}]"),
                " ",
            ]
            for action, (_, symbol, _, visible, enabled) in actions
            if visible
        ]
    )
    resize()


def _register_key(*args: Tuple[str, str]) -> FunctionType:
    """Decorate a function to register it to some context actions

    Args: `(context, action)` tuple(s), each specifying an _action_ and it's _context_.

    Returns: a wrapper that registers a function to some context actions.

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

    for context, action in args:
        if context not in context_keys:
            raise ValueError(f"Unknown context {context!r}")
        if action not in context_keys[context]:
            raise ValueError(f"No action {action!r} in context {context!r}")

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
        _placeholder, _prev_view_widget.title_widget.text.strip(" "), "left"
    )

    confirmation_overlay.bottom_w = bottom_widget
    main_widget.contents[0] = (confirmation_overlay, ("weight", 1))


# Context Actions

# {<context>: [<func>, <state>], ...}
keys = {context: {} for context in context_keys}


# global
@_register_key(("global", "Quit"))
def quit():
    raise urwid.ExitMainLoop()


@_register_key(("global", "Key Bar"))
def expand_collapse_keys():
    global key_bar_is_collapsed

    if expand_key_is_shown:
        if key_bar_is_collapsed and key_bar_rows() > 1:
            expand.original_widget.set_text(f"\u25BC [{expand_key[0]}]")
            main_widget.contents[-1] = (
                bottom_bar,
                ("given", key_bar_rows()),
            )
            key_bar_is_collapsed = False
        elif not key_bar_is_collapsed:
            expand.original_widget.set_text(f"\u25B2 [{expand_key[0]}]")
            main_widget.contents[-1] = (bottom_bar, ("given", 1))
            key_bar_is_collapsed = True


def resize():
    global expand_key_is_shown

    cols = get_terminal_size()[0]
    rows = key_bar.original_widget.rows((cols,))
    if expand_key_is_shown:
        if rows == 1:
            bottom_bar.contents.pop()
            expand_key_is_shown = False
    elif rows > 1:
        bottom_bar.contents.append((expand, ("given", 5, False)))
        expand_key_is_shown = True

    if not key_bar_is_collapsed:
        main_widget.contents[-1] = (
            bottom_bar,
            ("given", key_bar_rows()),
        )


def key_bar_rows():
    # Consider columns occupied by the expand key
    cols = get_terminal_size()[0] - (5 + 2) * expand_key_is_shown
    return key_bar.original_widget.rows((cols,))


keys["global"].update({"resized": [resize, True]})


# menu
@_register_key(
    ("menu", "Prev"),
    ("menu", "Next"),
    ("menu", "Page Up"),
    ("menu", "Page Down"),
    ("menu", "Top"),
    ("menu", "Bottom"),
)
def menu_nav():
    main.displayer.send(menu.focus_position - 1)
    if not main.at_top_level or main.at_top_level and main.menu_list:
        set_menu_actions()


def set_menu_actions():
    pos = menu.focus_position - 1
    if pos == -1:
        disable_actions("menu", "Switch Pane", "Delete", "Prev", "Page Up", "Top")
    elif isinstance(main.menu_list[pos][1], GeneratorType):
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

    if pos == len(main.menu_list) - 1:
        disable_actions("menu", "Next", "Page Down", "Bottom")
    else:
        enable_actions("menu", "Next", "Page Down", "Bottom")


@_register_key(("menu", "Open"))
def open():
    if menu.focus_position == 0 or isinstance(
        main.menu_list[menu.focus_position - 1][1], GeneratorType
    ):
        main.displayer.send(main.OPEN)
    else:
        main.set_context("full-image")
        main_widget.contents[0] = (view, ("weight", 1))
        set_image_view_actions()


@_register_key(("menu", "Back"))
def back():
    main.displayer.send(main.BACK)


# image
@_register_key(("image", "Maximize"))
def maximize():
    main.set_context("full-image")
    main_widget.contents[0] = (view, ("weight", 1))
    set_image_view_actions()


# image-grid
@_register_key(("image-grid", "Size+"))
def cell_width_inc():
    if image_grid.cell_width < 50:
        image_grid.cell_width += 2
        Image._grid_cache.clear()


@_register_key(("image-grid", "Open"))
def maximize_cell():
    main.set_context("full-grid-image")
    row = image_grid_box.base_widget.focus
    image = (
        row.focus
        if isinstance(row, urwid.Columns)  # when maxcol >= cell_width
        else row
    ).original_widget.original_widget  # The Image is in a LineSquare in an AttrMap

    image_box._w.contents[1][0].contents[1] = (image, ("weight", 1, True))
    image_box.set_title(basename(image._image._source))
    main_widget.contents[0] = (image_box, ("weight", 1))


@_register_key(("image-grid", "Size-"))
def cell_width_dec():
    if image_grid.cell_width > 30:
        image_grid.cell_width -= 2
        Image._grid_cache.clear()


# full-grid-image
@_register_key(("full-grid-image", "Force Render"))
def force_render_maximized_cell():
    # Will re-render immediately after processing input, since caching has been disabled
    # for `Image` widgets.
    image_box._w.contents[1][0].contents[1][0]._force_render = True


# full-image, full-grid-image
@_register_key(("full-image", "Restore"), ("full-grid-image", "Back"))
def restore():
    main.set_prev_context()
    main_widget.contents[0] = (pile, ("weight", 1))
    if main.get_context() == "menu":
        set_menu_actions()
    elif main.get_context() == "image":
        set_image_view_actions()


# image, full-image
@_register_key(("image", "Prev"), ("full-image", "Prev"))
def prev_image():
    if menu.focus_position > 1:
        menu.focus_position -= 1
        main.displayer.send(menu.focus_position - 1)
    set_image_view_actions()


@_register_key(("image", "Next"), ("full-image", "Next"))
def next_image():
    # `menu_list` is one item less than `menu` (at it's beginning), hence no `len - 1`
    if (
        menu.focus_position < len(main.menu_list)
        # Don't scroll through directory items in image views
        and isinstance(main.menu_list[menu.focus_position][1], Image)  # Next item
    ):
        menu.focus_position += 1
        main.displayer.send(menu.focus_position - 1)

    set_image_view_actions()


@_register_key(("image", "Force Render"), ("full-image", "Force Render"))
def force_render():
    # Will re-render immediately after processing input, since caching has been disabled
    # for `Image` widgets.
    main.menu_list[menu.focus_position - 1][1]._force_render = True


def set_image_view_actions(context: str = None):
    context = context or main.get_context()
    if menu.focus_position > 1:
        enable_actions(context, "Prev")
    else:
        disable_actions(context, "Prev")

    if (
        menu.focus_position == len(main.menu_list)  # Last item
        # Next item is a directory
        or isinstance(main.menu_list[menu.focus_position][1], GeneratorType)
    ):
        disable_actions(context, "Next")
    else:
        enable_actions(context, "Next")


# menu, image, full-image
@_register_key(
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
        logging.log_exception(f"Unable to delete {abspath(entry)}", logger)
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
        if not main.menu_list or isinstance(
            main.menu_list[menu.focus_position - 1][1], GeneratorType
        ):  # All menu entries have been deleted OR selected menu item is a directory
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
@_register_key(
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


# confirmation
@_register_key(("confirmation", "Confirm"))
def confirm():
    # `_confirm()` must [re]set `view.original_widget`
    _confirm[0](*_confirm[1])
    main.set_prev_context()


@_register_key(("confirmation", "Cancel"))
def cancel():
    _cancel[0](*_cancel[1])
    view.original_widget = _prev_view_widget
    main.set_prev_context()


logger = _logging.getLogger(__name__)
key_bar_is_collapsed = True
expand_key_is_shown = True
no_globals = {"global", "confirmation", "full-grid-image"}
_confirm = _cancel = _prev_view_widget = None  # To be set by `set_confirmation()`

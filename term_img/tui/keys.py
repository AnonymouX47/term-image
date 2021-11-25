"""Definitions of key functions"""

from shutil import get_terminal_size
from types import FunctionType
from typing import Tuple

import urwid

from .config import context_keys, expand_key
from .widgets import (
    bottom_bar,
    Image,
    image_box,
    key_bar,
    main as main_widget,
    menu,
    expand,
    pile,
    view,
    viewer,
)
from . import main


def _display_context_keys(context):
    actions = (*context_keys[context].items(), *context_keys["global"].items())
    # The underscores and blocks (U+2588) are to prevent wrapping amidst keys
    key_bar.original_widget.set_text(
        [
            [
                ("keys", f"{action.replace(' ', '_')}"),
                ("keys block", "\u2588"),
                ("keys", f"[{icon}]"),
                " ",
            ]
            for action, (_, icon, _) in actions[:-1]
        ]
        + [
            ("keys", f"{actions[-1][0].replace(' ', '_')}"),
            ("keys block", "\u2588"),
            ("keys", f"[{actions[-1][1][1]}]"),
        ]
    )


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
            keys[context][context_keys[context][action][0]] = func

    for context, action in args:
        if context not in context_keys:
            raise ValueError("Unknown context {context!r}")
        if context not in context_keys:
            raise ValueError("No action {action!r} in context {context!r}")

    return register


keys = {context: {} for context in context_keys}


# global
@_register_key(("global", "Quit"))
def quit():
    raise urwid.ExitMainLoop()


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
    else:
        if rows > 1:
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


keys["global"].update({expand_key[0]: expand_collapse_keys, "resized": resize})


# menu
@_register_key(("menu", "Prev"), ("menu", "Next"))
def menu_nav():
    main.displayer.send(menu.focus_position)


# image
@_register_key(("image", "Maximize"))
def maximize():
    main.set_context("full-image")
    main_widget.contents[0] = (view, ("weight", 1))


# full-image
@_register_key(("full-image", "Restore"))
def restore():
    main.set_context("image")
    main_widget.contents[0] = (pile, ("weight", 1))


# image, full-image
@_register_key(("image", "Prev"), ("full-image", "Prev"))
def prev_image():
    if menu.focus_position > 1:
        menu.focus_position -= 1
        main.displayer.send(menu.focus_position)


@_register_key(("image", "Next"), ("full-image", "Next"))
def next_image():
    # `menu_list` is one item less than `menu` (at it's beginning)
    if (
        menu.focus_position < len(main.menu_list)
        # Don't scroll through directory items in image views
        and isinstance(main.menu_list[menu.focus_position][1], Image)
    ):
        menu.focus_position += 1
        main.displayer.send(menu.focus_position)


@_register_key(("image", "Force Render"), ("full-image", "Force Render"))
def force_render():
    # Will re-render immediately after processing input, since caching has been disabled
    # for `Image` widgets.
    main.menu_list[menu.focus_position - 1][1]._forced_render = True


# menu, image, image-grid
@_register_key(
    ("menu", "Switch Pane"),
    ("image", "Switch Pane"),
    ("image-grid", "Switch Pane"),
)
def switch_pane():
    if main._context != "menu":
        main.set_context("menu")
        viewer.focus_position = 0
    elif menu.focus_position > 0:  # Do not switch to view pane when on '..' or 'Top'
        main.set_context("image" if view.original_widget is image_box else "image-grid")
        viewer.focus_position = 1


key_bar_is_collapsed = True
expand_key_is_shown = True

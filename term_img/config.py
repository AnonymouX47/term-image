"""Term-Img COnfiguration"""

from copy import deepcopy
import json
import os
import sys
from typing import Dict

import urwid

from .exit_codes import CONFIG_ERROR


def action_with_key(key: str, keyset: Dict[str, list]) -> str:
    """Return _action_ in _keyset_ having key _key_"""
    # The way it's used internally, it'll always return an action.
    for action, (k, *_) in keyset.items():
        if k == key:
            return action


def load_config() -> None:
    """Load user config from disk"""

    try:
        with open(f"{user_dir}/config.json") as f:
            config = json.load(f)
    except json.JSONDecodeError:
        print("config: Error loading user config... Using defaults.")
        update_context_nav_keys(context_keys, nav, nav)
        _set_action_status()
        return

    for name, is_valid in config_options.items():
        try:
            value = config[name]
            if is_valid(value):
                globals()[name.replace(" ", "_")] = value
            else:
                print(
                    f"config: Invalid value/type for {name!r} "
                    f"(got: {value!r} of type {type(value).__name__!r})... "
                    "Using default."
                )
        except KeyError:
            print(f"config: {name!r} not found... Using default.")

    try:
        keys = config["keys"]
    except KeyError:
        print("config: Key config not found... Using defaults.")
        update_context_nav_keys(context_keys, nav, nav)
        _set_action_status()
        return

    prev_nav = deepcopy(nav)  # used for identification.
    try:
        nav_update = keys.pop("navigation")
    except KeyError:
        print("config: Navigation keys config not found... Using defaults.")
    else:
        # Resolves all issues with _nav_update_ in the process
        update_context("navigation", nav, nav_update)

    # Done before updating other context keys to prevent modifying user-customized
    # actions using keys that are among the default navigation keys.
    update_context_nav_keys(context_keys, prev_nav, nav)

    for context, keyset in keys.items():
        if context not in context_keys:
            print(f"config: Unknown context {context!r}.")
            continue
        update_context(context, context_keys[context], keyset)

    _set_action_status()


def _set_action_status() -> None:
    for keyset in context_keys.values():
        for action in keyset.values():
            action[3:] = (True, True)  # Default: "shown", "enabled"


def store_config(*, default: bool = False) -> None:
    """Write current config to disk"""
    stored_keys = {"navigation": (_nav if default else nav)}

    # Remove help and navigation keys from contexts
    navi = {v[0] for v in (_nav if default else nav).values()}
    for context, keyset in (_context_keys if default else context_keys).items():
        keys = {}
        for action, (key, symbol, *_) in keyset.items():
            if key not in navi:
                keys[action] = [key, symbol]
        # Exclude contexts with navigation-only controls
        if keys:
            stored_keys[context] = keys

    with open(f"{user_dir}/config.json", "w") as f:
        json.dump(
            {
                "version": version,
                "cell width": (_cell_width if default else cell_width),
                "font ratio": (_font_ratio if default else font_ratio),
                "frame duration": (_frame_duration if default else frame_duration),
                "max pixels": (_max_pixels if default else max_pixels),
                "keys": stored_keys,
            },
            f,
            indent=4,
        )


def update_context(name: str, keyset: Dict[str, list], update: Dict[str, list]) -> None:
    """Update _keyset_ for context _name_ with _update_"""

    def use_default_key() -> None:
        default = keyset[action][0]
        if key == default or default in assigned | navi | _global:
            print(
                f"...Failed to fallback to default key {default!r} "
                f"for action {action!r} in context {name!r}, ..."
            )
            if default in _global:
                print(
                    f"...already assigned to global action "
                    f"{action_with_key(default, context_keys['global'])!r}."
                )
            elif default in navi:
                print(
                    f"...already assigned to navigation action "
                    f"{action_with_key(default, nav)!r}."
                )
            elif default in assigned:
                print(
                    f"...already assigned to action "
                    f"{action_with_key(default, keyset)!r} in the same context."
                )
            sys.exit(CONFIG_ERROR)

        assigned.add(key)
        print(
            f"...Using default key {default!r} for action {action!r} "
            f"in context {name!r}."
        )

    _global = (
        {v[0] for v in context_keys["global"].values()} if name != "global" else set()
    )
    navi = set() if name == "navigation" else {v[0] for v in nav.values()}
    assigned = set()

    for action, details in update.items():
        if not (
            isinstance(details, list)
            and len(details) == 2
            and all(isinstance(x, str) for x in details)
        ):
            print(
                f"config: The details of action {action!r} in context {name!r} "
                "is in an incorrect format... Using the default."
            )
            continue

        key, symbol = details
        if action not in keyset:
            print(f"config: Action {action!r} not available in context {name!r}.")
            continue
        if key not in _valid_keys:
            print(f"config: Invalid key {key!r}; Trying default...")
            use_default_key()
            continue

        if key in _global:
            print(
                f"config: {key!r} already assigned to a global action; "
                "Trying default..."
            )
            use_default_key()
        elif key in navi:
            print(
                f"config: {key!r} already assigned to a navigation action; "
                "Trying default..."
            )
            use_default_key()
        elif key in assigned:
            print(
                f"config: {key!r} already assigned to action "
                f"{action_with_key(key, keyset)!r} in the same context; "
                "Trying default..."
            )
            use_default_key()
        else:
            assigned.add(key)
            keyset[action][:2] = (key, symbol)


def update_context_nav_keys(
    context_keys: Dict[str, Dict[str, list]],
    nav: Dict[str, list],
    nav_update: Dict[str, list],
):
    """Update keys and symbols of navigation actions in all contexts in _context_keys_
    using _nav_ to identify navigation actions and _nav_update_ to update
    """
    navi = {v[0]: k for k, v in nav.items()}
    for context, keyset in context_keys.items():
        for action, details in keyset.items():
            if details[0] in navi:
                details[:2] = nav_update[navi[details[0]]]


user_dir = os.path.expanduser("~/.term_img")
if os.path.exists(user_dir):
    if not os.path.isdir(user_dir):
        print("config: Please rename or remove the file {user_dir!r}.")
        sys.exit(CONFIG_ERROR)
else:
    os.mkdir(user_dir)

version = 0.1  # For backwards compatibility

_valid_keys = {*bytes(range(32, 127)).decode(), *urwid.escape._keyconv.values(), "esc"}
_valid_keys.difference_update({f"shift f{n}" for n in range(1, 13)}.union({None}))

# For users and documentation
# Grouped by length and sorted lexicographically
valid_keys = sorted(_valid_keys, key=lambda s: chr(127 + len(s)) + s)

# Defaults
_cell_width = 30
_max_pixels = 2 ** 22  # 2048x2048
_font_ratio = 0.5
_frame_duration = 0.1

_nav = {
    "Left": ["left", "\u25c0"],
    "Up": ["up", "\u25b2"],
    "Right": ["right", "\u25b6"],
    "Down": ["down", "\u25bc"],
    "Page Up": ["page up", "PgUp"],
    "Page Down": ["page down", "PgDn"],
    "Home": ["home", "Home"],
    "End": ["end", "End"],
}

# {<context>: {<action>: [<key>, <symbol>, <help>, <visibility>, <state>], ...}, ...}
# <visibility> and <state> are added later in `load_config()`.
_context_keys = {
    "global": {
        "Config": ["C", "\u21e7C", "Open configuration menu"],
        "Help": ["f1", "F1", "Show this help menu"],
        "Quit": ["q", "q", "Exit Term-Img"],
        "Key Bar": [".", ".", "Expand/Collapse key bar"],
    },
    "menu": {
        "Open": ["enter", "\u23ce", "Open the selected item"],
        "Prev": ["up", "", "Select the next item on the list"],
        "Next": ["down", "", "Select the previous item on the list"],
        "Back": ["backspace", "\u27f5 ", "Return to the previous directory"],
        "Delete": ["d", "d", "Delete selected image"],
        "Switch Pane": ["tab", "\u21b9", "Switch to image pane"],
        "Page Up": ["page up", "PgUp", "Jump up one page"],
        "Page Down": ["page down", "PgDn", "Jump down one page"],
        "Top": ["home", "Home", "Jump to the top of the list"],
        "Bottom": ["end", "End", "Jump to the bottom of the list"],
    },
    "image": {
        "Prev": ["left", "", "Move to the previous image"],
        "Next": ["right", "", "Move to the next image"],
        "Force Render": [
            "F",
            "F",
            "Force an image, with more pixels than the set maximum, to be displayed",
        ],
        "Maximize": ["f", "f", "Maximize the current image"],
        "Delete": ["d", "d", "Delete current image"],
        "Switch Pane": ["tab", "\u21b9", "Switch to list pane"],
    },
    "image-grid": {
        "Open": ["enter", "\u23ce", "Maximize the selected image"],
        "Up": ["up", "", "Move cursor up"],
        "Down": ["down", "", "Move cursor down"],
        "Left": ["left", "", "Move cursor left"],
        "Right": ["right", "", "Move cursor right"],
        "Switch Pane": ["tab", "\u21b9", "Switch to list pane"],
        "Size-": ["-", "-", "Decrease grid cell size"],
        "Size+": ["+", "+", "Increase grid cell size"],
        "Page Up": ["page up", "PgUp", "Jump up one page"],
        "Page Down": ["page down", "PgDn", "Jump down one page"],
        "Top": ["home", "Home", "Jump to the top of the grid"],
        "Bottom": ["end", "End", "Jump to the bottom of the grid"],
    },
    "full-image": {
        "Restore": ["esc", "\u238b", "Exit maximized view"],
        "Prev": ["left", "", "Move to the previous image"],
        "Next": ["right", "", "Move to the next image"],
        "Force Render": [
            "F",
            "F",
            "Force an image, with more pixels than the set maximum, to be displayed",
        ],
        "Delete": ["d", "d", "Delete current image"],
    },
    "full-grid-image": {
        "Back": ["esc", "\u238b", "Back to grid view"],
        "Force Render": [
            "F",
            "F",
            "Force an image, with more pixels than the set maximum, to be displayed",
        ],
    },
    "confirmation": {
        "Confirm": ["enter", "\u23ce", ""],
        "Cancel": ["esc", "\u238b", ""],
    },
    "overlay": {
        "Close": ["esc", "\u238b", ""],
        "Up": ["up", "", "Scroll up"],
        "Down": ["down", "", "Scroll down"],
        "Page Up": ["page up", "PgUp", "Scroll up one page"],
        "Page Down": ["page down", "PgDn", "Scroll down one page"],
        "Top": ["home", "Home", "Jump to the top"],
        "Bottom": ["end", "End", "Jump to the bottom"],
    },
}
# End of Defaults

cell_width = _cell_width
max_pixels = _max_pixels
font_ratio = _font_ratio
frame_duration = _frame_duration
nav = deepcopy(_nav)
context_keys = deepcopy(_context_keys)

config_options = {
    "cell width": lambda value: isinstance(value, int) and value > 0,
    "font ratio": lambda value: isinstance(value, float) and value > 0.0,
    "frame duration": lambda value: isinstance(value, float) and value > 0.0,
    "max pixels": lambda value: isinstance(value, int) and value > 0,
}

if os.path.isfile(f"{user_dir}/config.json"):
    load_config()
else:
    update_context_nav_keys(context_keys, nav, nav)
    _set_action_status()
    store_config(default=True)

context_keys["global"]["Config"][3] = False  # Temporary, till config menu is implemted
expand_key = context_keys["global"]["Key Bar"]
expand_key[3] = False  # Hidden

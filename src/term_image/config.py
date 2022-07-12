"""Term-Image's Configuration"""

from __future__ import annotations

import json
import os
import sys
from copy import deepcopy
from operator import gt
from typing import Any, Dict

import urwid

from .exit_codes import CONFIG_ERROR
from .utils import COLOR_RESET, CSI, QUERY_TIMEOUT


def action_with_key(key: str, keyset: Dict[str, list]) -> str:
    """Return _action_ in _keyset_ having key _key_"""
    # The way it's used internally, it'll always return an action.
    for action, (k, *_) in keyset.items():
        if k == key:
            return action


def info(msg: str) -> None:
    print(
        f"{CSI}34mconfig: {COLOR_RESET}{msg}",
        # In case output is being redirected or piped
        file=sys.stdout if sys.stdout.isatty() else sys.stderr,
    )


def error(msg: str) -> None:
    print(f"{CSI}34mconfig: {CSI}31m{msg}{COLOR_RESET}", file=sys.stderr)


def fatal(msg: str) -> None:
    print(f"{CSI}34mconfig: {CSI}39m{CSI}41m{msg}{COLOR_RESET}", file=sys.stderr)


def init_config() -> None:
    """Initializes user configuration

    IMPORTANT:
        Must be called before any other function in this module
        and before anything else is imported from this module.
    """
    global checkers

    if os.path.exists(user_dir):
        if not os.path.isdir(user_dir):
            fatal(f"Please rename or remove the file {user_dir!r}.")
            sys.exit(CONFIG_ERROR)
    else:
        os.mkdir(user_dir)

    if os.path.isfile(config_file):
        if load_config():
            # Stored at this point in order to put missing values in place.
            store_config()
            info("... Successfully updated user config.")
    else:
        update_context_nav_keys(context_keys, nav, nav)
        store_config(default=True)

    for keyset in context_keys.values():
        for action in keyset.values():
            action[3:] = (True, True)  # Default: "shown", "enabled"
    context_keys["global"]["Config"][3] = False  # Till the config menu is implemented
    expand_key[3] = False  # "Key bar" action should be hidden

    if checkers is None:
        checkers = max(
            (
                len(os.sched_getaffinity(0))
                if hasattr(os, "sched_getaffinity")
                else os.cpu_count() or 0
            )
            - 1,
            2,
        )


def load_config() -> bool:
    """Load user config from disk"""
    updated = False

    try:
        with open(config_file) as f:
            config = json.load(f)
    except Exception as e:
        error(
            f"Failed to load user config ({type(e).__name__}: {e})... Using defaults."
        )
        update_context_nav_keys(context_keys, nav, nav)
        return updated

    try:
        c_version = config["version"]
        if gt(*[(*map(int, v.split(".")),) for v in (version, c_version)]):
            info("Updating user config...")
            updated = update_config(config, c_version)
            if not updated:
                error("... Failed to update user config.")
    except KeyError:
        error("Config version not found... Please correct this manually.")

    for name, (is_valid, msg) in config_options.items():
        try:
            value = config[name]
            if is_valid(value):
                globals()[name.replace(" ", "_")] = value
            else:
                error(
                    f"Invalid type/value for {name!r}, {msg} "
                    f"(got: {value!r} of type {type(value).__name__!r})... "
                    "Using default."
                )
        except KeyError:
            error(f"{name!r} not found... Using default.")

    try:
        keys = config["keys"]
    except KeyError:
        error("Key config not found... Using defaults.")
        update_context_nav_keys(context_keys, nav, nav)
        return updated

    prev_nav = deepcopy(nav)  # used for identification.
    try:
        nav_update = keys.pop("navigation")
    except KeyError:
        error("Navigation keys config not found... Using defaults.")
    else:
        # Resolves all issues with _nav_update_ in the process
        update_context("navigation", nav, nav_update)

    # Done before updating other context keys to prevent modifying user-customized
    # actions using keys that are among the default navigation keys.
    update_context_nav_keys(context_keys, prev_nav, nav)

    for context, keyset in keys.items():
        if context not in context_keys:
            error(f"Unknown context {context!r}.")
            continue
        update_context(context, context_keys[context], keyset)

    return updated


def store_config(*, default: bool = False) -> None:
    """Write current config to disk"""
    stored_keys = {"navigation": (_nav if default else nav)}

    # Remove description and navigation keys from contexts
    navi = {v[0] for v in (_nav if default else nav).values()}
    for context, keyset in (_context_keys if default else context_keys).items():
        keys = {}
        for action, (key, symbol, *_) in keyset.items():
            if key not in navi:
                keys[action] = [key, symbol]
        # Exclude contexts with navigation-only controls
        if keys:
            stored_keys[context] = keys

    try:
        with open(config_file, "w") as f:
            json.dump(
                {
                    "version": version,
                    **{
                        name: globals()["_" * default + f"{name.replace(' ', '_')}"]
                        for name in config_options
                    },
                    "keys": stored_keys,
                },
                f,
                indent=4,
            )
    except Exception as e:
        error(f"Failed to write user config ({type(e).__name__}: {e}).")


def update_config(config: Dict[str, Any], old_version: str) -> bool:
    """Updates the user config to latest version

    Returns:
        ``True``, if successful. Otherwise, ``False``.
    """
    # Must use the values directly, never reference the corresponding global variables,
    # as those might change later and will break updating since it's incremental
    #
    # {<version>: [(<location>, <old-value>, <new-value>), ...], ...}
    changes = {
        "0.1": [],
        "0.2": [
            ("['anim cache']", NotImplemented, 100),
            ("['checkers']", NotImplemented, None),
            ("['getters']", NotImplemented, 4),
            ("['grid renderers']", NotImplemented, 1),
            ("['log file']", NotImplemented, os.path.join(user_dir, "term_image.log")),
            ("['max notifications']", NotImplemented, 2),
            ("['frame duration']", 0.1, NotImplemented),
            ("['keys']['image']['Force Render'][1]", "F", "\u21e7F"),
            ("['keys']['full-image']['Force Render'][1]", "F", "\u21e7F"),
            ("['keys']['full-grid-image']['Force Render'][1]", "F", "\u21e7F"),
        ],
        "0.3": [
            ("['font ratio']", 0.5, None),
            ("['no multi']", NotImplemented, False),
            ("['query timeout']", NotImplemented, 0.1),
            ("['style']", NotImplemented, "auto"),
            ("['swap win size']", NotImplemented, False),
        ],
    }

    versions = tuple(changes)
    versions = versions[versions.index(old_version) :]

    for version in versions:
        for location, old, new in changes[version]:
            try:
                if old is NotImplemented:  # Addition
                    exec(f"config{location} = new")
                elif new is NotImplemented:  # Removal
                    exec("del config" + location)
                else:  # Update
                    if old == eval("config" + location):  # Still default
                        exec(f"config{location} = new")
            except (KeyError, IndexError):
                if new is not NotImplemented:
                    error(
                        f"Config option/value at {location!r} is missing, "
                        "the new default will be put in place."
                    )

    config["version"] = version
    try:
        os.replace(config_file, f"{config_file}.old")
    except OSError as e:
        error(f"Failed to backup previous config file ({type(e).__name__}: {e})")
        return False
    else:
        info(f"Previous config file has been moved to '{config_file}.old'.")

    return True


def update_context(name: str, keyset: Dict[str, list], update: Dict[str, list]) -> None:
    """Update _keyset_ for context _name_ with _update_"""

    def use_default_key() -> None:
        default = keyset[action][0]
        if key == default or default in assigned | navi | global_:
            fatal(
                f"...Failed to fallback to default key {default!r} "
                f"for action {action!r} in context {name!r}, ..."
            )
            if default in global_:
                fatal(
                    f"...already assigned to global action "
                    f"{action_with_key(default, context_keys['global'])!r}."
                )
            elif default in navi:
                fatal(
                    f"...already assigned to navigation action "
                    f"{action_with_key(default, nav)!r}."
                )
            elif default in assigned:
                fatal(
                    f"...already assigned to action "
                    f"{action_with_key(default, keyset)!r} in the same context."
                )
            sys.exit(CONFIG_ERROR)

        assigned.add(key)
        info(
            f"...Using default key {default!r} for action {action!r} "
            f"in context {name!r}."
        )

    global_ = (
        {v[0] for v in context_keys["global"].values()} if name != "global" else set()
    )
    navi = set() if name == "navigation" else {v[0] for v in nav.values()}
    assigned = set()

    for action, properties in update.items():
        if not (
            isinstance(properties, list)
            and len(properties) == 2
            and all(isinstance(x, str) for x in properties)
        ):
            error(
                f"The properties of action {action!r} in context {name!r} "
                "is in an incorrect format... Using the default."
            )
            continue

        key, symbol = properties
        if action not in keyset:
            error(f"Action {action!r} not available in context {name!r}.")
            continue
        if key not in _valid_keys:
            error(f"Invalid key {key!r}; Trying default...")
            use_default_key()
            continue

        if key in global_:
            error(f"{key!r} already assigned to a global action; Trying default...")
            use_default_key()
        elif key in navi:
            error(f"{key!r} already assigned to a navigation action; Trying default...")
            use_default_key()
        elif key in assigned:
            error(
                f"{key!r} already assigned to action "
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
) -> None:
    """Update keys and symbols of navigation actions in all contexts in _context_keys_
    using _nav_ to identify navigation actions and _nav_update_ to update
    """
    navi = {v[0]: k for k, v in nav.items()}
    for context, keyset in context_keys.items():
        for action, properties in keyset.items():
            if properties[0] in navi:
                properties[:2] = nav_update[navi[properties[0]]]


user_dir = os.path.join(os.path.expanduser("~"), ".term_image")
config_file = os.path.join(user_dir, "config.json")
version = "0.3"  # For config upgrades

_valid_keys = {*bytes(range(32, 127)).decode(), *urwid.escape._keyconv.values(), "esc"}
_valid_keys.update(
    {
        f"{modifier} {key}"
        for key in (
            *(f"f{n}" for n in range(1, 13)),
            "delete",
            "end",
            "home",
            "up",
            "down",
            "left",
            "right",
        )
        for modifier in ("ctrl", "shift", "shift ctrl")
    }
)
_valid_keys.update(
    {
        f"ctrl {key}"
        for key in (
            *map(chr, range(ord("a"), ord("z") + 1)),
            "page up",
            "page down",
        )
    }
)
_valid_keys.difference_update({None, "ctrl c", "ctrl z"})

# For users and documentation
valid_keys = sorted(
    _valid_keys,
    key=lambda s: (
        chr(127 + len(s.rsplit(" ", 1)[-1]))  # group by main key
        + s.rsplit(" ", 1)[-1].lower()  # group both cases of alphabetical keys together
        + s.rsplit(" ", 1)[-1]  # sort alphabetical keys by case
        + chr(127 + len(s))  # sort by length within a group of the same main key
    ),
)
for key in ("page up", "page down"):
    valid_keys.remove(key)
    valid_keys.remove("ctrl " + key)
valid_keys.extend(("page up", "ctrl page up", "page down", "ctrl page down"))

# Defaults
anim_cache = _anim_cache = 100
cell_width = _cell_width = 30
checkers = _checkers = None
font_ratio = _font_ratio = None
getters = _getters = 4
grid_renderers = _grid_renderers = 1
log_file = _log_file = os.path.join(user_dir, "term_image.log")
max_notifications = _max_notifications = 2
max_pixels = _max_pixels = 2**22  # 2048x2048
no_multi = _no_multi = False
query_timeout = _query_timeout = QUERY_TIMEOUT
style = _style = "auto"
swap_win_size = _swap_win_size = False

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

# {<context>: {<action>: [<key>, <symbol>, <desc>, <visibility>, <state>], ...}, ...}
# <visibility> and <state> are added later in `init_config()`.
_context_keys = {
    "global": {
        "Config": ["C", "\u21e7C", "Open configuration menu"],
        "Help": ["f1", "F1", "Show this help menu"],
        "Quit": ["q", "q", "Exit term-image"],
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
            "\u21e7F",
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
            "\u21e7F",
            "Force an image, with more pixels than the set maximum, to be displayed",
        ],
        "Delete": ["d", "d", "Delete current image"],
    },
    "full-grid-image": {
        "Back": ["esc", "\u238b", "Back to grid view"],
        "Force Render": [
            "F",
            "\u21e7F",
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

nav = deepcopy(_nav)
context_keys = deepcopy(_context_keys)
expand_key = context_keys["global"]["Key Bar"]

config_options = {
    "anim cache": (
        lambda x: isinstance(x, int) and x > 0,
        "must be an integer greater than zero",
    ),
    "cell width": (
        lambda x: isinstance(x, int) and 30 <= x <= 50 and not x % 2,
        "must be an even integer between 30 and 50 (both inclusive)",
    ),
    "checkers": (
        lambda x: x is None or isinstance(x, int) and x >= 0,
        "must be `null` or a non-negative integer",
    ),
    "font ratio": (
        lambda x: x is None or isinstance(x, float) and x > 0.0,
        "must be `null` or a float greater than zero",
    ),
    "getters": (
        lambda x: isinstance(x, int) and x > 0,
        "must be an integer greater than zero",
    ),
    "grid renderers": (
        lambda x: isinstance(x, int) and x >= 0,
        "must be a non-negative integer",
    ),
    "log file": (
        lambda x: (
            isinstance(x, str)
            and (
                # exists, is a file and writable
                (os.path.isfile(x) and os.access(x, os.W_OK))
                # is not a directory and the parent directory is writable
                or (not os.path.isdir(x) and os.access(os.path.dirname(x), os.W_OK))
            )
        ),
        "must be a string containing a writable path to a file",
    ),
    "max notifications": (
        lambda x: isinstance(x, int) and x > -1,
        "must be an non-negative integer",
    ),
    "max pixels": (
        lambda x: isinstance(x, int) and x > 0,
        "must be an integer greater than zero",
    ),
    "no multi": (
        lambda x: isinstance(x, bool),
        "must be a boolean",
    ),
    "query timeout": (
        lambda x: isinstance(x, float) and x > 0.0,
        "must be a float greater than zero",
    ),
    "style": (
        lambda x: x in {"auto", "block", "iterm2", "kitty"},
        "must be one of 'auto', 'block', 'iterm2', 'kitty'",
    ),
    "swap win size": (
        lambda x: isinstance(x, bool),
        "must be a boolean",
    ),
}

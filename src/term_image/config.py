"""Term-Image's Configuration"""

from __future__ import annotations

import json
import os
import sys
from copy import deepcopy
from dataclasses import dataclass, field
from os import path
from typing import Any, Callable, Dict, Tuple

import urwid

from .exit_codes import CONFIG_ERROR
from .utils import COLOR_RESET, CSI, QUERY_TIMEOUT


class ConfigOptions(dict):
    """Config options store

    * Subscription with an option name returns the corresponding :py:class:`Option`
      instance.
    * Attribute reference with a variable name ('s/ /_/g') returns the option's current
      value.
    * Attribute reference with a "private" name ('s/ /_/g' and preceded by '_') returns
      the option's default value.
    """

    def _attr_to_option(self, attr: str) -> Tuple[Option, str]:
        default = attr.startswith("_")
        name = attr.replace("_", " ")
        if default:
            name = name[1:]
        try:
            return self[name], "default" if default else "value"
        except KeyError:
            raise AttributeError(f"Ain't no such config option as {name!r}") from None

    def __getattr__(self, attr: str):
        return getattr(*self._attr_to_option(attr))

    def __setattr__(self, attr: str, value: Any):
        setattr(*self._attr_to_option(attr), value)


@dataclass
class Option:
    """A config option."""

    value: Any = field(init=False)
    default: Any
    is_valid: Callable[[Any], bool]
    error_msg: str

    def __post_init__(self):
        self.value = self.default


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
    """Initializes user configuration.

    IMPORTANT:
        Must be called before any other function in this module
        and before anything else is imported from this module.
    """
    if user_config_file:
        load_config(user_config_file)
    elif xdg_config_file:
        load_xdg_config()

    for keyset in context_keys.values():
        for action in keyset.values():
            action[3:] = (True, True)  # "shown", "enabled"
    context_keys["global"]["Config"][3] = False  # Till the config menu is implemented
    expand_key[3] = False  # "Key bar" action should be hidden

    if config_options.checkers is None:
        config_options.checkers = max(
            (
                len(os.sched_getaffinity(0))
                if hasattr(os, "sched_getaffinity")
                else os.cpu_count() or 0
            )
            - 1,
            2,
        )


def load_config(config_file: str) -> None:
    """Loads a user config file."""
    try:
        with open(config_file) as f:
            config = json.load(f)
    except Exception as e:
        error(
            f"Failed to load config file {config_file!r} ({type(e).__name__}: {e})... "
            "Using fallbacks."
        )
        return

    keys = config.pop("keys", None)

    for name, value in config.items():
        try:
            option = config_options[name]
        except KeyError:
            error(f"Unknown option {name!r} from {config_file!r}.")
        else:
            if option.is_valid(value):
                option.value = value
            else:
                error(
                    f"Invalid type/value for {name!r}; {option.error_msg} "
                    f"(got: {value!r} of type {type(value).__name__!r})... "
                    f"Using fallback: {option.value!r}."
                )
    if keys:
        # Globals first...
        keyset = keys.pop("global", None)
        if keyset:
            update_context("global", context_keys["global"], keyset, config_file)

        # Then navigation...
        try:
            nav_update = keys.pop("navigation")
        except KeyError:
            pass
        else:
            # Resolves all issues with *nav_update* in the process
            update_context("navigation", nav, nav_update, config_file)
        # Done before updating other context keys so that actions having keys
        # conflicting with those for naviagation in the same context can be detected
        update_context_nav(context_keys, nav)
        navi.update((key, nav_action) for nav_action, (key, _) in nav.items())

        # Then other context actions.
        # Also going through unupdated contexts to detect conflicts between the
        # unpdated keys and navigation or global keys
        for context, keyset in context_keys.items():
            update = keys.pop(context, {})
            update_context(context, keyset, update, config_file)
        for context in keys:
            error(f"Unknown context {context!r}.")


def load_xdg_config() -> None:
    """Loads user config files according to the XDG Base Directories spec."""
    for config_dir in reversed(os.environ.get("XDG_CONFIG_DIRS", "/etc").split(":")):
        config_file = path.join(config_dir, "term_image", "config.json")
        if (
            # The XDG Base Dirs spec states that relative paths should be ignored
            path.abspath(config_dir) == config_dir
            and path.isfile(config_file)
        ):
            load_config(config_file)

    if path.isfile(xdg_config_file):
        load_config(xdg_config_file)


def store_config(config_file: str) -> None:
    """Writes current config to a file."""
    config = {
        name: option.value
        for name, option in config_options.items()
        if option.value != option.default
    }

    modified_keys = {}
    modified_nav = {
        action: properties
        for _properties, (action, properties) in zip(_nav.values(), nav.items())
        if properties != _properties
    }
    if modified_nav:
        modified_keys["navigation"] = modified_nav
    for _keyset, (context, keyset) in zip(_context_keys.values(), context_keys.items()):
        context_nav = context_navs[context]
        keys = {}
        for _properties, (action, properties) in zip(_keyset.values(), keyset.items()):
            # Exclude context navigation actions and of course, unmodified actions
            if action not in context_nav and properties[:2] != _properties[:2]:
                keys[action] = properties[:2]  # Remove description and state
        if keys:  # Exclude contexts with only navigation actions
            modified_keys[context] = keys
    if modified_keys:
        config["keys"] = modified_keys

    err = None
    try:
        try:
            os.makedirs(path.dirname(config_file) or ".", exist_ok=True)
        except (FileExistsError, NotADirectoryError):
            err = "one of the parent paths is a non-directory"
        else:
            with open(config_file, "w") as f:
                json.dump(config, f, indent=4)
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
    if err:
        error(f"Failed to write user config to {config_file!r} ({err}).")


def update_context(
    context: str, keyset: Dict[str, list], update: Dict[str, list], config_file: str
) -> None:
    """Updates the *keyset* of context *context* with *update*"""

    def try_fallback(default: bool = False) -> None:
        default_keyset = _nav if context == "navigation" else _context_keys[context]
        _key = default_keyset[action][0] if default else keyset[action][0]
        default = default or _key == default_keyset[action][0]
        in_global = _key in global_
        in_assigned = _key in assigned

        info(
            f"... trying {'default' if default else 'fallback'} key {_key!r} "
            + f"for action {action!r} in context {context!r}"
            + (f" from {config_file!r}" if action in update else "")
            + "..."
        )
        if in_global or in_assigned:
            emit, end = (fatal, ".") if default else (error, "...")
            if in_global:
                emit(f"... already assigned to global action {global_[_key]!r}{end}")
            elif in_assigned:
                _action = assigned[_key]
                emit(
                    f"... already assigned to action {_action!r} "
                    + (
                        f"(derived from navigation action {context_nav[_action]!r}) "
                        if _action in context_nav
                        else ""
                    )
                    + f"in the same context{end}"
                )
            sys.exit(CONFIG_ERROR) if default else try_fallback(default=True)
            return

        assigned[_key] = action
        if default:
            keyset[action][:2] = default_keyset[action][:2]
        info(f"... using key {_key!r} for action {action!r} in context {context!r}.")

    global_ = (
        set()
        if context == "global"
        else {key: action for action, (key, *_) in context_keys["global"].items()}
    )
    context_nav = context_navs.get(context, {})
    assigned = {keyset[action][0]: action for action in keyset.keys() - update.keys()}
    # Must include all context nav actions and they should override normal actions
    # using the same key since they have been updated earlier.
    assigned.update({keyset[action][0]: action for action in context_nav.keys()})

    for action, (key, *_) in keyset.items():
        try:
            properties = update.pop(action)
        except KeyError:
            if key in global_:
                error(f"Unupdated key {key!r} already assigned to a global action...")
                try_fallback(default=True)
            elif assigned[key] != action:  # Has been assigned to a nav action earlier
                _action = assigned[key]
                error(
                    f"Unupdated key {key!r} already assigned to action {_action!r} "
                    f"(derived from navigation action {context_nav[_action]!r}) "
                    "in the same context..."
                )
                try_fallback(default=True)
            continue

        if action in context_nav:
            error(
                f"Navigation action {action!r} in context {context!r} should be "
                f"modified via navigation action {context_nav[action]!r}."
            )
            continue

        if not (
            isinstance(properties, list)
            and len(properties) == 2
            and all(isinstance(x, str) for x in properties)
        ):
            error(f"The properties {repr(properties)!r} are in an incorrect format...")
            try_fallback()
            continue

        key, symbol = properties
        if key not in _valid_keys:
            error(f"Invalid key {key!r}...")
            try_fallback()
        elif key in global_:
            error(
                f"Updated Key {key!r} already assigned to global action "
                f"{global_[key]!r}..."
            )
            try_fallback()
        elif key in assigned:
            _action = assigned[key]
            error(
                f"Updated Key {key!r} already assigned to action {_action!r} "
                + (
                    f"(derived from navigation action {context_nav[_action]!r}) "
                    if _action in context_nav
                    else ""
                )
                + "in the same context..."
            )
            try_fallback()
        else:
            assigned[key] = action
            keyset[action][:2] = (key, symbol)

    for action in update:
        error(f"Unknown action {action!r} in context {context!r} from {config_file!r}.")


def update_context_nav(
    context_keys: Dict[str, Dict[str, list]],
    nav_update: Dict[str, list],
) -> None:
    """Updates keys and symbols of navigation actions in all contexts
    in *context_keys*.
    """
    for context, keyset in context_keys.items():
        context_nav = context_navs[context]
        for action, properties in keyset.items():
            if action in context_nav:
                properties[:2] = nav_update[context_nav[action]]


user_dir = path.join(path.expanduser("~"), ".term_image")
user_config_file = None
xdg_config_file = path.join(
    os.environ.get("XDG_CONFIG_HOME", path.join(path.expanduser("~"), ".config")),
    "term_image",
    "config.json",
)

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

config_options = {
    "anim cache": Option(
        100,
        lambda x: isinstance(x, int) and x > 0,
        "must be an integer greater than zero",
    ),
    "cell width": Option(
        30,
        lambda x: isinstance(x, int) and 30 <= x <= 50 and not x % 2,
        "must be an even integer between 30 and 50 (both inclusive)",
    ),
    "checkers": Option(
        None,
        lambda x: x is None or isinstance(x, int) and x >= 0,
        "must be `null` or a non-negative integer",
    ),
    "font ratio": Option(
        None,
        lambda x: x is None or isinstance(x, float) and x > 0.0,
        "must be `null` or a float greater than zero",
    ),
    "getters": Option(
        4,
        lambda x: isinstance(x, int) and x > 0,
        "must be an integer greater than zero",
    ),
    "grid renderers": Option(
        1,
        lambda x: isinstance(x, int) and x >= 0,
        "must be a non-negative integer",
    ),
    "log file": Option(
        path.join(user_dir, "term_image.log"),
        lambda x: (
            isinstance(x, str)
            and (
                # exists, is a file and writable
                (path.isfile(x) and os.access(x, os.W_OK))
                # is not a directory and the parent directory is writable
                or (not path.isdir(x) and os.access(path.dirname(x) or ".", os.W_OK))
            )
        ),
        "must be a string containing a writable file path",
    ),
    "max notifications": Option(
        2,
        lambda x: isinstance(x, int) and x > -1,
        "must be an non-negative integer",
    ),
    "max pixels": Option(
        2**22,  # 2048x2048
        lambda x: isinstance(x, int) and x > 0,
        "must be an integer greater than zero",
    ),
    "no multi": Option(
        False,
        lambda x: isinstance(x, bool),
        "must be a boolean",
    ),
    "query timeout": Option(
        QUERY_TIMEOUT,
        lambda x: isinstance(x, float) and x > 0.0,
        "must be a float greater than zero",
    ),
    "style": Option(
        "auto",
        lambda x: x in {"auto", "block", "iterm2", "kitty"},
        "must be one of 'auto', 'block', 'iterm2', 'kitty'",
    ),
    "swap win size": Option(
        False,
        lambda x: isinstance(x, bool),
        "must be a boolean",
    ),
}
config_options = ConfigOptions(config_options)

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
_navi = {key: nav_action for nav_action, (key, _) in _nav.items()}

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
        "Page Up": ["page up", "", "Jump up one page"],
        "Page Down": ["page down", "", "Jump down one page"],
        "Top": ["home", "", "Jump to the top of the list"],
        "Bottom": ["end", "", "Jump to the bottom of the list"],
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
        "Page Up": ["page up", "", "Jump up one page"],
        "Page Down": ["page down", "", "Jump down one page"],
        "Top": ["home", "", "Jump to the top of the grid"],
        "Bottom": ["end", "", "Jump to the bottom of the grid"],
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
        "Page Up": ["page up", "", "Scroll up one page"],
        "Page Down": ["page down", "", "Scroll down one page"],
        "Top": ["home", "", "Jump to the top"],
        "Bottom": ["end", "", "Jump to the bottom"],
    },
}

nav = deepcopy(_nav)
navi = deepcopy(_navi)
context_navs = {
    context: {action: navi[key] for action, (key, *_) in keyset.items() if key in navi}
    for context, keyset in _context_keys.items()
}
update_context_nav(_context_keys, _nav)  # Update symbols
context_keys = deepcopy(_context_keys)
expand_key = context_keys["global"]["Key Bar"]

"""Term-Image's Configuration"""

from __future__ import annotations

import json
import logging as _logging
import os
from copy import deepcopy
from dataclasses import dataclass, field
from os import path
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple, Union

import urwid

from . import logging, notify
from .utils import DEFAULT_QUERY_TIMEOUT


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


def is_writable(path: Union[str, os.PathLike, Path]) -> bool:
    """Checks if a file path is writable or creatable.

    Returns:
      - ``True``, if:
        - the file exists and is writable
        - the file doesn't exists but can be created
      - ``False``, if:
        - the path points to a directory
        - the file exists but is unwritable
        - the file doesn't exists and cannot be created
    """
    path = Path(path).expanduser()
    writable = False

    try:
        if path.exists():
            if path.is_file() and os.access(path, os.W_OK):
                writable = True
        else:
            for path in path.parents:
                if path.exists():
                    if path.is_dir() and os.access(path, os.W_OK):
                        writable = True
                    break
    except OSError:  # Fails to stat some directories
        pass

    return writable


def action_with_key(key: str, keyset: Dict[str, list]) -> Optional[str]:
    """Returns the *action* in *keyset* having key *key* or ``None`` if there's no
    such action.
    """
    for action, (k, *_) in keyset.items():
        if k == key:
            return action


def get_log_function(level) -> Callable[[str], None]:
    def log(msg: str) -> None:
        if logging.VERBOSE is None:  # logging not yet initialized
            notify.notify(msg, notify_level, "config", verbose=verbose)
        else:
            logging.log(msg, _logger, log_level, "config", verbose=verbose)

    notify_level = getattr(notify, level)
    log_level = getattr(_logging, level)
    verbose = level == "INFO"

    return log


def init_config() -> None:
    """Initializes user configuration."""
    for var, level in (("error", "ERROR"), ("info", "INFO"), ("warn", "WARNING")):
        globals()[var] = get_log_function(level)

    if user_config_file:
        load_config(user_config_file)
    elif xdg_config_file:
        load_xdg_config()

    for keyset in context_keys.values():
        for action in keyset.values():
            action[3:] = (True, True)  # "shown", "enabled"
    context_keys["global"]["Config"][3] = False  # Till the config menu is implemented
    expand_key[3] = False  # "Key bar" action should be hidden

    reconfigure_tui(_context_keys)


def load_config(config_file: str) -> None:
    """Loads a user config file."""

    def revert_context_update(
        keyset: Dict[str, list], prev_keyset: Dict[str, list]
    ) -> None:
        for properties, prev_properties in zip(keyset.values(), prev_keyset.values()):
            properties[:] = prev_properties

    try:
        with open(config_file) as f:
            config = json.load(f)
    except Exception as e:
        error(f"Failed to load {config_file!r} ({type(e).__name__}: {e}).")
        return

    keys = config.pop("keys", None)

    for name, value in config.items():
        try:
            option = config_options[name]
        except KeyError:
            warn(f"Unknown option {name!r} (in {config_file!r}).")
        else:
            if option.is_valid(value):
                option.value = value
            else:
                value_repr = "null" if value is None else repr(value)
                value_type_name = "null" if value is None else type(value).__name__
                error(
                    f"Invalid type/value for {name!r}; {option.error_msg} "
                    f"(got: {value_repr} of type {value_type_name!r})."
                )
                option_repr = "null" if option.value is None else repr(option.value)
                info(f"Using former value: {option_repr}.")
    if keys:
        prev_context_keys = deepcopy(context_keys)

        # Globals first...
        g_keyset = context_keys["global"]
        g_update = keys.pop("global", None)
        if g_update:
            prev_g_keyset = deepcopy(g_keyset)
            if not update_context("global", g_keyset, g_update, config_file):
                revert_context_update(g_keyset, prev_g_keyset)
                return

        # Then navigation...
        # Also going through if unupdated to detect conflicts between the unpdated keys
        # and global keys
        nav_update = keys.pop("navigation", {})
        prev_nav = deepcopy(nav)
        if not update_context("navigation", nav, nav_update, config_file):
            g_update and revert_context_update(g_keyset, prev_g_keyset)
            revert_context_update(nav, prev_nav)
            return

        # Done before updating other context keys so that actions having keys
        # conflicting with those for naviagation in the same context can be detected
        update_context_nav(context_keys, nav)
        navi.update((key, nav_action) for nav_action, (key, _) in nav.items())

        # Then other context actions.
        # Also going through unupdated contexts to detect conflicts between the
        # unpdated keys and navigation or global keys
        for context, keyset in context_keys.items():
            update = keys.pop(context, {})
            if not update_context(context, keyset, update, config_file):
                for keyset, prev_keyset in zip(
                    context_keys.values(), prev_context_keys.values()
                ):  # Includes the global context
                    revert_context_update(keyset, prev_keyset)
                revert_context_update(nav, prev_nav)
                navi.update((key, nav_action) for nav_action, (key, _) in nav.items())
                return
        for context in keys:
            warn(f"Unknown context {context!r} (in {config_file!r}).")


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


def reconfigure_tui(
    old_context_keys: Optional[Dict[str, Dict[str, list]]] = None
) -> None:
    """Updates aspects of the TUI to use the current config option values and
    keybindings.
    """
    from . import logging
    from .tui.keys import change_key
    from .tui.widgets import expand, image_grid, notif_bar, pile

    command = urwid.command_map._command_defaults.copy()
    urwid.command_map._command = {
        nav[action][0]: command[key] for key, action in _navi.items()
    }

    if old_context_keys:
        for context, keyset in context_keys.items():
            old_keyset = old_context_keys[context]
            for action, (key, *_) in keyset.items():
                old_key = old_keyset[action][0]
                if old_key != key:
                    try:
                        change_key(context, old_key, key)
                    except KeyError:  # e.g navigation keys in "image-grid"
                        pass

    expand_or_collapse = expand.original_widget.text[0]
    expand.original_widget.set_text(f"{expand_or_collapse} [{expand_key[1]}]")

    if not logging.QUIET:
        if pile.contents[-1][0] is notif_bar:
            pile.contents.pop()
        if config_options.max_notifications:
            pile.contents.append(
                (notif_bar, ("given", config_options.max_notifications))
            )

    image_grid.cell_width = config_options.cell_width


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
            err = "one of the parents is not a directory"
        else:
            with open(config_file, "w") as f:
                json.dump(config, f, indent=4)
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
    if err:
        error(f"Failed to write user config to {config_file!r} ({err}).")


def update_context(
    context: str, keyset: Dict[str, list], update: Dict[str, list], config_file: str
) -> bool:
    """Updates the *keyset* of context *context* with *update*.

    Returns ``True`` if successful, otherwise ``False``.
    """

    def try_fallback(default: bool = False) -> bool:
        """Sets the fallback (old) or default key for the current action if not already
        assigned to another action.

        Returns ``True`` if successful, otherwise ``False``.
        """
        if default:
            default_keyset = _nav if context == "navigation" else _context_keys[context]
            _key = default_keyset[action][0]
            if _key == keyset[action][0]:
                info("... default key is the same as the current/former key.")
                error("... unable to find an unassigned fallback.")
                return False
        else:
            _key = keyset[action][0]
            if _key == key:
                info("... former key is the same as the new key.")
                return try_fallback(default=True)
        in_global = _key in global_
        in_assigned = _key in assigned
        fallback = "default" if default else "former"

        if in_global or in_assigned:
            if in_global:
                error(
                    f"... {fallback} key {_key!r} already assigned to global action "
                    f"{global_[_key]!r}."
                )
            elif in_assigned:
                _action = assigned[_key]
                error(
                    f"... {fallback} key {_key!r} already assigned to action "
                    f"{_action!r} "
                    + (
                        f"(derived from 'navigation::{context_nav[_action]}') "
                        if _action in context_nav
                        else ""
                    )
                    + "in the same context."
                )
            if default:
                error("... unable to find an unassigned fallback.")
                return False
            return try_fallback(default=True)

        assigned[_key] = action
        if default:
            keyset[action][:2] = default_keyset[action][:2]
        info(f"... using {fallback} key {_key!r}.")

        return True

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

    failed = True
    for action, (key, *_) in keyset.items():
        context_action = f"'{context}::{action}'"
        try:
            properties = update.pop(action)
        except KeyError:
            conflict_msg = f"Key conclict with {context_action}..."
            if key in global_:
                error(conflict_msg)
                error(
                    f"... current key {key!r} already assigned to global action "
                    f"{global_[key]!r}."
                )
                if not try_fallback(default=True):
                    break
            elif assigned[key] != action:  # Has been assigned to a nav action earlier
                _action = assigned[key]
                error(conflict_msg)
                error(
                    f"... current key {key!r} already assigned to action {_action!r} "
                    f"(derived from 'navigation::{context_nav[_action]}') "
                    "in the same context."
                )
                if not try_fallback(default=True):
                    break
            continue

        if action in context_nav:
            warn(
                f"{context_action} should be updated via 'navigation::"
                f"{context_nav[action]}' (in {config_file!r})."
            )
            continue

        if not (
            isinstance(properties, list)
            and len(properties) == 2
            and all(isinstance(x, str) for x in properties)
        ):
            error(
                f"The properties ({properties!r}) of {context_action} are not in the "
                f"correct format (in {config_file!r})..."
            )
            if not try_fallback():
                break
            continue

        key, symbol = properties
        conflict_msg = (
            f"Key conclict with {context_action} (updated in {config_file!r})..."
        )

        if key not in _valid_keys:
            error(f"Invalid key {key!r} for {context_action} (in {config_file!r})...")
            if not try_fallback():
                break
        elif key in global_:
            error(conflict_msg)
            error(
                f"... new key {key!r} already assigned to global action "
                f"{global_[key]!r}."
            )
            if not try_fallback():
                break
        elif key in assigned:
            _action = assigned[key]
            error(conflict_msg)
            error(
                f"... new Key {key!r} already assigned to action {_action!r} "
                + (
                    f"(derived from 'navigation::{context_nav[_action]}') "
                    if _action in context_nav
                    else ""
                )
                + "in the same context."
            )
            if not try_fallback():
                break
        else:
            assigned[key] = action
            keyset[action][:2] = (key, symbol)
    else:
        failed = False
        for action in update:
            warn(
                f"Unknown action {action!r} in context {context!r} "
                f"(in {config_file!r})."
            )
    if failed:
        error(
            f"Unable to update with keybindings from {config_file!r} due to the "
            "previous error... Changes reverted."
        )

    return not failed


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


_logger = _logging.getLogger(__name__)
error: Callable[[str], None] = None
info: Callable[[str], None] = None
warn: Callable[[str], None] = None

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
    "cell ratio": Option(
        None,
        lambda x: x is None or isinstance(x, float) and x > 0.0,
        "must be `null` or a float greater than zero",
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
        path.join("~", ".term_image", "term_image.log"),
        lambda x: isinstance(x, str) and is_writable(x),
        "must be a string containing a writable/creatable file path",
    ),
    "max notifications": Option(
        2,
        lambda x: isinstance(x, int) and 0 <= x <= 5,
        "must be an integer between 0 and 5 (both inclusive)",
    ),
    "max pixels": Option(
        2**22,  # 2048x2048
        lambda x: isinstance(x, int) and x > 0,
        "must be an integer greater than zero",
    ),
    "multi": Option(
        True,
        lambda x: isinstance(x, bool),
        "must be a boolean",
    ),
    "query timeout": Option(
        DEFAULT_QUERY_TIMEOUT,
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

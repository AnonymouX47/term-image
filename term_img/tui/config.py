"""Term-Img COnfiguration"""

from __future__ import annotations

import json
import os
import sys
from typing import Dict

import urwid


def load_config() -> None:
    try:
        with open(f"{user_dir}/config.json") as f:
            config = json.load(f)
        version = config["version"]
        keys = config["keys"]
        nav_update = keys.pop("navigation")

        if len({v[0] for v in nav_update.values()}) == len(nav):
            # Update context navigation keys.
            # Done before updating 'nav' since it uses default keys for identification.
            # Done before updating other contexts to prevent modifying user-customized
            # actions using keys that are among the default navigation keys.
            navi = {v[0]: k for k, v in nav.items()}
            for context, keyset in context_keys.items():
                for action, details in keyset.items():
                    if details[0] in navi:
                        details[:2] = nav_update[navi[details[0]]]

            update_context("navigation", nav, nav_update)
        else:
            print("Too many or conflicting navigation keys; Using defaults")

        for context, keyset in keys.items():
            if context not in context_keys:
                print(f"Unknown context {context!r}.")
                continue
            update_context(context, context_keys[context], keyset)
    except (json.JSONDecodeError, KeyError) as e:
        print(f"Error loading user config: {e}\nUsing default config.")


def store_config() -> None:
    stored_keys = {"navigation": nav}

    # Remove help and navigation keys from contexts
    navi = {v[0] for v in nav.values()}
    for context, keyset in context_keys.items():
        keys = {}
        for action, (key, icon, _) in keyset.items():
            if key not in navi:
                keys[action] = [key, icon]
        # Exclude contexts with navigation-only controls
        if keys:
            stored_keys[context] = keys

    with open(f"{user_dir}/config.json", "w") as f:
        json.dump({"version": version, "keys": stored_keys}, f, indent=4)


def update_context(name: str, keyset: Dict[str, list], update: Dict[str, list]) -> None:
    """Update _keyset_ for context _name_ with _update_"""

    def use_default_key():
        default = keyset[action][0]
        if key == default or default in assigned:
            print(
                f"Failed to fallback to default key {default!r} for action {action!r} "
                f"in context {name!r}; "
                f"previously assigned to action {action_with_key(default, keyset)!r}."
            )
            sys.exit(CONFIG_ERROR)
        assigned.add(key)
        print(
            f"...Using default key {keyset[action][0]!r} for action {action!r} "
            f"in context {name!r}."
        )

    _global = (
        {v[0] for v in context_keys["global"].values()}
        if name != "global"
        else set()
    )
    navi = (
        set()
        if name == "navigation"
        else {v[0] for v in nav.values()}
    )
    assigned = set()

    for action, (key, icon) in update.items():
        if action not in keyset:
            print(f"Action {action!r} not available in context {name!r}.")
            continue
        if key not in _valid_keys:
            print(f"Invalid key {key!r}; Trying default...")
            use_default_key()
            continue

        if key in _global:
            print(f"{key!r} already assigned to a global action; Trying default...")
            use_default_key()
        elif key in navi:
            print(f"{key!r} already assigned to a navigation action; Trying default...")
            use_default_key()
        elif key in assigned:
            print(
                f"{key!r} already assigned to action {action_with_key(key, keyset)!r} "
                f"in the same context; Trying default..."
            )
            use_default_key()
        else:
            assigned.add(key)
            keyset[action][:2] = [key, icon]

def action_with_key(key: str, keyset: Dict[str, list]) -> str:
    """Return _action_ in _keyset_ having key _key_"""
    # The way it's used internally, it'll always return an action.
    for action, (k, *_) in keyset.items():
        if k == key:
            return action


CONFIG_ERROR = 3

user_dir = os.path.expanduser("~/.term_img")
if os.path.exists(user_dir):
    if not os.path.isdir(user_dir):
        print("Please rename or remove the file {user_dir!r}.")
        sys.exit(CONFIG_ERROR)
else:
    os.mkdir(user_dir)

version = 0.1  # For backwards compatibility

_valid_keys = {*bytes(range(32, 127)).decode(), *urwid.escape._keyconv.values(), "esc"}
_valid_keys.difference_update({f"shift f{n}" for n in range(1, 13)}.union({None}))

# For users and documentation
valid_keys = sorted(_valid_keys, key=lambda s: chr(127+len(s)) + s)

# Defaults
nav = {
    "Left": ["left", "\u2190"],
    "Up": ["up", "\u2191"],
    "Right": ["right", "\u2192"],
    "Down": ["down", "\u2193"],
}

# {<context>: {<action>: [<key>, <icon>, <help>], ...}, ...}
context_keys = {
    "global": {
        "Help": ["f1", "F1", "Show this help menu"],
        "Quit": ["q", "q", "Exit Term-Img"],
    },
    "menu": {
        "Next": ["down", "\u2193", "Move to the previous item on the list"],
        "Prev": ["up", "\u2191", "Move to the next item on the list"],
        "Switch Pane": ["tab", "\u21b9", "Switch to image pane"],
    },
    "image": {
        "Prev": ["left", "\u2190", "Move to the previous image"],
        "Next": ["right", "\u2192", "Move to the next image"],
        "Maximize": ["f", "f", "Maximize image view"],
        "Switch Pane": ["tab", "\u21b9", "Switch to list pane"],
    },
    "image-grid": {"Switch Pane": ["tab", "\u21b9", "Switch to list pane"]},
    "full-image": {
        "Restore": ["esc", "\u238b", "Exit maximized view"],
        "Prev": ["left", "\u2190", "Move to the previous image"],
        "Next": ["right", "\u2192", "Move to the next image"],
    },
}
# End of Defaults

if os.path.isfile(f"{user_dir}/config.json"):
    load_config()
else:
    store_config()

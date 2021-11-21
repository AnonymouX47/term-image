"""Main UI"""

import urwid

from .widgets import info_bar, image_box, main, menu, view, viewer
from .keys import keys


def _process_input(key):
    info_bar.original_widget.set_text(f"{key!r} {info_bar.original_widget.text}")

    found = False
    if key in keys["global"]:
        keys["global"][key]()
        found = True
    else:
        found = keys[context].get(key, lambda: False)() is None

    if key[0] == "mouse press":  # strings also support subscription
        # change context if the pane in focus changed.
        if context in {"image", "image-grid"} and viewer.focus_position == 0:
            set_context("menu")
        elif context == "menu":
            if viewer.focus_position == 1:
                set_context(
                    "image" if view.original_widget is image_box else "image-grid"
                )
            else:  # Update image view
                displayer.send(menu.focus_position)

    return bool(found)


def set_context(new_context):
    global context
    context = new_context


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


context = "menu"
menu_list = []

palette = [
    ("default", "", "", "", "#ffffff", "#000000"),
    ("white on black", "", "", "", "#ffffff", "#000000"),
    ("black on white", "", "", "", "#000000", "#ffffff"),
    ("mine", "", "", "", "#ff00ff", "#ffff00"),
    ("focused entry", "", "", "", "standout", ""),
    ("unfocused box", "", "", "", "#7f7f7f", ""),
    ("focused box", "", "", "", "#ffffff", ""),
    ("green fg", "", "", "", "#00ff00", ""),
    ("red on green", "", "", "", "#ff0000,bold", "#00ff00"),
]

loop = MyLoop(main, palette, unhandled_input=_process_input)
loop.screen.clear()
loop.screen.set_terminal_properties(2 ** 24)

displayer = None  # Placeholder for image display generator; Set from `..cli.main()`

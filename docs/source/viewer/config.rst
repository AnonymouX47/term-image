Configuration
=============

The configuration is divided into the following categories:

* Options
* Keys

The configuration is stored in the JSON format in a file located at ``~/.term_image/config.json``.


Config Options
--------------

| These are fields whose values control various behaviours of the viewer.
| Any option with a "[\*]" after its description will be used only when the corresponding command-line option is either not specified or has an invalid value.

They are as follows:

anim cache
   The maximum frame count of an image for which frames will be cached during animation. [\*]

   * Type: integer
   * Valid values: x > ``0``

cell width
   The initial width of (no of columns for) grid cells, in the TUI.

   * Type: integer
   * Valid values: ``30`` <= x <= ``50`` and x is even

checkers
   Maximum number of subprocesses for checking directory sources.

   * Type: null or integer
   * Valid values: ``null`` or x >= ``0``

   | If ``null``, the number of subprocesses is automatically determined based on the amount of logical processors available. CPU affinity is also taken into account on supported platforms.
   | If ``0`` (zero), directory sources are checked within the main process.

.. _font-ratio-config:

font ratio
   The :term:`font ratio`. [\*]

   * Type: float
   * Valid values: x > ``0.0``

getters
   Number of threads for downloading images from URL sources.

   * Type: integer
   * Valid values: x > ``0``

grid renderers
   Number of subprocesses for rendering grid cells.

   * Type: integer
   * Valid values: x > ``0``

   | If ``0`` (zero), grid cells are rendered by a thread of the main process.

.. _log-file:

log file
   The file to which logs are written. [\*]

   * Type: string
   * Valid values: An absolute path to a writable file.

   | If the file doesn't exist the parent directory must be writable, so the file can created.
   | If the file exists, it is appended to, not overwritten.
   | See :ref:`logging`.

max notifications
   The maximum number of TUI notifications that can show at a time.

   * Type: integer
   * Valid values: x >= ``0``

   | Adjusts the height of the :ref:`notification bar <notif-bar>`.

max pixels
   The maximum amount of pixels in images to be displayed in the TUI. [\*]

   * Type: integer
   * Valid values: x > ``0``

   Any image having more pixels than the specified value will be:

     * skipped, in CLI mode, if ``--max-pixels-cli`` is specified.
     * replaced, in TUI mode, with a placeholder when displayed but can still be forced to display or viewed externally.

   Note that increasing this should not have any effect on general performance (i.e navigation, etc) but the larger an image is, the more the time and memory it'll take to render it. Thus, a large image might delay the rendering of other images to be rendered immediately after it.


.. attention:: The ``version`` field is not a config option, it's used for config file updates and should not be tampered with.


Key Config
----------

The key assigned to every :ref:`action <actions>` can be modified in the config file.

The ``"keys"`` field in the configuration holds a mapping containing fields each mapping a :ref:`context <contexts>` to a mapping of :ref:`actions <actions>` to their properties.

The format of the ``"keys"`` mapping is thus::

   {
      "<context>": {
         "<action>": [
            "<key>",
            "<symbol>"
         ],

         ...
      },

      ...
   }

*'...' means continuous repitition of the format occurs.*

| *action* is the name of the action. **It should not be modified**.
| Any or both of *key* and *symbol* can be changed. Both must be valid Python strings, hence Unicode characters are supported.

.. hint::

   If using a Unicode character that occupies multiple columns in *symbol*, then add spaces after it as required to cover-up for the extra columns.

.. note::

   The ``navigation`` field is not actually a *context*, instead it's the universal navigation controls configuration from which navigation *actions* in actual *contexts* are updated.

.. attention::

   1. Keys used in ``navigation`` or ``global`` contexts cannot be used in any other context.
   2. All keys in a context must be unique.
   3. If a key is invalid or already used, the default is tried as a fallback but if that fails (because it's already used), the session is terminated.

| `Here <https://raw.githubusercontent.com/AnonymouX47/term-image/main/vim-style_config.json>`_ is a config with Vim-style (majorly navigation) keybindings.
| *Remember to rename the file to* ``config.json``.

Below is a list of all **valid** values for *key*::

    " "
    "!"
    """
    "#"
    "$"
    "%"
    "&"
    "'"
    "("
    ")"
    "*"
    "+"
    ","
    "-"
    "."
    "/"
    "0"
    "1"
    "2"
    "3"
    "4"
    "5"
    "6"
    "7"
    "8"
    "9"
    ":"
    ";"
    "<"
    "="
    ">"
    "?"
    "@"
    "["
    "\\"
    "]"
    "^"
    "_"
    "`"
    "A"
    "a"
    "ctrl a"
    "B"
    "b"
    "ctrl b"
    "C"
    "c"
    "D"
    "d"
    "ctrl d"
    "E"
    "e"
    "ctrl e"
    "F"
    "f"
    "ctrl f"
    "G"
    "g"
    "ctrl g"
    "H"
    "h"
    "ctrl h"
    "I"
    "i"
    "ctrl i"
    "J"
    "j"
    "ctrl j"
    "K"
    "k"
    "ctrl k"
    "L"
    "l"
    "ctrl l"
    "M"
    "m"
    "ctrl m"
    "N"
    "n"
    "ctrl n"
    "O"
    "o"
    "ctrl o"
    "P"
    "p"
    "ctrl p"
    "Q"
    "q"
    "ctrl q"
    "R"
    "r"
    "ctrl r"
    "S"
    "s"
    "ctrl s"
    "T"
    "t"
    "ctrl t"
    "U"
    "u"
    "ctrl u"
    "V"
    "v"
    "ctrl v"
    "W"
    "w"
    "ctrl w"
    "X"
    "x"
    "ctrl x"
    "Y"
    "y"
    "ctrl y"
    "Z"
    "z"
    "{"
    "|"
    "}"
    "~"
    "f1"
    "ctrl f1"
    "shift f1"
    "shift ctrl f1"
    "f2"
    "ctrl f2"
    "shift f2"
    "shift ctrl f2"
    "f3"
    "ctrl f3"
    "shift f3"
    "shift ctrl f3"
    "f4"
    "ctrl f4"
    "shift f4"
    "shift ctrl f4"
    "f5"
    "ctrl f5"
    "shift f5"
    "shift ctrl f5"
    "f6"
    "ctrl f6"
    "shift f6"
    "shift ctrl f6"
    "f7"
    "ctrl f7"
    "shift f7"
    "shift ctrl f7"
    "f8"
    "ctrl f8"
    "shift f8"
    "shift ctrl f8"
    "f9"
    "ctrl f9"
    "shift f9"
    "shift ctrl f9"
    "up"
    "ctrl up"
    "shift up"
    "shift ctrl up"
    "end"
    "ctrl end"
    "shift end"
    "shift ctrl end"
    "esc"
    "f10"
    "ctrl f10"
    "shift f10"
    "shift ctrl f10"
    "f11"
    "ctrl f11"
    "shift f11"
    "shift ctrl f11"
    "f12"
    "ctrl f12"
    "shift f12"
    "shift ctrl f12"
    "tab"
    "down"
    "ctrl down"
    "shift down"
    "shift ctrl down"
    "home"
    "ctrl home"
    "shift home"
    "shift ctrl home"
    "left"
    "ctrl left"
    "shift left"
    "shift ctrl left"
    "enter"
    "right"
    "ctrl right"
    "shift right"
    "shift ctrl right"
    "delete"
    "ctrl delete"
    "shift delete"
    "shift ctrl delete"
    "insert"
    "backspace"
    "page up"
    "ctrl page up"
    "page down"
    "ctrl page down"

Any values other than these will be flagged as invalid and the default will be used instead (if possible) for that session.

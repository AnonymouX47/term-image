"""
..
   Control Sequences

   See https://invisible-island.net/xterm/ctlseqs/ctlseqs.html
"""

from __future__ import annotations

__all__ = []  # Updated later on

import re
from typing import Tuple

# Parameters
C = "%c"
Ps = "%d"
Pt = "%s"
Pm = lambda n: ";".join((Ps,) * n)  # noqa: E731

_START = None  # Marks the beginning control sequence definitions

# C0
BEL = "\x07"
ESC = "\x1b"

# C1
APC = f"{ESC}_"
CSI = f"{ESC}["
DCS = f"{ESC}P"
OSC = f"{ESC}]"
ST = f"{ESC}\\"

# Cursor Movement
CURSOR_UP = f"{CSI}{Ps}A"
CURSOR_DOWN = f"{CSI}{Ps}B"
CURSOR_FORWARD = f"{CSI}{Ps}C"
CURSOR_BACKWARD = f"{CSI}{Ps}D"

# Select Graphic Rendition
SGR_NORMAL = f"{CSI}m"
SGR_FG_RGB = f"{CSI}38;2;{Pm(3)}m"
SGR_FG_RGB_2 = f"{CSI}38:2::{Ps}:{Ps}:{Ps}m"
SGR_BG_RGB = f"{CSI}48;2;{Pm(3)}m"
SGR_BG_RGB_2 = f"{CSI}48:2::{Ps}:{Ps}:{Ps}m"
SGR_FG_INDEXED = f"{CSI}38;5;{Ps}m"
SGR_FG_INDEXED_2 = f"{CSI}38:5:{Ps}m"
SGR_BG_INDEXED = f"{CSI}48;5;{Ps}m"
SGR_BG_INDEXED_2 = f"{CSI}48:5:{Ps}m"

# DEC Modes
DECSET = f"{CSI}?{Ps}h"
DECRST = f"{CSI}?{Ps}l"

SHOW_CURSOR = DECSET % 25
HIDE_CURSOR = DECRST % 25

# # Terminal Synchronized Output
# # See https://gist.github.com/christianparpart/d8a62cc1ab659194337d73e399004036
BEGIN_SYNCED_UPDATE = DECSET % 2026
END_SYNCED_UPDATE = DECRST % 2026

# Window manipulation (XTWINOPS)
XTWINOPS_1 = f"{CSI}{Ps}t"

TEXT_AREA_SIZE_PX = XTWINOPS_1 % 14
CELL_SIZE_PX = XTWINOPS_1 % 16

# Text parameters (OSC Ps ; Pt ST)
TEXT_PARAM_SET = f"{OSC}{Ps};{Pt}{ST}"
TEXT_PARAM_QUERY = f"{OSC}{Ps};?{ST}"

TEXT_FG_QUERY = TEXT_PARAM_QUERY % 10
TEXT_BG_QUERY = TEXT_PARAM_QUERY % 11

# Others
DA1 = f"{CSI}c"
ERASE_CHARS = f"{CSI}{Ps}X"
XTVERSION = f"{CSI}>q"

# iTerm2 Inline Image Protocol
# See https://iterm2.com/documentation-images.html
ITERM2_START = f"{OSC}1337;File="

# Kitty Graphics Protocol
# See https://sw.kovidgoyal.net/kitty/graphics-protocol/
KITTY_START = f"{APC}G"
KITTY_TRANSMISSION = f"{KITTY_START}{Pt};{Pt}{ST}"
KITTY_DELETE = KITTY_TRANSMISSION % (f"a=d,d={C}", "")
KITTY_DELETE_EXTRA = KITTY_TRANSMISSION % (f"a=d,d={C},{Pt}", "")

KITTY_SUPPORT_QUERY = KITTY_TRANSMISSION % (
    "a=q,t=d,i=31,f=24,s=1,v=1,C=1,c=1,r=1",
    "AAAA",
)
KITTY_END_CHUNKED = KITTY_TRANSMISSION % ("q=1,m=0", "")
KITTY_DELETE_ALL = KITTY_DELETE % "A"
KITTY_DELETE_CURSOR = KITTY_DELETE % "C"
KITTY_DELETE_Z_INDEX = KITTY_DELETE_EXTRA % ("Z", f"z={Ps}")


module_items = tuple(globals().items())
for name, value in module_items[module_items.index(("_START", None)) + 1 :]:
    globals()[f"{name}_b"] = value.encode()
    __all__.extend((name, f"{name}_b"))


# Patterns for responses to queries
class Response:
    CSI_escaped = re.escape(CSI)
    OSC_escaped = re.escape(OSC)
    ST_escaped = re.escape(ST)
    ST_or_BEL = f"(?:{ST_escaped}|{BEL})"
    XTWINOPS = rf"{CSI_escaped}{Ps};(\d+);(\d+)t"

    RGB_SPEC_re = rf"{OSC_escaped}(\d+);rgb:([\da-fA-F/]+){ST_or_BEL}"
    XTVERSION_re = rf"{DCS}>\|(\w+)[( ]([^){ESC}]+)\)?{ST_or_BEL}"
    TEXT_AREA_SIZE_PX_re = XTWINOPS % 4
    CELL_SIZE_PX_re = XTWINOPS % 6
    KITTY_RESPONSE_re = (
        f"{KITTY_START}"
        r"i=(?P<id>\d+)(?:,I=(?P<number>\d+))?;(?P<message>.+?)"
        f"{ST_escaped}"
    )

    for name, regex in tuple(locals().items()):
        if name.endswith("_re"):
            globals()[name] = re.compile(regex, re.ASCII)
            __all__.append(name)


__all__ += ("x_parse_color",)


def x_parse_color(spec: str) -> Tuple[int, int, int]:
    """Converts an RGB device specification according to ``XParseColor``

    See the "Color Names" section of the ``XParseColor`` man page.
    """
    # One hex char -> 4 bits
    return tuple(int(x, 16) * 255 // ((1 << (len(x) * 4)) - 1) for x in spec.split("/"))


del _START, module_items, Response

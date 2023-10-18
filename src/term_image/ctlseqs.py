"""
..
   Control Sequences

   See https://invisible-island.net/xterm/ctlseqs/ctlseqs.html
"""

from __future__ import annotations

__all__: list[str] = []  # Updated later on

import re

# Parameters ===========================================================================

C = "%c"
Ps = "%d"
Pt = "%s"


def Pm(n: int) -> str:
    return ";".join((Ps,) * n)


# ============================ START OF CONTROL SEQUENCES ==============================

_START = None  # Marks the beginning control sequence definitions


# C0 ===================================================================================

BEL = "\x07"
ESC = "\x1b"

BEL_b: bytes
ESC_b: bytes


# C1 ===================================================================================

APC = f"{ESC}_"
CSI = f"{ESC}["
DCS = f"{ESC}P"
OSC = f"{ESC}]"
ST = f"{ESC}\\"

APC_b: bytes
CSI_b: bytes
DCS_b: bytes
OSC_b: bytes
ST_b: bytes


# Functions Beginning With CSI =========================================================

DA1 = f"{CSI}c"
ERASE_CHARS = f"{CSI}{Ps}X"
XTVERSION = f"{CSI}>q"

DA1_b: bytes
ERASE_CHARS_b: bytes
XTVERSION_b: bytes

# # Cursor Movement ====================================================================

CURSOR_UP = f"{CSI}{Ps}A"
CURSOR_DOWN = f"{CSI}{Ps}B"
CURSOR_FORWARD = f"{CSI}{Ps}C"
CURSOR_BACKWARD = f"{CSI}{Ps}D"

CURSOR_UP_b: bytes
CURSOR_DOWN_b: bytes
CURSOR_FORWARD_b: bytes
CURSOR_BACKWARD_b: bytes

# # Select Graphic Rendition ===========================================================

SGR_NORMAL = f"{CSI}m"
SGR_FG_RGB = f"{CSI}38;2;{Pm(3)}m"
SGR_FG_RGB_2 = f"{CSI}38:2::{Ps}:{Ps}:{Ps}m"
SGR_BG_RGB = f"{CSI}48;2;{Pm(3)}m"
SGR_BG_RGB_2 = f"{CSI}48:2::{Ps}:{Ps}:{Ps}m"

SGR_NORMAL_b: bytes
SGR_FG_RGB_b: bytes
SGR_FG_RGB_2_b: bytes
SGR_BG_RGB_b: bytes
SGR_BG_RGB_2_b: bytes

# # DEC Modes ==========================================================================

DECSET = f"{CSI}?{Ps}h"
DECRST = f"{CSI}?{Ps}l"

DECSET_b: bytes
DECRST_b: bytes

SHOW_CURSOR = DECSET % 25
HIDE_CURSOR = DECRST % 25

SHOW_CURSOR_b: bytes
HIDE_CURSOR_b: bytes

# # # Terminal Synchronized Output =====================================================
# # # See https://gist.github.com/christianparpart/d8a62cc1ab659194337d73e399004036

BEGIN_SYNCED_UPDATE = DECSET % 2026
END_SYNCED_UPDATE = DECRST % 2026

BEGIN_SYNCED_UPDATE_b: bytes
END_SYNCED_UPDATE_b: bytes

# # Window manipulation (XTWINOPS) =====================================================

XTWINOPS_1 = f"{CSI}{Ps}t"

XTWINOPS_1_b: bytes

TEXT_AREA_SIZE_PX = XTWINOPS_1 % 14
CELL_SIZE_PX = XTWINOPS_1 % 16

TEXT_AREA_SIZE_PX_b: bytes
CELL_SIZE_PX_b: bytes


# Operating System Commands ============================================================

# # Text parameters (OSC Ps ; Pt ST) ===================================================

TEXT_PARAM_SET = f"{OSC}{Ps};{Pt}{ST}"
TEXT_PARAM_QUERY = f"{OSC}{Ps};?{ST}"

TEXT_PARAM_SET_b: bytes
TEXT_PARAM_QUERY_b: bytes

TEXT_FG_QUERY = TEXT_PARAM_QUERY % 10
TEXT_BG_QUERY = TEXT_PARAM_QUERY % 11

TEXT_FG_QUERY_b: bytes
TEXT_BG_QUERY_b: bytes

# # iTerm2 Inline Image Protocol =======================================================
# # See https://iterm2.com/documentation-images.html

ITERM2_START = f"{OSC}1337;File="

ITERM2_START_b: bytes


# Application Program Commands =========================================================

# # Kitty Graphics Protocol ============================================================
# # See https://sw.kovidgoyal.net/kitty/graphics-protocol/

KITTY_START = f"{APC}G"
KITTY_TRANSMISSION = f"{KITTY_START}{Pt};{Pt}{ST}"
KITTY_DELETE = KITTY_TRANSMISSION % (f"a=d,d={C}", "")
KITTY_DELETE_EXTRA = KITTY_TRANSMISSION % (f"a=d,d={C},{Pt}", "")

KITTY_START_b: bytes
KITTY_TRANSMISSION_b: bytes
KITTY_DELETE_b: bytes
KITTY_DELETE_EXTRA_b: bytes

KITTY_SUPPORT_QUERY = KITTY_TRANSMISSION % (
    "a=q,t=d,i=31,f=24,s=1,v=1,C=1,c=1,r=1",
    "AAAA",
)
KITTY_END_CHUNKED = KITTY_TRANSMISSION % ("q=1,m=0", "")
KITTY_DELETE_ALL = KITTY_DELETE % "A"
KITTY_DELETE_CURSOR = KITTY_DELETE % "C"
KITTY_DELETE_Z_INDEX = KITTY_DELETE_EXTRA % ("Z", f"z={Ps}")

KITTY_SUPPORT_QUERY_b: bytes
KITTY_END_CHUNKED_b: bytes
KITTY_DELETE_ALL_b: bytes
KITTY_DELETE_CURSOR_b: bytes
KITTY_DELETE_Z_INDEX_b: bytes


# `bytes` Versions of Control Sequences ================================================

module_items = tuple(globals().items())
for name, value in module_items[module_items.index(("_START", None)) + 1 :]:
    globals()[f"{name}_b"] = value.encode()
    __all__.extend((name, f"{name}_b"))

del _START, module_items


# ============================= END OF CONTROL SEQUENCES ===============================


# Patterns For Query Responses =========================================================

RGB_SPEC_re: re.Pattern[str]
XTVERSION_re: re.Pattern[str]
TEXT_AREA_SIZE_PX_re: re.Pattern[str]
CELL_SIZE_PX_re: re.Pattern[str]
KITTY_RESPONSE_re: re.Pattern[str]


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


del Response


# Other Definitions ====================================================================

__all__ += (
    "cursor_backward",
    "cursor_down",
    "cursor_forward",
    "cursor_up",
    "x_parse_color",
)


def cursor_backward(columns: int) -> str:
    return CURSOR_BACKWARD % columns if columns > 0 else ""


def cursor_down(lines: int) -> str:
    return CURSOR_DOWN % lines if lines > 0 else ""


def cursor_forward(columns: int) -> str:
    return CURSOR_FORWARD % columns if columns > 0 else ""


def cursor_up(lines: int) -> str:
    return CURSOR_UP % lines if lines > 0 else ""


def x_parse_color(spec: str) -> tuple[int, int, int]:
    """Converts an RGB device specification according to ``XParseColor``

    See the "Color Names" section of the ``XParseColor`` man page.

    NOTE:
        The older syntax isn't supported.
    """
    rgb = spec.split("/")
    scale = len(rgb[0]) * 4  # One hex char -> 4 bits
    uint_scale_max = (1 << scale) - 1
    r, g, b = [int(component, 16) * 255 // uint_scale_max for component in rgb]

    return (r, g, b)

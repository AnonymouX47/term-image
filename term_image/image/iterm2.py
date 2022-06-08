from __future__ import annotations

import re

from ..utils import lock_tty, query_terminal, read_tty
from .common import GraphicsImage


class ITerm2Image(GraphicsImage):
    """A render style using the iTerm2 inline image protocol.

    See :py:class:`GraphicsImage` for the complete description of the constructor.

    ATTENTION:
        Currently supported terminal emulators include:

          * `ITerm2 <https://iterm2.com>`_.
          * `Konsole <https://konsole.kde.org>`_ >= 22.04.0.
          * `WezTerm <https://wezfurlong.org/wezterm/>`_.
    """

    _TERM: str = ""
    _TERM_VERSION: str = ""

    @classmethod
    @lock_tty  # the terminal's response to the query is not read all at once
    def is_supported(cls):
        if cls._supported is None:
            # Terminal name/version query + terminal attribute query
            # The latter is to speed up the entirequery since most (if not all)
            # terminals should support it and most terminals treat queries as FIFO
            response = query_terminal(
                b"\033[>q\033[c", lambda s: not s.endswith(b"\033[?6")
            ).decode()
            read_tty()  # The rest of the response to `CSI c`

            # Not supported if the terminal doesn't respond to either query
            # or responds to the second but not the first
            if response:
                match = re.fullmatch(
                    r"\033P>\|(\w+)[( ]([^\033]+)\)?\033\\",
                    response.rpartition("\033")[0],
                )
                if match and match.group(1).lower() in {"iterm2", "konsole", "wezterm"}:
                    name, version = map(str.lower, match.groups())
                    try:
                        if name == "konsole" and (
                            tuple(map(int, version.split("."))) < (22, 4, 0)
                        ):
                            cls._supported = False
                        else:
                            cls._supported = True
                            cls._TERM, cls._TERM_VERSION = name, version
                    except ValueError:  # version string not "understood"
                        cls._supported = False
            else:
                cls._supported = False

        return cls._supported

from __future__ import annotations

__all__ = ("KittyImage",)

import PIL

from ..exceptions import TermImageException
from ..utils import query_terminal
from .common import BaseImage


class KittyImage(BaseImage):
    """An image based on the Kitty terminal graphics protocol.

    Raises:
        term_image.exceptions.TermImageException: The :term:`active terminal` doesn't
          support the protocol.

    See :py:class:`BaseImage` for the complete description of the constructor.
    """

    def __init__(self, image: PIL.Image.Image, **kwargs) -> None:
        if not self.is_supported():
            raise TermImageException(
                "This image render style is not supported in the current terminal"
            )
        super().__init__(image, **kwargs)

    @classmethod
    def is_supported(cls):
        if cls._supported is None:
            # Kitty graphics query + terminal attribute query
            # The second query is to speed up the query since most (if not all)
            # terminals should support it and most terminals treat queries as FIFO
            response = query_terminal(
                b"\033_Gi=31,s=1,v=1,a=q,t=d,f=24;AAAA\033\\\033[c",
                lambda s: not s.endswith(b"c"),
            )
            # Not supported if it doesn't respond to either query
            # or responds to the second but not the first
            cls._supported = bool(response and response.rpartition(b"\033")[0])

        return cls._supported

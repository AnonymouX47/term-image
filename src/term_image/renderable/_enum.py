"""
.. Enumerations for the Renderable API
"""

from __future__ import annotations

__all__ = ("FrameCount", "FrameDuration", "Seek")

import os
from enum import Enum, IntEnum, auto


class FrameCount(Enum):
    """Frame count enumeration

    .. seealso::
        :py:attr:`~term_image.renderable.Renderable.frame_count`,
        :py:meth:`~term_image.renderable.Renderable.seek`,
        :py:meth:`~term_image.renderable.Renderable.tell`.
    """

    INDEFINITE = auto()
    """Indicates a renderable has a streaming source.

    In other words, it's either the renderable has an infinite amount of frames or the
    exact amount cannot be predetermined.

    :meta hide-value:
    """

    POSTPONED = auto()
    """Indicates lazy evaluation of frame count.

    Evaluation of frame count is postponed until
    :py:attr:`~term_image.renderable.Renderable.frame_count` is invoked.

    .. seealso:: :py:meth:`~term_image.renderable.Renderable._get_frame_count_`.

    :meta hide-value:
    """


class FrameDuration(Enum):
    """Frame duration enumeration

    .. seealso:: :py:attr:`~term_image.renderable.Renderable.frame_duration`.
    """

    DYNAMIC = auto()
    """Dynamic frame duration

    The duration of each frame is determined at render-time.

    :meta hide-value:
    """


class Seek(IntEnum):
    """Relative seek enumeration

    TIP:
        * Each member's value is that of the corresponding
          :py:data:`os.SEEK_* <os.SEEK_SET>` constant.
        * Every member can be used directly as an integer since
          :py:class:`enum.IntEnum` is a base class.

    .. seealso::
       :py:meth:`Renderable.seek`,
       :py:meth:`RenderIterator.seek() <term_image.render.RenderIterator.seek>`
    """

    START = SET = os.SEEK_SET
    """Start position"""

    CURRENT = CUR = os.SEEK_CUR
    """Current position"""

    END = os.SEEK_END
    """End position"""

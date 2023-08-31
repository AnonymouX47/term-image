"""
.. Enumerations for the Renderable API
"""

from __future__ import annotations

__all__ = ("FrameCount", "FrameDuration")

from enum import Enum, auto


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

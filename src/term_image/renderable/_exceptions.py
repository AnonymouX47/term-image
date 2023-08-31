"""
.. Exceptions for the Renderable API core
"""

__all__ = (
    "RenderableError",
    "IndefiniteSeekError",
    "RenderError",
    "RenderSizeOutofRangeError",
)

from ..exceptions import TermImageError


class RenderableError(TermImageError):
    """Base exception class for errors specific to the :py:mod:`Renderable API
    <term_image.renderable>` and other APIs extending it.

    Raised for errors that occur during the creation of :term:`render classes`.
    """


class IndefiniteSeekError(RenderableError):
    """Raised when a seek is attempted on a renderable with
    :py:attr:`~term_image.renderable.FrameCount.INDEFINITE` frame count.
    """


class RenderError(RenderableError):
    """Base exception class for errors that occur **during** :term:`rendering`.

    If the direct cause of the error is an exception, it should typically be attached
    as the context of this exception, as in::

       raise SubclassOfRenderError("...") from exception
    """


class RenderSizeOutofRangeError(RenderableError):
    """Raised when the :term:`render size` of a renderable is beyond an expected
    range.
    """

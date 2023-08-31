"""
.. Exceptions for the Renderable API core
"""

from ..exceptions import TermImageError


class RenderableError(TermImageError):
    """Base exception for errors specific to the :py:mod:`Renderable API
    <term_image.renderable>` and other APIs extending it.

    Raised for errors specific to :py:class:`~term_image.renderable.Renderable`.
    """


class RenderError(RenderableError):
    """Raised for errors that occur **during** :term:`rendering`.

    If the direct cause of the error is an exception, it should typically be attached
    as the context of this exception i.e ``raise RenderError(...) from exc``.
    """

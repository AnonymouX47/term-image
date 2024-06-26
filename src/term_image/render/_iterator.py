"""
.. The RenderIterator API
"""

from __future__ import annotations

__all__ = ("RenderIterator", "RenderIteratorError", "FinalizedIteratorError")

from collections.abc import Generator

from typing_extensions import Any, Self

from .._utils import (
    arg_value_error,
    arg_value_error_msg,
    arg_value_error_range,
    get_terminal_size,
)
from ..exceptions import TermImageError
from ..geometry import Size, _Size
from ..padding import AlignedPadding, ExactPadding, Padding
from ..renderable import (
    Frame,
    FrameCount,
    FrameDuration,
    Renderable,
    RenderableData,
    RenderArgs,
    RenderData,
    Seek,
)

# Variables ====================================================================

DUMMY_FRAME: Frame = Frame(0, 0, _Size(1, 1), " ")

# Classes ======================================================================


class RenderIterator:
    """An iterator for efficient iteration over :term:`rendered` frames of an
    :term:`animated` renderable.

    Args:
        renderable: An animated renderable.
        render_args: Render arguments.
        padding: :term:`Render output` padding.
        loops: The number of times to go over all frames.

          * ``< 0`` -> loop infinitely.
          * ``0`` -> invalid.
          * ``> 0`` -> loop the given number of times.

          .. note::
            The value is ignored and taken to be ``1`` (one), if *renderable* has
            :py:class:`~term_image.renderable.FrameCount.INDEFINITE` frame count.

        cache: Determines if :term:`rendered` frames are cached.

          If the value is ``True`` or a positive integer greater than or equal to the
          frame count of *renderable*, caching is enabled. Otherwise i.e ``False`` or
          a positive integer less than the frame count, caching is disabled.

          .. note::
            The value is ignored and taken to be ``False``, if *renderable* has
            :py:class:`~term_image.renderable.FrameCount.INDEFINITE` frame count.

    Raises:
        ValueError: An argument has an invalid value.
        IncompatibleRenderArgsError: Incompatible render arguments.

    The iterator yields a :py:class:`~term_image.renderable.Frame` instance on every
    iteration.

    NOTE:
        * Seeking the underlying renderable
          (via :py:meth:`Renderable.seek() <term_image.renderable.Renderable.seek>`)
          does not affect an iterator, use :py:meth:`RenderIterator.seek` instead.
          Likewise, the iterator does not modify the underlying renderable's current
          frame number.
        * Changes to the underlying renderable's :term:`render size` does not affect
          an iterator's :term:`render outputs`, use :py:meth:`set_render_size` instead.
        * Changes to the underlying renderable's
          :py:attr:`~term_image.renderable.Renderable.frame_duration` does not affect
          the value yiedled by an iterator, the value when initializing the iterator
          is what it will use.
        * :py:exc:`StopDefiniteIterationError` is raised when a renderable with
          *definite* frame count raises :py:exc:`StopIteration` when rendering a frame.

    .. seealso::

       :py:meth:`Renderable.__iter__() <term_image.renderable.Renderable.__iter__>`
          Renderables are iterable

       :ref:`render-iterator-ext-api`
          :py:class:`RenderIterator`\\ 's Extension API
    """

    # Instance Attributes ======================================================

    loop: int
    """Iteration loop countdown

    * A negative integer, if iteration is infinite.
    * Otherwise, the current iteration loop countdown value.

      * Starts from the value of the *loops* constructor argument,
      * decreases by one upon rendering the first frame of every loop after the
        first,
      * and ends at zero after the iterator is exhausted.

    NOTE:
        Modifying this doesn't affect the iterator.
    """

    _cached: bool
    _closed: bool
    _finalize_data: bool
    _iterator: Generator[Frame, None, None]
    _loops: int
    _padding: Padding
    _padded_size: Size
    _render_args: RenderArgs
    _render_data: RenderData
    _renderable: Renderable
    _renderable_data: RenderableData

    # Special Methods ==========================================================

    def __init__(
        self,
        renderable: Renderable,
        render_args: RenderArgs | None = None,
        padding: Padding = ExactPadding(),
        loops: int = 1,
        cache: bool | int = 100,
    ) -> None:
        self._init(renderable, render_args, padding, loops, cache)
        self._iterator, self._padding = renderable._init_render_(
            self._iterate, render_args, padding, iteration=True, finalize=False
        )
        self._finalize_data = True
        next(self._iterator)

    def __del__(self) -> None:
        try:
            self.close()
        except AttributeError:
            pass

    def __iter__(self) -> Self:
        return self

    def __next__(self) -> Frame:
        try:
            return next(self._iterator)
        except StopIteration:
            self.close()
            raise StopIteration("Iteration has ended") from None
        except AttributeError:
            if self._closed:
                raise StopIteration("This iterator has been finalized") from None
            else:
                self.close()
                raise
        except Exception:
            self.close()
            raise

    def __repr__(self) -> str:
        return (
            f"<{type(self).__name__}: "
            f"type(renderable)={type(self._renderable).__name__}, "
            f"frame_count={self._renderable.frame_count}, loops={self._loops}, "
            f"loop={self.loop}, cached={self._cached}>"
        )

    # Public Methods ===========================================================

    def close(self) -> None:
        """Finalizes the iterator and releases resources used.

        NOTE:
            This method is automatically called when the iterator is exhausted or
            garbage-collected but it's recommended to call it manually if iteration
            is ended prematurely (i.e before the iterator itself is exhausted),
            especially if frames are cached.

            This method is safe for multiple invocations.
        """
        if not self._closed:
            self._iterator.close()
            del self._iterator
            if self._finalize_data:
                self._render_data.finalize()
            del self._render_data
            self._closed = True

    def seek(self, offset: int, whence: Seek = Seek.START) -> None:
        """Sets the frame to be rendered on the next iteration, without affecting
        the loop count.

        Args:
            offset: Frame offset (relative to *whence*).
            whence: Reference position for *offset*.

        Raises:
            FinalizedIteratorError: The iterator has been finalized.
            ValueError: *offset* is out of range.

        The value range for *offset* depends on the
        :py:attr:`~term_image.renderable.Renderable.frame_count` of the underlying
        renderable and *whence*:

        .. list-table:: *definite* frame count
           :align: left
           :header-rows: 1
           :width: 90%
           :widths: auto

           * - *whence*
             - Valid value range for *offset*

           * - :py:attr:`~term_image.renderable.Seek.START`
             - ``0`` <= *offset*
               < :py:attr:`~term_image.renderable.Renderable.frame_count`
           * - :py:attr:`~term_image.renderable.Seek.CURRENT`
             - -*next_frame_number* [#ri-nf]_ <= *offset*
               < :py:attr:`~term_image.renderable.Renderable.frame_count`
               - *next_frame_number*
           * - :py:attr:`~term_image.renderable.Seek.END`
             - -:py:attr:`~term_image.renderable.Renderable.frame_count` < *offset*
               <= ``0``

        .. list-table:: :py:attr:`~term_image.renderable.FrameCount.INDEFINITE` frame
           count
           :align: left
           :header-rows: 1
           :width: 90%
           :widths: auto

           * - *whence*
             - Valid value range for *offset*

           * - :py:attr:`~term_image.renderable.Seek.START`
             - ``0`` <= *offset*
           * - :py:attr:`~term_image.renderable.Seek.CURRENT`
             - *any value*
           * - :py:attr:`~term_image.renderable.Seek.END`
             - *offset* <= ``0``

        NOTE:
            If the underlying renderable has *definite* frame count, seek operations
            have **immeditate** effect. Hence, multiple consecutive seek operations,
            starting with any kind and followed by one or more with *whence* =
            :py:attr:`~term_image.renderable.Seek.CURRENT`, between any two
            consecutive renders have a **cumulative** effect. In particular, any seek
            operation with *whence* = :py:attr:`~term_image.renderable.Seek.CURRENT`
            is relative to the frame to be rendered next [#ri-nf]_.

            .. collapse:: Example

               >>> animated_renderable.frame_count
               10
               >>> render_iter = RenderIterator(animated_renderable)  # next = 0
               >>> render_iter.seek(5)  # next = 5
               >>> next(render_iter).number  # next = 5 + 1 = 6
               5
               >>> # cumulative
               >>> render_iter.seek(2, Seek.CURRENT)  # next = 6 + 2 = 8
               >>> render_iter.seek(-4, Seek.CURRENT)  # next = 8 - 4 = 4
               >>> next(render_iter).number  # next = 4 + 1 = 5
               4
               >>> # cumulative
               >>> render_iter.seek(7)  # next = 7
               >>> render_iter.seek(1, Seek.CURRENT)  # next = 7 + 1 = 8
               >>> render_iter.seek(-5, Seek.CURRENT)  # next = 8 - 5 = 3
               >>> next(render_iter).number  # next = 3 + 1 = 4
               3
               >>> # NOT cumulative
               >>> render_iter.seek(3, Seek.CURRENT)  # next = 4 + 3 = 7
               >>> render_iter.seek(2)  # next = 2
               >>> next(render_iter).number  # next = 2 + 1 = 3
               2

            On the other hand, if the underlying renderable has
            :py:attr:`~term_image.renderable.FrameCount.INDEFINITE` frame count, seek
            operations don't take effect **until the next render**. Hence, multiple
            consecutive seek operations between any two consecutive renders do **not**
            have a **cumulative** effect; rather, only **the last one** takes effect.
            In particular, any seek operation with *whence* =
            :py:attr:`~term_image.renderable.Seek.CURRENT` is relative to the frame
            after that which was rendered last.

            .. collapse:: Example

               >>> animated_renderable.frame_count is FrameCount.INDEFINITE
               True
               >>> # iterating normally without seeking
               >>> [frame.render_output for frame in animated_renderable]
               ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'A', ...]
               >>>
               >>> # Assuming the renderable implements all kinds of seek operations
               >>> render_iter = RenderIterator(animated_renderable)  # next = 0
               >>> render_iter.seek(5)  # next = 5
               >>> next(render_iter).render_output  # next = 5 + 1 = 6
               '5'
               >>> render_iter.seek(2, Seek.CURRENT)  # next = 6 + 2 = 8
               >>> render_iter.seek(-4, Seek.CURRENT)  # next = 6 - 4 = 2
               >>> next(render_iter).render_output  # next = 2 + 1 = 3
               '2'
               >>> render_iter.seek(7)  # next = 7
               >>> render_iter.seek(3, Seek.CURRENT)  # next = 3 + 3 = 6
               >>> next(render_iter).render_output  # next = 6 + 1 = 7
               '6'

            A renderable with :py:attr:`~term_image.renderable.FrameCount.INDEFINITE`
            frame count may not support/implement all kinds of seek operations or any
            at all. If the underlying renderable doesn't support/implement a given
            seek operation, the seek operation should simply have no effect on
            iteration i.e the next frame should be the one after that which was
            rendered last. See each :term:`render class` that implements
            :py:attr:`~term_image.renderable.FrameCount.INDEFINITE` frame count for
            the seek operations it supports and any other specific related details.
        """
        if self._closed:
            raise FinalizedIteratorError("This iterator has been finalized") from None

        frame_count = self._renderable.frame_count
        renderable_data = self._renderable_data
        if frame_count is FrameCount.INDEFINITE:
            if whence is Seek.START and offset < 0 or whence is Seek.END and offset > 0:
                raise arg_value_error_range("offset", offset, f"whence={whence.name}")
            renderable_data.update(frame_offset=offset, seek_whence=whence)
        else:
            frame = (
                offset
                if whence is Seek.START
                else (
                    renderable_data.frame_offset + offset
                    if whence is Seek.CURRENT
                    else frame_count + offset - 1
                )
            )
            if not 0 <= frame < frame_count:
                raise arg_value_error_range(
                    "offset",
                    offset,
                    (
                        f"whence={whence.name}, frame_count={frame_count}"
                        + (
                            f", next={renderable_data.frame_offset}"
                            if whence is Seek.CURRENT
                            else ""
                        )
                    ),
                )
            renderable_data.update(frame_offset=frame, seek_whence=Seek.START)

    def set_frame_duration(self, duration: int | FrameDuration) -> None:
        """Sets the frame duration.

        Args:
            duration: Frame duration (see
              :py:attr:`~term_image.renderable.Renderable.frame_duration`).

        Raises:
            FinalizedIteratorError: The iterator has been finalized.
            ValueError: *duration* is out of range.

        NOTE:
            Takes effect from the next [#ri-nf]_ rendered frame.
        """
        if self._closed:
            raise FinalizedIteratorError("This iterator has been finalized") from None

        if isinstance(duration, int) and duration <= 0:
            raise arg_value_error_range("duration", duration)

        self._renderable_data.duration = duration

    def set_padding(self, padding: Padding) -> None:
        """Sets the :term:`render output` padding.

        Args:
            padding: Render output padding.

        Raises:
            FinalizedIteratorError: The iterator has been finalized.

        NOTE:
            Takes effect from the next [#ri-nf]_ rendered frame.
        """
        if self._closed:
            raise FinalizedIteratorError("This iterator has been finalized") from None

        self._padding = (
            padding.resolve(get_terminal_size())
            if isinstance(padding, AlignedPadding) and padding.relative
            else padding
        )
        self._padded_size = padding.get_padded_size(self._renderable_data.size)

    def set_render_args(self, render_args: RenderArgs) -> None:
        """Sets the render arguments.

        Args:
            render_args: Render arguments.

        Raises:
            FinalizedIteratorError: The iterator has been finalized.
            IncompatibleRenderArgsError: Incompatible render arguments.

        NOTE:
            Takes effect from the next [#ri-nf]_ rendered frame.
        """
        if self._closed:
            raise FinalizedIteratorError("This iterator has been finalized") from None

        render_cls = type(self._renderable)
        self._render_args = (
            render_args
            if render_args.render_cls is render_cls
            # Validate compatibility (and convert, if compatible)
            else RenderArgs(render_cls, render_args)
        )

    def set_render_size(self, render_size: Size) -> None:
        """Sets the :term:`render size`.

        Args:
            render_size: Render size.

        Raises:
            FinalizedIteratorError: The iterator has been finalized.

        NOTE:
            Takes effect from the next [#ri-nf]_ rendered frame.
        """
        if self._closed:
            raise FinalizedIteratorError("This iterator has been finalized") from None

        self._renderable_data.size = render_size
        self._padded_size = self._padding.get_padded_size(render_size)

    # Extension methods ========================================================

    @classmethod
    def _from_render_data_(
        cls,
        renderable: Renderable,
        render_data: RenderData,
        render_args: RenderArgs | None = None,
        padding: Padding = ExactPadding(),
        *args: Any,
        finalize: bool = True,
        **kwargs: Any,
    ) -> Self:
        """Constructs an iterator with pre-generated render data.

        Args:
            renderable: An animated renderable.
            render_data: Render data.
            render_args: Render arguments.
            args: Other positional arguments accepted by the class constructor.
            finalize: Whether *render_data* is finalized along with the iterator.
            kwargs: Other keyword arguments accepted by the class constructor.

        Returns:
            A new iterator instance.

        Raises the same exceptions as the class constructor.

        NOTE:
            *render_data* may be modified by the iterator or the underlying renderable.
        """
        new = cls.__new__(cls)
        new._init(renderable, render_args, padding, *args, **kwargs)

        if render_data.render_cls is not type(renderable):
            raise arg_value_error_msg(
                "Invalid render data for renderable of type "
                f"{type(renderable).__name__!r}",
                render_data,
            )
        if render_data.finalized:
            raise ValueError("The render data has been finalized")
        if not render_data[Renderable].iteration:
            raise arg_value_error_msg("Invalid render data for iteration", render_data)

        if not (render_args and render_args.render_cls is type(renderable)):
            # Validate compatibility (and convert, if compatible)
            render_args = RenderArgs(type(renderable), render_args)

        new._padding = (
            padding.resolve(get_terminal_size())
            if isinstance(padding, AlignedPadding) and padding.relative
            else padding
        )
        new._iterator = new._iterate(render_data, render_args)
        new._finalize_data = finalize
        next(new._iterator)

        return new

    # Private Methods ==========================================================

    def _init(
        self,
        renderable: Renderable,
        render_args: RenderArgs | None = None,
        padding: Padding = ExactPadding(),
        loops: int = 1,
        cache: bool | int = 100,
    ) -> None:
        """Partially initializes an instance.

        Performs the part of the initialization common to all constructors.
        """
        if not renderable.animated:
            raise arg_value_error_msg("'renderable' is not animated", renderable)
        if not loops:
            raise arg_value_error("loops", loops)
        if False is not cache <= 0:
            raise arg_value_error_range("cache", cache)

        indefinite = renderable.frame_count is FrameCount.INDEFINITE
        self._closed = False
        self._renderable = renderable
        self.loop = self._loops = 1 if indefinite else loops
        self._cached = (
            False
            if indefinite
            else (
                cache
                # `isinstance` is much costlier on failure and `bool` cannot be
                # subclassed
                if type(cache) is bool
                else renderable.frame_count <= cache  # type: ignore[operator]
            )
        )

    def _iterate(
        self,
        render_data: RenderData,
        render_args: RenderArgs,
    ) -> Generator[Frame, None, None]:
        """Performs the actual render iteration operation."""
        # Instance init completion
        self._render_data = render_data
        self._render_args = render_args
        renderable_data: RenderableData
        self._renderable_data = renderable_data = render_data[Renderable]
        self._padded_size = self._padding.get_padded_size(renderable_data.size)

        # Setup
        renderable = self._renderable
        frame_count = renderable.frame_count
        if frame_count is FrameCount.INDEFINITE:
            frame_count = 1
        definite = frame_count > 1
        loop = self.loop
        CURRENT = Seek.CURRENT
        renderable_data.frame_offset = 0
        cache: list[tuple[Frame | None, Size, int | FrameDuration, RenderArgs]] | None
        cache = (
            [(None,) * 4] * frame_count  # type: ignore[list-item]
            if self._cached
            else None
        )

        # Initial dummy frame, yielded but unused by initializers.
        # Acts as a breakpoint between completion of instance init + iteration setup
        # and render iteration.
        yield DUMMY_FRAME

        # Render iteration
        frame_no = renderable_data.frame_offset * definite
        while loop:
            while frame_no < frame_count:
                if cache:
                    frame = (cache_entry := cache[frame_no])[0]
                    frame_details = cache_entry[1:]
                else:
                    frame = None

                if not frame or frame_details != (
                    renderable_data.size,
                    renderable_data.duration,
                    self._render_args,
                ):
                    # NOTE: Re-render is required even when only `duration` changes
                    # and the new value is *static* because frame duration may affect
                    # the render output of some renderables.
                    try:
                        frame = renderable._render_(render_data, self._render_args)
                    except StopIteration as exc:
                        if definite:
                            raise StopDefiniteIterationError(
                                f"{renderable!r} with definite frame count raised "
                                "`StopIteration` when rendering a frame"
                            ) from exc
                        self.loop = 0
                        return

                    if cache:
                        cache[frame_no] = (
                            frame,
                            renderable_data.size,
                            renderable_data.duration,
                            self._render_args,
                        )

                if self._padded_size != frame.render_size:
                    frame = Frame(
                        frame.number,
                        frame.duration,
                        self._padded_size,
                        self._padding.pad(frame.render_output, frame.render_size),
                    )

                if definite:
                    renderable_data.frame_offset += 1
                elif (
                    renderable_data.frame_offset
                    or renderable_data.seek_whence != CURRENT
                ):  # was seeked
                    renderable_data.update(frame_offset=0, seek_whence=CURRENT)

                yield frame

                if definite:
                    frame_no = renderable_data.frame_offset

            # INDEFINITE can never reach here
            frame_no = renderable_data.frame_offset = 0
            if loop > 0:  # Avoid infinitely large negative numbers
                self.loop = loop = loop - 1


# Exceptions ===================================================================


class RenderIteratorError(TermImageError):
    """Base exception class for errors specific to :py:class:`RenderIterator`."""


class FinalizedIteratorError(RenderIteratorError):
    """Raised when certain operations are attempted on a finalized iterator."""


class StopDefiniteIterationError(RenderIteratorError):
    """Raised when a renderable with *definite* frame count raises
    :py:exc:`StopIteration` when rendering a frame.
    """

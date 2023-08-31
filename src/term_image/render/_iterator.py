"""
.. The RenderIterator API
"""

from __future__ import annotations

__all__ = ("RenderIterator", "RenderIteratorError", "FinalizedIteratorError")

from typing import Generator

from ..exceptions import TermImageError
from ..geometry import Size
from ..padding import AlignedPadding, ExactPadding, Padding
from ..renderable import Frame, FrameCount, Renderable, RenderArgs, RenderData
from ..utils import (
    arg_type_error,
    arg_value_error,
    arg_value_error_msg,
    arg_value_error_range,
    get_terminal_size,
)


class RenderIterator:
    """Effeciently iterate over :term:`rendered` frames of an :term:`animated`
    renderable.

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

        cache: Determines if :term:`rendered` frames are cached. If the value is

          * ``True``, caching is enabled.
          * a positive integer greater than or equal to the frame count of
            *renderable*, caching is enabled.
          * otherwise (i.e ``False`` or a positive integer less than the frame count),
            caching is disabled.

          .. note::
            The value is ignored and taken to be ``False``, if *renderable* has
            :py:class:`~term_image.renderable.FrameCount.INDEFINITE` frame count.

    Raises:
        TypeError: An argument is of an inappropriate type.
        ValueError: An argument is of an appropriate type but has an
          unexpected/invalid value.
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

    .. seealso::

       :py:meth:`Renderable.__iter__() <term_image.renderable.Renderable.__iter__>`.
          Renderables are iterable.

       :ref:`render-iterator-ext-api`
          :py:class:`RenderIterator`\\ 's Extension API.
    """

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
        if not isinstance(renderable, Renderable):
            raise arg_type_error("renderable", renderable)
        if not renderable.animated:
            raise arg_value_error_msg("'renderable' is not animated", renderable)

        if render_args and not isinstance(render_args, RenderArgs):
            raise arg_type_error("render_args", render_args)

        if not isinstance(padding, Padding):
            raise arg_type_error("padding", padding)

        if not isinstance(loops, int):
            raise arg_type_error("loops", loops)
        if not loops:
            raise arg_value_error("loops", loops)

        if not isinstance(cache, int):  # `bool` is a subclass of `int`
            raise arg_type_error("cache", cache)
        if False is not cache <= 0:
            raise arg_value_error_range("cache", cache)

        indefinite = renderable.frame_count is FrameCount.INDEFINITE
        self._closed = False
        self._renderable = renderable
        self.loop = self._loops = 1 if indefinite else loops
        self._cached = (
            False
            if indefinite
            else cache
            if isinstance(cache, bool)
            else renderable.frame_count <= cache
        )

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

    def __iter__(self) -> RenderIterator:
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
        return "<{}: renderable={}, loops={}, loop={}, cached={}>".format(
            type(self).__name__,
            type(self._renderable).__name__,
            self._loops,
            self.loop,
            self._cached,
        )

    def close(self) -> None:
        """Finalizes the iterator and releases resources used.

        NOTE:
            This method is automatically called when the iterator is exhausted or
            garbage-collected but it's recommended to call it manually if iteration
            is ended prematurely (i.e before the iterator itself is exhausted),
            especially if frames are cached.

            This method is safe for multiple invokations.
        """
        if not self._closed:
            self._iterator.close()
            del self._iterator
            if self._finalize_data:
                self._render_data.finalize()
            del self._render_data
            self._closed = True

    def seek(self, offset: int) -> None:
        """Sets the frame to be yielded on the next iteration without affecting
        the loop count.

        Args:
            offset: Frame number; ``0`` <= *offset* < :py:attr:`renderable.frame_count
              <term_image.renderable.Renderable.frame_count>`.

        Raises:
            TypeError: An argument is of an inappropriate type.
            ValueError: An argument is of an appropriate type but has an
              unexpected/invalid value.
            FinalizedIteratorError: The iterator has been finalized.
        """
        if not isinstance(offset, int):
            raise arg_type_error("offset", offset)
        if self._renderable.frame_count is FrameCount.INDEFINITE:
            if offset:
                raise arg_value_error_msg(
                    "Non-zero offset is invalid because the underlying renderable has "
                    "INDEFINITE frame count",
                    offset,
                )
        elif not 0 <= offset < self._renderable.frame_count:
            raise arg_value_error_range(
                "offset", offset, f"frame_count={self._renderable.frame_count}"
            )

        try:
            self._render_data[Renderable].frame = offset
        except AttributeError:
            if self._closed:
                raise FinalizedIteratorError(
                    "This iterator has been finalized"
                ) from None
            raise

    def set_render_args(self, render_args: RenderArgs) -> None:
        """Sets the render arguments.

        Args:
            render_args: Render arguments.

        Raises:
            TypeError: An argument is of an inappropriate type.
            IncompatibleRenderArgsError: Incompatible render arguments.

        NOTE:
            Takes effect from the next rendered frame.
        """
        if not isinstance(render_args, RenderArgs):
            raise arg_type_error("render_args", render_args)

        self._render_args = RenderArgs(type(self._renderable), render_args)

    def set_padding(self, padding: Padding) -> None:
        """Sets the :term:`render output` padding.

        Args:
            padding: Render output padding.

        Raises:
            TypeError: An argument is of an inappropriate type.

        NOTE:
            Takes effect from the next rendered frame.
        """
        if not isinstance(padding, Padding):
            raise arg_type_error("padding", padding)

        self._padding = (
            padding.resolve(get_terminal_size())
            if isinstance(padding, AlignedPadding) and padding.relative
            else padding
        )
        self._padded_size = padding.get_padded_size(self._render_data[Renderable].size)

    def set_render_size(self, render_size: Size) -> None:
        """Sets the :term:`render size`.

        Args:
            render_size: Render size.

        Raises:
            TypeError: An argument is of an inappropriate type.

        NOTE:
            Takes effect from the next rendered frame.
        """
        if not isinstance(render_size, Size):
            raise arg_type_error("render_size", render_size)

        self._render_data[Renderable].size = render_size
        self._padded_size = self._padding.get_padded_size(render_size)

    @classmethod
    def _from_render_data_(
        cls,
        renderable: Renderable,
        render_data: RenderData,
        render_args: RenderArgs | None = None,
        padding: Padding = ExactPadding(),
        *args,
        finalize: bool = True,
        **kwargs,
    ) -> RenderIterator:
        """Constructs an iterator with pre-generated render data.

        Args:
            renderable: An animated renderable.
            render_data: Render data.
            render_args: Render arguments.
            args: Other positional arguments accepted by the class constructor.
            finalize: If ``True``, *render_data* is finalized along with the iterator.
              Otherwise, finalizing *render_data* is left to the caller of this method.
            kwargs: Other keyword arguments accepted by the class constructor.

        Returns:
            A new iterator instance.

        Raises the same exceptions as the class constructor.

        NOTE:
            *render_data* may be modified by the iterator or the underlying renderable.
        """
        new = cls.__new__(cls)
        new._init(renderable, render_args, padding, *args, **kwargs)

        if not isinstance(render_data, RenderData):
            raise arg_type_error("render_data", render_data)
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

        if not isinstance(finalize, bool):
            raise arg_type_error("finalize", finalize)

        render_args = RenderArgs(type(renderable), render_args)  # Validate and complete
        new._padding = (
            padding.resolve(get_terminal_size())
            if isinstance(padding, AlignedPadding) and padding.relative
            else padding
        )
        new._iterator = new._iterate(render_data, render_args)
        new._finalize_data = finalize
        next(new._iterator)

        return new

    def _iterate(
        self,
        render_data: RenderData,
        render_args: RenderArgs,
    ) -> Generator[Frame, None, None]:
        """Performs the actual render iteration operation."""
        # Instance init completion
        self._render_data = render_data
        self._render_args = render_args
        renderable_data = render_data[Renderable]
        self._padded_size = self._padding.get_padded_size(renderable_data.size)

        # Setup
        renderable = self._renderable
        frame_count = renderable.frame_count
        if frame_count is FrameCount.INDEFINITE:
            frame_count = 1
        definite = frame_count > 1
        loop = self.loop
        cache = [(None,) * 4] * frame_count if self._cached else None

        yield Frame(0, None, Size(1, 1), " ")

        # Render iteration
        frame_no = renderable_data.frame * definite
        while loop:
            while frame_no < frame_count:
                frame, *frame_details = cache[frame_no] if cache else (None,)
                if not frame or frame_details != [
                    renderable_data.size,
                    self._render_args,
                    self._padding,
                ]:
                    try:
                        frame = renderable._render_(render_data, self._render_args)
                    except StopIteration:
                        if not definite:
                            self.loop = 0
                            return
                        raise
                    if self._padded_size != frame.size:
                        frame = Frame(
                            frame.number,
                            frame.duration,
                            self._padded_size,
                            self._padding.pad(frame.render, frame.size),
                        )
                    if cache:
                        cache[frame_no] = (
                            frame,
                            renderable_data.size,
                            self._render_args,
                            self._padding,
                        )
                if definite:
                    renderable_data.frame += 1
                elif renderable_data.frame:  # reset after seek
                    renderable_data.frame = 0

                yield frame

                if definite:
                    frame_no = renderable_data.frame

            # INDEFINITE can never reach here
            frame_no = renderable_data.frame = 0
            if loop > 0:  # Avoid infinitely large negative numbers
                self.loop = loop = loop - 1


class RenderIteratorError(TermImageError):
    """Base exception class for errors specific to :py:class:`RenderIterator`."""


class FinalizedIteratorError(RenderIteratorError):
    """Raised if certain operations are attempted on a finalized itterator."""

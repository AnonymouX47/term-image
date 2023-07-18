"""
.. The RenderIterator API
"""

from __future__ import annotations

__all__ = ("RenderIterator",)

from typing import Generator

from ..exceptions import RenderIteratorError
from ..geometry import Size
from ..renderable import (
    Frame,
    FrameCount,
    Renderable,
    RenderArgs,
    RenderData,
    RenderFormat,
)
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
        render_fmt: Render formatting arguments. Same as for
          :py:meth:`Renderable.render() <term_image.renderable.Renderable.render>`.
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
            If *loops* equals 1 (one), caching is disabled.

    Raises:
        TypeError: An argument is of an inappropriate type.
        ValueError: An argument is of an appropriate type but has an
          unexpected/invalid value.
        term_image.exceptions.RenderArgsError: Incompatible render arguments.

    The iterator yields a :py:class:`~term_image.renderable.Frame` instance on every
    iteration.

    NOTE:
        * Seeking the underlying renderable
          (via :py:meth:`Renderable.seek() <term_image.renderable.Renderable.seek>`)
          does not affect an iterator, use :py:meth:`RenderIterator.seek` instead.
          Likewise, the iterator does not modify the underlying renderable's current
          frame number.
        * Changes to the underlying renderable's
          :py:attr:`~term_image.renderable.Renderable.render_size` does not affect the
          an iterator's render outputs, use :py:meth:`set_render_size` instead.
        * Changes to the underlying renderable's
          :py:attr:`~term_image.renderable.Renderable.frame_duration` does not affect
          the value yiedled by an iterator, the value when initializing the iterator
          is what it will use.

    .. seealso::
        :py:meth:`Renderable.__iter__() <term_image.renderable.Renderable.__iter__>`.
    """

    def __new__(
        cls,
        renderable: Renderable,
        render_args: RenderArgs | None = None,
        render_fmt: RenderFormat = RenderFormat(1, 1),
        loops: int = 1,
        cache: bool | int = 100,
    ) -> None:
        if not isinstance(renderable, Renderable):
            raise arg_type_error("renderable", renderable)
        if not renderable.animated:
            raise arg_value_error_msg("'renderable' is not animated", renderable)

        if render_args and not isinstance(render_args, RenderArgs):
            raise arg_type_error("render_args", render_args)

        if not isinstance(render_fmt, RenderFormat):
            raise arg_type_error("render_fmt", render_fmt)

        if not isinstance(loops, int):
            raise arg_type_error("loops", loops)
        if not loops:
            raise arg_value_error("loops", loops)

        if not isinstance(cache, int):  # `bool` is a subclass of `int`
            raise arg_type_error("cache", cache)
        if False is not cache <= 0:
            raise arg_value_error_range("cache", cache)

        new = super().__new__(cls)

        new._closed = False
        new._renderable = renderable
        new._loops = 1 if renderable.frame_count is FrameCount.INDEFINITE else loops
        new._cache = (
            False
            if new._loops == 1
            else cache
            if isinstance(cache, bool)
            else renderable.frame_count <= cache
        )

        return new

    def __init__(
        self,
        renderable: Renderable,
        render_args: RenderArgs | None = None,
        render_fmt: RenderFormat = RenderFormat(1, 1),
        loops: int = 1,
        cache: bool | int = 100,
    ) -> None:
        self._iterator, _, self._render_fmt = renderable._init_render_(
            self._iterate, render_args, render_fmt, iteration=True, finalize=False
        )
        self._finalize_data = True
        next(self._iterator)

    def __del__(self) -> None:
        self.close()

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
        return "{}({!r}, loops={}, cache={}, loop={})".format(
            type(self).__name__,
            self._renderable,
            self._loops,
            self._cache,
            self.loop,
        )

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

    def close(self) -> None:
        """Finalizes the iterator and releases resources used.

        NOTE:
            This method is automatically called when the iterator is exhausted or
            garbage-collected but it's recommended to call it manually if iteration
            is ended prematurely (i.e before the iterator itself is exhausted),
            especially if frames are cached.
        """
        try:
            self._iterator.close()
            del self._iterator
            if self._finalize_data:
                self._render_data.finalize()
            del self._render_data
        except AttributeError:
            pass
        finally:
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
            term_image.exceptions.RenderIteratorError: The iterator has been finalized.
        """
        if not isinstance(offset, int):
            raise arg_type_error("offset", offset)
        if self._renderable.frame_count is FrameCount.INDEFINITE:
            if offset:
                raise arg_value_error_msg(
                    "Non-zero offset is invalid for a renderable with "
                    "INDEFINITE frame count",
                    offset,
                )
        elif not 0 <= offset < self._renderable.frame_count:
            raise arg_value_error_range(
                "offset", offset, f"frame_count={self._renderable.frame_count}"
            )

        try:
            self._render_data.frame = offset
        except AttributeError:
            if self._closed:
                raise RenderIteratorError("This iterator has been finalized") from None
            raise

    def set_render_args(self, render_args: RenderArgs) -> None:
        """Sets the render arguments used to render frames,
        starting with the next rendered frame.

        Args:
            render_args: Render arguments.

        Raises:
            TypeError: An argument is of an inappropriate type.
            term_image.exceptions.RenderArgsError: Incompatible render arguments.
        """
        if not isinstance(render_args, RenderArgs):
            raise arg_type_error("render_args", render_args)

        self._render_args = RenderArgs(type(self._renderable), render_args)

    def set_render_fmt(self, render_fmt: RenderFormat) -> None:
        """Sets the render formatting arguments used to format frame render outputs,
        starting with the next rendered frame.

        Args:
            render_fmt: Render formatting arguments. Same as for
              :py:meth:`Renderable.render() <term_image.renderable.Renderable.render>`.

        Raises:
            TypeError: An argument is of an inappropriate type.
        """
        if not isinstance(render_fmt, RenderFormat):
            raise arg_type_error("render_fmt", render_fmt)

        self._render_fmt = render_fmt = render_fmt.absolute(get_terminal_size())
        self._formatted_size = render_fmt.get_formatted_size(self._render_data.size)

    def set_render_size(self, size: Size) -> None:
        """Sets the frame :term:`render size`, starting with the next rendered frame.

        Args:
            size: Render size.

        Raises:
            TypeError: An argument is of an inappropriate type.
            ValueError: An argument is of an appropriate type but has an
              unexpected/invalid value.
        """
        if not isinstance(size, Size):
            raise arg_type_error("size", size)
        if not size.width > 0 < size.height:
            raise arg_value_error_range("size", size)

        self._render_data.size = size
        self._formatted_size = self._render_fmt.get_formatted_size(size)

    @classmethod
    def _from_render_data_(
        cls,
        renderable: Renderable,
        render_data: RenderData,
        render_args: RenderArgs | None = None,
        render_fmt: RenderFormat = RenderFormat(1, 1),
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
            *render_data* may be modified by the iterator. Keep this in mind if
            *finalize* if ``False``.
        """
        if not isinstance(render_data, RenderData):
            raise arg_type_error("render_data", render_data)
        if not render_data.iteration:
            raise arg_value_error_msg(
                "Invalid render data for an iterator", render_data
            )

        render_args = RenderArgs(type(renderable), render_args)  # Validate and complete
        new = cls.__new__(cls, renderable, render_args, render_fmt, *args, **kwargs)
        new._render_fmt = render_fmt.absolute(get_terminal_size())
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
        # complete instance init
        self.loop = loop = self._loops
        self._render_data = render_data
        self._render_args = render_args
        self._formatted_size = self._render_fmt.get_formatted_size(render_data.size)

        renderable = self._renderable
        frame_count = renderable.frame_count
        if frame_count is FrameCount.INDEFINITE:
            frame_count = 1
        definite = frame_count > 1
        cache = self._cache and [None] * frame_count

        yield Frame(0, None, Size(0, 0), "")

        frame_no = render_data.frame * definite
        while loop:
            while frame_no < frame_count:
                try:
                    frame = renderable._render_(render_data, self._render_args)
                except StopIteration:
                    if not definite:
                        self.loop = 0
                        return
                    raise
                if self._formatted_size != frame.size:
                    frame = Frame(
                        frame.number,
                        frame.duration,
                        self._formatted_size,
                        renderable._format_render_(
                            frame.render, frame.size, self._render_fmt
                        ),
                    )
                if cache:
                    cache[frame_no] = frame

                if definite:
                    render_data.frame += 1
                elif render_data.frame:  # reset after seek
                    render_data.frame = 0

                yield frame

                if definite:
                    frame_no = render_data.frame

            # INDEFINITE can never reach here
            frame_no = render_data.frame = 0
            if loop > 0:  # Avoid infinitely large negative numbers
                self.loop = loop = loop - 1
            if cache:
                break

        # INDEFINITE can never reach here
        while loop:
            while frame_no < frame_count:
                frame = cache[frame_no]
                if not frame:  # Skipped by seek in uncached loop
                    frame = renderable._render_(render_data, self._render_args)
                    if self._formatted_size != frame.size:
                        frame = Frame(
                            frame.number,
                            frame.duration,
                            self._formatted_size,
                            renderable._format_render_(
                                frame.render, frame.size, self._render_fmt
                            ),
                        )
                    cache[frame_no] = frame

                render_data.frame += 1
                yield frame
                frame_no = render_data.frame

            frame_no = render_data.frame = 0
            if loop > 0:  # Avoid infinitely large negative numbers
                self.loop = loop = loop - 1

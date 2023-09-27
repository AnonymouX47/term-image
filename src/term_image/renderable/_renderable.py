"""
.. Core of the Renderable API
"""

from __future__ import annotations

__all__ = ("Renderable",)

import sys
from abc import ABCMeta, abstractmethod
from time import perf_counter_ns, sleep
from types import MappingProxyType
from typing import Any, Callable, ClassVar, TextIO

import term_image

from .. import geometry
from ..ctlseqs import HIDE_CURSOR, SHOW_CURSOR, cursor_down, cursor_forward, cursor_up
from ..padding import AlignedPadding, ExactPadding, Padding
from ..utils import arg_type_error, arg_value_error_range, get_terminal_size
from . import _types
from ._enum import FrameCount, FrameDuration, Seek
from ._exceptions import (
    IndefiniteSeekError,
    NonAnimatedFrameDurationError,
    RenderableError,
    RenderSizeOutofRangeError,
)
from ._types import Frame, RenderArgs, RenderData

try:
    import termios
except ImportError:
    OS_IS_UNIX = False
else:
    OS_IS_UNIX = True


class RenderableMeta(ABCMeta):
    """Base metaclass of the Renderable API.

    Implements certain internal/private aspects of the API.
    """

    def __new__(cls, name, bases, namespace, _base: bool = False, **kwargs):
        if not _base and not any(issubclass(base, Renderable) for base in bases):
            raise RenderableError(f"{name!r} is not a subclass of 'Renderable'")

        try:
            args_cls = namespace["Args"]
        except KeyError:
            args_cls = None

        if args_cls is not None:
            if not isinstance(args_cls, type):
                raise arg_type_error(f"'{name}.Args'", args_cls)
            if (
                not issubclass(args_cls, RenderArgs.Namespace)
                or args_cls is RenderArgs.Namespace
            ):
                raise RenderableError(
                    f"'{name}.Args' is not a strict subclass of 'RenderArgs.Namespace'"
                )
            if args_cls._RENDER_CLS:
                raise RenderableError(
                    f"'{name}.Args' is already associated with render class "
                    f"{args_cls._RENDER_CLS.__name__!r}"
                )

        try:
            data_cls = namespace["_Data_"]
        except KeyError:
            data_cls = None

        if data_cls is not None:
            if not isinstance(data_cls, type):
                raise arg_type_error(f"'{name}._Data_'", data_cls)
            if (
                not issubclass(data_cls, RenderData.Namespace)
                or data_cls is RenderData.Namespace
            ):
                raise RenderableError(
                    f"'{name}._Data_' is not a strict subclass of "
                    "'RenderData.Namespace'"
                )
            if data_cls._RENDER_CLS:
                raise RenderableError(
                    f"'{name}._Data_' is already associated with render class "
                    f"{data_cls._RENDER_CLS.__name__!r}"
                )

        new_cls = super().__new__(cls, name, bases, namespace, **kwargs)

        if args_cls:
            args_cls._RENDER_CLS = new_cls
        else:
            new_cls.Args = None

        if data_cls:
            data_cls._RENDER_CLS = new_cls
        else:
            new_cls._Data_ = None

        if _base:  # Renderable
            all_default_args = {}
            render_data_mro = {new_cls: new_cls._Data_}
            all_exported_descendant_attrs = frozenset()
        else:
            all_default_args = {new_cls: args_cls()} if args_cls else {}
            render_data_mro = {new_cls: data_cls} if data_cls else {}
            all_exported_descendant_attrs = set()  # remove duplicates

            for mro_cls in new_cls.__mro__:
                if not issubclass(mro_cls, Renderable):
                    continue

                if mro_cls is not new_cls:
                    if mro_cls.Args:
                        all_default_args[mro_cls] = mro_cls._ALL_DEFAULT_ARGS[mro_cls]
                    if mro_cls._Data_:
                        render_data_mro[mro_cls] = mro_cls._RENDER_DATA_MRO[mro_cls]
                try:
                    all_exported_descendant_attrs.update(
                        mro_cls.__dict__["_EXPORTED_DESCENDANT_ATTRS_"]
                    )
                except KeyError:
                    pass

        new_cls._ALL_DEFAULT_ARGS = MappingProxyType(all_default_args)
        new_cls._RENDER_DATA_MRO = MappingProxyType(render_data_mro)
        new_cls._ALL_EXPORTED_ATTRS = tuple(
            all_exported_descendant_attrs.union(namespace.get("_EXPORTED_ATTRS_", ()))
        )

        return new_cls


class Renderable(metaclass=RenderableMeta, _base=True):
    """A renderable.

    Args:
        frame_count: Number of frames. If it's a

          * positive integer, the number of frames is as given.
          * :py:class:`~term_image.renderable.FrameCount` enum member, see the
            member's description.

          If equal to 1 (one), the renderable is non-animated.
          Otherwise, it is animated.

        frame_duration: The duration of a frame. If it's a

          * positive integer, it implies a static duration (in **milliseconds**)
            i.e the same duration applies to every frame.
          * :py:class:`~term_image.renderable.FrameDuration` enum member, see the
            member's description.

          This argument is ignored if *frame_count* equals 1 (one)
          i.e the renderable is non-animated.

    Raises:
        TypeError: An argument is of an inappropriate type.
        ValueError: An argument is of an appropriate type but has an
          unexpected/invalid value.

    ATTENTION:
        This is an abstract base class. Hence, only **concrete** subclasses can be
        instantiated.

    .. seealso::

       :ref:`renderable-ext-api`
          :py:class:`Renderable`\\ 's Extension API
    """

    # Class Attributes =========================================================

    _EXPORTED_ATTRS_: ClassVar[tuple[str]]
    """Exported attributes.

    This specifies class attributes defined by the class (not a parent) on itself
    **but not** its subclasses which should be exported to definitions of the class
    in subprocesses.

    These attributes are typically assigned using ``__class__.*`` within methods.

    NOTE:
        * Defining this is optional.
        * The attributes are exported for a class if and only if they are defined
          on that class when starting a subprocess.
        * The attributes are exported only for subprocesses started via
          :py:class:`multiprocessing.Process`.

    TIP:
        This can be used to export "private" attributes of the class across
        subprocesses.
    """

    _EXPORTED_DESCENDANT_ATTRS_: ClassVar[tuple[str]]
    """Exported :term:`descendant` attributes.

    This specifies class attributes defined by the class (not a parent) on itself
    **and** its subclasses (i.e :term:`descendant` attributes) which should be exported
    to definitions of the class and its subclasses in subprocesses.

    These attributes are typically assigned using ``cls.*`` within class methods.

    This extends the exported descendant attributes of parent classes i.e all
    exported descendant attributes of a class are also exported for its subclasses.

    NOTE:
        * Defining this is optional.
        * The attributes are exported for a class if and only if they are defined
          on that class when starting a subprocess.
        * The attributes are exported only for subprocesses started via
          :py:class:`multiprocessing.Process`.

    TIP:
        This can be used to export "private" :term:`descendant` attributes of the
        class across subprocesses.
    """

    # Instance Attributes ======================================================

    animated: bool
    """``True`` if the renderable is :term:`animated`. Otherwise, ``False``."""

    # Special Methods ==========================================================

    def __init__(
        self,
        frame_count: int | FrameCount,
        frame_duration: int | FrameDuration,
    ) -> None:
        if isinstance(frame_count, int):
            if frame_count < 1:
                raise arg_value_error_range("frame_count", frame_count)
        elif not isinstance(frame_count, FrameCount):
            raise arg_type_error("frame_count", frame_count)

        if frame_count == 1:
            self.__frame_duration = None
        else:
            if isinstance(frame_duration, int):
                if frame_duration <= 0:
                    raise arg_value_error_range("frame_duration", frame_duration)
            elif not isinstance(frame_duration, FrameDuration):
                raise arg_type_error("frame_duration", frame_duration)

            self.__frame_duration = frame_duration

        self.animated = frame_count != 1
        self.__frame_count = frame_count
        self.__frame = 0

    def __iter__(self) -> term_image.render.RenderIterator:
        """Returns a render iterator.

        Returns:
            A render iterator (with frame caching disabled and all other optional
            arguments to :py:class:`~term_image.render.RenderIterator` being the
            default values).

        Raises:
            ValueError: The renderable is non-animated.

        :term:`Animated` renderables are iterable i.e they can be used with various
        means of iteration such as the ``for`` statement and iterable unpacking.
        """
        from term_image.render import RenderIterator

        return RenderIterator(self, cache=False)

    def __repr__(self) -> str:
        return f"<{type(self).__name__}: frame_count={self.__frame_count}>"

    def __str__(self) -> str:
        """:term:`Renders` the current frame with default arguments and no padding.

        Returns:
            The frame :term:`render output`.

        Raises:
            RenderError: An error occured during :term:`rendering`.
        """
        return self._init_render_(self._render_)[0].render_output

    # Properties ===============================================================

    @property
    def frame_count(self) -> int | FrameCount:
        """Frame count

        GET:
            Returns either

            * the number of frames the renderable has, or
            * :py:attr:`~term_image.renderable.FrameCount.INDEFINITE`.
        """
        if self.__frame_count is FrameCount.POSTPONED:
            self.__frame_count = self._get_frame_count_()

        return self.__frame_count

    @property
    def frame_duration(self) -> int | FrameDuration | None:
        """Frame duration

        GET:
            Returns

            * ``None``, if the renderable is non-animated.
            * Otherwise,

              * A static duration (in **milliseconds**) i.e the same duration applies
                to every frame, or
              * :py:attr:`~term_image.renderable.FrameDuration.DYNAMIC`.

        SET:
            If the renderable is

            * :term:`animated` and the value is

              * a positive integer, it implies a static duration (in **milliseconds**)
                i.e the same duration applies to every frame.
              * :py:attr:`~term_image.renderable.FrameDuration.DYNAMIC`, see the
                enum member's description.

            * non-animated,
              :py:class:`~term_image.renderable.NonAnimatedFrameDurationError`
              is raised.
        """
        return self.__frame_duration

    @frame_duration.setter
    def frame_duration(self, duration: int | FrameDuration) -> None:
        if not self.animated:
            raise NonAnimatedFrameDurationError(
                "Cannot set frame duration for a non-animated renderable"
            )

        if isinstance(duration, int):
            if duration <= 0:
                raise arg_value_error_range("frame_duration", duration)
        elif not isinstance(duration, FrameDuration):
            raise arg_type_error("frame_duration", duration)

        self.__frame_duration = duration

    @property
    def render_size(self) -> geometry.Size:
        """:term:`Render size`

        GET:
            Returns the size of the renderable's :term:`render output`.
        """
        return self._get_render_size_()

    # Public Methods ===========================================================

    def draw(
        self,
        render_args: RenderArgs | None = None,
        padding: Padding = AlignedPadding(0, -2),
        *,
        animate: bool = True,
        loops: int = -1,
        cache: bool | int = 100,
        check_size: bool = True,
        allow_scroll: bool = False,
        hide_cursor: bool = True,
        echo_input: bool = False,
    ) -> None:
        """Draws the current frame or an animation to standard output.

        Args:
            render_args: Render arguments.
            padding: :term:`Render output` padding.
            animate: Whether to enable animation for :term:`animated` renderables.
              If disabled, only the current frame is drawn.
            loops: See :py:class:`~term_image.render.RenderIterator`
              (applies to **animations only**).
            cache: See :py:class:`~term_image.render.RenderIterator`.
              (applies to **animations only**).
            check_size: Whether to validate the padded :term:`render size` of
              **non-animations**.
            allow_scroll: Whether to validate the padded :term:`render height` of
              **non-animations**. Ignored if *check_size* is ``False``.
            hide_cursor: Whether to hide the cursor **while drawing**.
            echo_input: Whether to display input **while drawing** (applies on **Unix
              only**).

              .. note::
                 * If disabled (default), input is not read/consumed, it's just not
                   displayed.
                 * If enabled, echoed input may affect cursor positioning and
                   therefore, the output (especially for animations).

        Raises:
            TypeError: An argument is of an inappropriate type.
            RenderSizeOutofRangeError: The padded :term:`render size` can not fit into
              the :term:`terminal size`.
            IncompatibleRenderArgsError: Incompatible render arguments.
            RenderError: An error occured during :term:`rendering`.

        If *check_size* is ``True`` (or it's an animation),

        * the padded :term:`render width` must not be greater than the
          :term:`terminal width`.
        * and *allow_scroll* is ``False`` (or it's an animation), the padded
          :term:`render height` must not be greater than the :term:`terminal height`.

        NOTE:
            * *hide_cursor* and *echo_input* apply if and only if the output stream
              is connected to a terminal.
            * For animations (i.e animated renderables with *animate* = ``True``),
              the padded :term:`render size` is always validated.
            * Animations with **definite** frame count, **by default**, are infinitely
              looped but can be terminated with :py:data:`~signal.SIGINT`
              (``CTRL + C``), **without** raising :py:class:`KeyboardInterrupt`.
        """
        if render_args and not isinstance(render_args, RenderArgs):
            raise arg_type_error("render_args", render_args)
        if not isinstance(padding, Padding):
            raise arg_type_error("padding", padding)
        if self.animated and not isinstance(animate, bool):
            raise arg_type_error("animate", animate)

        # Validation of *loops* and *cache* is delegated to `RenderIterator`.

        if not isinstance(check_size, bool):
            raise arg_type_error("check_size", check_size)
        if not isinstance(allow_scroll, bool):
            raise arg_type_error("allow_scroll", allow_scroll)

        animation = self.animated and animate
        output = sys.stdout
        not_echo_input = OS_IS_UNIX and not echo_input and output.isatty()
        hide_cursor = hide_cursor and output.isatty()

        # Validate size and get render data
        (render_data, render_args), padding = self._init_render_(
            lambda *args: args,
            render_args,
            padding,
            iteration=animation,
            finalize=False,
            check_size=animation or check_size,
            allow_scroll=not animation and allow_scroll,
        )

        if not_echo_input:
            output_fd = output.fileno()
            old_attr = termios.tcgetattr(output_fd)
            new_attr = termios.tcgetattr(output_fd)
            new_attr[3] &= ~termios.ECHO
        try:
            if hide_cursor:
                output.write(HIDE_CURSOR)
            if not_echo_input:
                termios.tcsetattr(output_fd, termios.TCSAFLUSH, new_attr)

            if animation:
                self._animate_(render_data, render_args, padding, loops, cache, output)
            else:
                frame = self._render_(render_data, render_args)
                padded_size = padding.get_padded_size(frame.render_size)
                render = (
                    frame.render_output
                    if frame.render_size == padded_size
                    else padding.pad(frame.render_output, frame.render_size)
                )
                try:
                    output.write(render)
                    output.flush()
                except KeyboardInterrupt:
                    self._handle_interrupted_draw_(render_data, render_args)
                    raise
        finally:
            output.write("\n")
            if hide_cursor:
                output.write(SHOW_CURSOR)
            output.flush()
            if not_echo_input:
                termios.tcsetattr(output_fd, termios.TCSANOW, old_attr)
            render_data.finalize()

    def render(
        self,
        render_args: RenderArgs | None = None,
        padding: Padding = ExactPadding(),
    ) -> Frame:
        """:term:`Renders` the current frame.

        Args:
            render_args: Render arguments.
            padding: :term:`Render output` padding.

        Returns:
            The rendered frame.

        Raises:
            TypeError: An argument is of an inappropriate type.
            IncompatibleRenderArgsError: Incompatible render arguments.
            RenderError: An error occured during :term:`rendering`.
        """
        if render_args and not isinstance(render_args, RenderArgs):
            raise arg_type_error("render_args", render_args)
        if not isinstance(padding, Padding):
            raise arg_type_error("padding", padding)

        frame, padding = self._init_render_(self._render_, render_args, padding)
        padded_size = padding.get_padded_size(frame.render_size)

        return (
            frame
            if frame.render_size == padded_size
            else Frame(
                frame.number,
                frame.duration,
                padded_size,
                padding.pad(frame.render_output, frame.render_size),
            )
        )

    def seek(self, offset: int, whence: Seek = Seek.START) -> int:
        """Sets the current frame number.

        Args:
            offset: Frame offset (relative to *whence*).
            whence: Reference position for *offset*.

        Returns:
            The new current frame number.

        Raises:
            IndefiniteSeekError: The renderable has
              :py:attr:`~term_image.renderable.FrameCount.INDEFINITE` frame count.
            TypeError: An argument is of an inappropriate type.
            ValueError: *offset* is out of range.

        The value range for *offset* depends on *whence*:

        .. list-table::
           :align: left
           :header-rows: 1
           :widths: auto

           * - *whence*
             - Valid value range for *offset*

           * - :py:attr:`~term_image.renderable.Seek.START`
             - ``0`` <= *offset* < :py:attr:`frame_count`
           * - :py:attr:`~term_image.renderable.Seek.CURRENT`
             - -:py:meth:`tell` <= *offset* < :py:attr:`frame_count` - :py:meth:`tell`
           * - :py:attr:`~term_image.renderable.Seek.END`
             - -:py:attr:`frame_count` < *offset* <= ``0``
        """
        frame_count = self.frame_count

        if frame_count is FrameCount.INDEFINITE:
            raise IndefiniteSeekError(
                "Cannot seek a renderable with INDEFINITE frame count"
            )
        if not isinstance(offset, int):
            raise arg_type_error("offset", offset)

        frame = (
            offset
            if whence is Seek.START
            else self.__frame + offset
            if whence is Seek.CURRENT
            else frame_count + offset - 1
        )
        if not 0 <= frame < frame_count:
            raise arg_value_error_range(
                "offset",
                offset,
                (
                    f"whence={whence.name}, frame_count={frame_count}"
                    + (f", current={self.__frame}" if whence is Seek.CURRENT else "")
                ),
            )
        self.__frame = frame

        return frame

    def tell(self) -> int:
        """Returns the current frame number.

        Returns:
            Zero, if the renderable is non-animated or has
            :py:attr:`~term_image.renderable.FrameCount.INDEFINITE` frame count.
            Otherwise, the current frame number.
        """
        return self.__frame

    # Extension methods ========================================================

    def _animate_(
        self,
        render_data: RenderData,
        render_args: RenderArgs,
        padding: Padding,
        loops: int,
        cache: bool | int,
        output: TextIO,
    ) -> None:
        """Animates frames of a renderable.

        Args:
            render_data: Render data.
            render_args: Render arguments associated with the renderable's class.
            output: The text I/O stream to which rendered frames will be written.

        All other parameters are the same as for :py:meth:`draw`, except that
        *padding* must have **absolute** dimensions if it's an instance of
        :py:class:`~term_image.padding.AlignedPadding`.

        This is called by :py:meth:`draw` for animations.

        NOTE:
            * The base implementation does not finalize *render_data*.
            * :term:`Render size` validation is expected to have been performed by
              the caller.
            * When called by :py:meth:`draw` (at least, the base implementation),
              *loops* and *cache* wouldn't have been validated.
        """
        from term_image.render import RenderIterator

        width, height = render_data[__class__].size
        pad_left, _, _, pad_bottom = padding._get_exact_dimensions_(
            render_data[__class__].size
        )
        render_iter = RenderIterator._from_render_data_(
            self,
            render_data,
            render_args,
            padding,
            loops,
            False if loops == 1 else cache,
            finalize=False,
        )
        cursor_to_bottom = cursor_down(height + pad_bottom - 1)
        cursor_to_next_render_line = f"\n{cursor_forward(pad_left)}"
        cursor_to_render_top_left = (
            f"\r{cursor_up(height - 1)}{cursor_forward(pad_left)}"
        )
        write = output.write
        flush = output.flush

        try:
            # first frame
            try:
                frame = next(render_iter)
            except StopIteration:  # `INDEFINITE` frame count
                return

            try:
                write(frame.render_output)
            except KeyboardInterrupt:
                self._handle_interrupted_draw_(render_data, render_args)
                return
            else:
                write(
                    f"\r{cursor_up(height + pad_bottom - 1)}{cursor_forward(pad_left)}"
                )
            finally:
                flush()

            # Padding has been drawn with the first frame, only the actual render is
            # needed henceforth.
            render_iter.set_padding(ExactPadding())

            # render next frame during previous frame's duration
            duration_ms = frame.duration
            start_ns = perf_counter_ns()

            for frame in render_iter:  # Render next frame
                # left-over of previous frame's duration
                sleep(
                    max(0, duration_ms * 10**6 - (perf_counter_ns() - start_ns))
                    / 10**9
                )

                # clear previous frame, if necessary
                self._clear_frame_(render_data, render_args, pad_left + 1, output)

                # draw next frame
                try:
                    write(frame.render_output.replace("\n", cursor_to_next_render_line))
                    write(cursor_to_render_top_left)
                    flush()
                except KeyboardInterrupt:
                    self._handle_interrupted_draw_(render_data, render_args)
                    return

                # render next frame during previous frame's duration
                start_ns = perf_counter_ns()
                duration_ms = frame.duration

            # left-over of last frame's duration
            sleep(
                max(0, duration_ms * 10**6 - (perf_counter_ns() - start_ns)) / 10**9
            )
        except KeyboardInterrupt:
            pass
        finally:
            render_iter.close()
            # Move the cursor to the last line to prevent "overlayed" output in a
            # terminal
            write(cursor_to_bottom)
            flush()

    def _clear_frame_(
        self,
        render_data: RenderData,
        render_args: RenderArgs,
        cursor_x: int,
        output: TextIO,
    ) -> None:
        """Clears the previous frame of an animation, if necessary.

        Args:
            render_data: Render data.
            render_args: Render arguments.
            cursor_x: Column/horizontal position of the cursor at the point of calling
              this method.

              .. note:: The position is **1-based** i.e the leftmost column on the
                 screen is at position 1 (one).

            output: The text I/O stream to which frames of the animation are being
              written.

        Called by the base implementation of :py:meth:`_animate_` just before drawing
        the next frame of an animation.

        Upon calling this method, the cursor should be positioned at the top-left-most
        cell of the region occupied by the frame render output on the terminal screen.

        Upon return, ensure the cursor is at the same position it was at the point of
        calling this method (at least logically, since *output* shouldn't be flushed
        yet).

        The base implementation does nothing.

        NOTE:
            * This is required only if drawing the next frame doesn't inherently
              overwrite the previous frame.
            * This is only meant (and should only be used) as a last resort since
              clearing the previous frame before drawing the next may result in
              visible flicker.
            * Ensure whatever this method does doesn't result in the screen being
              scrolled.

        TIP:
            To reduce flicker, it's advisable to **not** flush *output*. It will be
            flushed after writing the next frame.
        """

    @classmethod
    def _finalize_render_data_(cls, render_data: RenderData) -> None:
        """Finalizes render data.

        Args:
            render_data: Render data.

        Typically, an overriding method should

        * finalize the data generated by :py:meth:`_get_render_data_` of the
          **same class**, if necessary,
        * call the overriden method, passing on *render_data*.

        NOTE:
            * It's recommended to call :py:meth:`RenderData.finalize()
              <term_image.renderable.RenderData.finalize>`
              instead as that assures a single invokation of this method.
            * Any definition of this method should be safe for multiple invokations on
              the same :py:class:`~term_image.renderable.RenderData` instance, just in
              case.

        .. seealso::
            :py:meth:`_get_render_data_`,
            :py:meth:`RenderData.finalize()
            <term_image.renderable.RenderData.finalize>`,
            the *finalize* parameter of :py:meth:`_init_render_`.
        """

    def _get_frame_count_(self) -> int | FrameCount:
        """Implements :py:attr:`~term_image.renderable.FrameCount.POSTPONED` frame
        count evaluation.

        Returns:
            The frame count of the renderable. See :py:attr:`frame_count`.

            .. note::
                Returning :py:attr:`~term_image.renderable.FrameCount.POSTPONED` or
                ``1`` (one) is invalid and may result in unexpected/undefined behaviour
                across various interfaces defined by this library (and those derived
                from them), since re-postponing evaluation is unsupported and the
                renderable would have been taken to be animated.

        The base implementation raises :py:class:`NotImplementedError`.
        """
        raise NotImplementedError("POSTPONED frame count evaluation isn't implemented")

    def _get_render_data_(self, *, iteration: bool) -> RenderData:
        """Generates data required for rendering that's based on internal or
        external state.

        Args:
            iteration: Whether the render operation requiring the data involves a
              sequence of :term:`renders` (most likely of different frames), or it's
              a one-off render.

        Returns:
            The generated render data.

        The render data should include **copies** of any **variable/mutable**
        internal/external state required for rendering and other data generated from
        constant state but which should **persist** throughout a render operation
        (which may involve consecutive/repeated renders of one or more frames).

        May also be used to "allocate" and initialize storage for mutable/variable
        data specific to a render operation.

        Typically, an overriding method should

        * call the overriden method,
        * update the namespace for its defining class (i.e
          :py:meth:`render_data[__class__]
          <term_image.renderable.RenderData.__getitem__>`) within the
          :py:class:`~term_image.renderable.RenderData` instance returned by the
          overriden method,
        * return the same :py:class:`~term_image.renderable.RenderData` instance.

        IMPORTANT:
            The :py:class:`~term_image.renderable.RenderData` instance returned must be
            associated [#rd1]_ with the type of the renderable on which this method is
            called i.e ``type(self)``. This is always the case for the base
            implementation of this method.

        NOTE:
            This method being called doesn't mean the data generated will be used
            immediately.

        .. seealso::
            :py:class:`~term_image.renderable.RenderData`,
            :py:meth:`_finalize_render_data_`,
            :py:meth:`~term_image.renderable.Renderable._init_render_`.
        """
        render_data = RenderData(type(self))
        render_data[__class__].update(
            size=self._get_render_size_(),
            frame_offset=self.__frame,
            seek_whence=Seek.START,
            duration=self.__frame_duration,
            iteration=iteration,
        )

        return render_data

    @abstractmethod
    def _get_render_size_(self) -> geometry.Size:
        """Returns the renderable's :term:`render size`.

        Returns:
            The size of the renderable's :term:`render output`.

        The base implementation raises :py:class:`NotImplementedError`.

        NOTE:
            Both dimensions are expected to be positive.

        .. seealso:: :py:attr:`render_size`
        """
        raise NotImplementedError

    def _handle_interrupted_draw_(
        self, render_data: RenderData, render_args: RenderArgs
    ) -> None:
        """Performs any necessary actions if :py:class:`KeyboardInterrupt` is raised
        while writing a frame to the terminal.

        Args:
            render_data: Render data.
            render_args: Render arguments.

        The base implementation does nothing.

        HINT:
            For a renderable that uses SGR sequences in its :term:`render output`,
            this method may write ``CSI 0 m`` to standard output.
        """

    def _init_render_(
        self,
        renderer: Callable[[RenderData, RenderArgs], Any],
        render_args: RenderArgs | None = None,
        padding: Padding | None = None,
        *,
        iteration: bool = False,
        finalize: bool = True,
        check_size: bool = False,
        allow_scroll: bool = False,
    ) -> tuple[Any, Padding | None]:
        """Initiates a render operation.

        Args:
            renderer: Performs a render operation or extracts render data and arguments
              for a render operation to be performed later on.
            render_args: Render arguments.
            padding: :term:`Render output` padding.
            iteration: Whether the render operation involves a sequence of renders
              (most likely of different frames), or it's a one-off render.
            finalize: Whether to finalize the render data passed to *renderer*
              immediately *renderer* returns.
            check_size: Whether to validate the [padded] :term:`render size` of
              **non-animations**.
            allow_scroll: Whether to validate the [padded] :term:`render height` of
              **non-animations**. Ignored if *check_size* is ``False``.

        Returns:
            A tuple containing

            * The return value of *renderer*.
            * *padding* (with equivalent **absolute** dimensions if it's an instance of
              :py:class:`~term_image.padding.AlignedPadding`).

        Raises:
            IncompatibleRenderArgsError: Incompatible render arguments.
            RenderSizeOutofRangeError: *check_size* is ``True`` and the [padded]
              :term:`render size` cannot fit into the :term:`terminal size`.

        After preparing render data and processing arguments, *renderer* is called with
        the following positional arguments:

        1. Render data associated with **the renderable's class**
        2. Render arguments associated with **the renderable's class** and initialized
           with *render_args*

        Any exception raised by *renderer* is propagated.

        IMPORTANT:
            Beyond this method (i.e any context from *renderer* onwards), use of any
            variable state (internal or external) should be avoided if possible.
            Any variable state (internal or external) required for rendering should
            be provided via :py:meth:`_get_render_data_`.

            If at all any variable state has to be used and is not
            reasonable/practicable to be provided via :py:meth:`_get_render_data_`,
            it should be read only once during a single render and passed to any
            nested/subsequent calls that require the value of that state during the
            same render.

            This is to prevent inconsitency in data used for the same render which may
            result in unexpected output.
        """
        if not (render_args and render_args.render_cls is type(self)):
            # Validate compatibility (and convert, if compatible)
            render_args = RenderArgs(type(self), render_args)
        terminal_size = get_terminal_size()
        render_data = self._get_render_data_(iteration=iteration)
        try:
            if padding and isinstance(padding, AlignedPadding) and padding.relative:
                padding = padding.resolve(terminal_size)

            if check_size:
                render_size = render_data[__class__].size
                width, height = (
                    padding.get_padded_size(render_size) if padding else render_size
                )
                terminal_width, terminal_height = terminal_size

                if width > terminal_width:
                    raise RenderSizeOutofRangeError(
                        f"{'Padded render' if padding else 'Render'} width out of "
                        f"range (got: {width}; terminal_width={terminal_width})"
                    )
                if not allow_scroll and height > terminal_height:
                    raise RenderSizeOutofRangeError(
                        f"{'Padded render' if padding else 'Render'} height out of "
                        f"range (got: {height}; terminal_height={terminal_height})"
                    )

            return renderer(render_data, render_args), padding
        finally:
            if finalize:
                render_data.finalize()

    @abstractmethod
    def _render_(self, render_data: RenderData, render_args: RenderArgs) -> Frame:
        """:term:`Renders` a frame.

        Args:
            render_data: Render data.
            render_args: Render arguments.

        Returns:
            The rendered frame.

            * *render_size* = :py:attr:`render_data[Renderable].size
              <term_image.renderable.Renderable._Data_.size>`.
            * The :py:attr:`~term_image.renderable.Frame.render_output` field holds the
              :term:`render output`. This string should:

              * contain as many lines as :py:attr:`render_size.height
                <term_image.geometry.Size.height>` i.e exactly
                ``render_size.height - 1`` occurences of ``\\n`` (the newline sequence).
              * occupy exactly :py:attr:`render_size.height
                <term_image.geometry.Size.height>` lines and
                :py:attr:`render_size.width <term_image.geometry.Size.width>` columns
                on each line when drawn onto a terminal screen, **at least** when the
                render **size** it not greater than the terminal size on either axis.

                .. tip::
                  If for any reason, the output behaves differently when the render
                  **height** is greater than the terminal height, the behaviour, along
                  with any possible alternatives or workarounds, should be duely noted.
                  This doesn't apply to the **width**.

              * **not** end with ``\\n`` (the newline sequence).

            * The value of the :py:attr:`~term_image.renderable.Frame.duration` field
              should be determined from the frame data source (or a default/fallback
              value, if undeterminable), if :py:attr:`render_data[Renderable].duration
              <term_image.renderable.Renderable._Data_.duration>` is
              :py:attr:`~term_image.renderable.FrameDuration.DYNAMIC`.
              Otherwise, it should be equal to
              :py:attr:`render_data[Renderable].duration
              <term_image.renderable.Renderable._Data_.duration>`.

        Raises:
            StopIteration: End of iteration for an animated renderable with
              :py:attr:`~term_image.renderable.FrameCount.INDEFINITE` frame count.
            RenderError: An error occured while rendering.

        NOTE:
            :py:class:`StopIteration` may be raised if and only if
            :py:attr:`render_data[Renderable].iteration
            <term_image.renderable.Renderable._Data_.iteration>` is ``True``.
            Otherwise, it would be out of place.

        .. seealso:: :py:class:`~term_image.renderable.Renderable._Data_`.
        """
        raise NotImplementedError

    # Inner classes ============================================================

    class _Data_(RenderData.Namespace):
        """_Data_()

        Render data namespace for :py:class:`~term_image.renderable.Renderable`.

        .. seealso::

           :ref:`renderable-data`,
           :py:meth:`~term_image.renderable.Renderable._render_`.
        """

        size: geometry.Size
        """:term:`Render size`

        See :py:meth:`~term_image.renderable.Renderable._render_`.
        """

        frame_offset: int
        """Frame number/offset

        If the :py:attr:`~term_image.renderable.Renderable.frame_count` of the
        renderable (that generated the data) is:

        * *definite* (i.e an integer); the value of this field is a **non-negative**
          integer **less than the frame count**, the number of the frame to be rendered.
        * :py:attr:`~term_image.renderable.FrameCount.INDEFINITE`, the value range and
          interpretation of this field depends on the value of :py:attr:`iteration`
          and :py:attr:`seek_whence`.

          If :py:attr:`iteration` is ``False``, the value is always **zero** and
          anything (such as a placeholder frame) may be rendered, as renderables with
          :py:attr:`~term_image.renderable.FrameCount.INDEFINITE` frame count are
          typically meant for iteration/animation.

          If :py:attr:`iteration` is ``True`` and :py:attr:`seek_whence` is:

          * :py:attr:`~term_image.renderable.Seek.CURRENT`, the value of this field
            may be:

            * **zero**, denoting that the next frame on the stream should be rendered.
            * **positive**, denoting that the stream should be seeked **forward** by
              :py:attr:`frame_offset` frames and then the new next frame should be
              rendered.
            * **negative**, denoting that the stream should be seeked **backward** by
              -:py:attr:`frame_offset` frames and then the new next frame should be
              rendered.

          * :py:attr:`~term_image.renderable.Seek.START`, the value of this field
            may be:

            * **zero**, denoting that the stream should be seeked to its beginning
              and then the first frame should be rendered.
            * **positive**, denoting that the stream should be seeked to the
              (:py:attr:`frame_offset`)th frame **after the first** and then the new
              next frame should be rendered.

          * :py:attr:`~term_image.renderable.Seek.END`, the value of this field
            may be:

            * **zero**, denoting that the stream should be seeked to its end
              and then the last frame should be rendered.
            * **negative**, denoting that the stream should be seeked to the
              (-:py:attr:`frame_offset`)th frame **before the last** and then the new
              next frame should be rendered.

            If the end of the stream cannot be determined (yet), such as with a live
            source, the furthest available frame in the **forward** direction should
            be taken to be the end.

          .. note::
             * If any seek operation is not supported by the underlying source, it
               should be ignored and the next frame on the stream should be rendered.
             * If forward seek is supported but the offset is out of the range of
               available frames, the stream should be seeked to the furthest available
               frame in the forward direction if its end cannot be determined (yet),
               such as with a live source.
               Otherwise i.e if the offset is determined to be beyond the end of the
               stream, :py:class:`StopIteration` should be raised
               (see :py:meth:`~term_image.renderable.Renderable._render_`).
             * If backward seek is supported but the offset is out of the range of
               available frames, the stream should be seeked to its beginning or the
               furthest available frame in the backward direction.

          .. tip::
             A :term:`render class` that implements
             :py:attr:`~term_image.renderable.FrameCount.INDEFINITE` frame count should
             specify which seek operations it supports and any necessary details.
        """

        seek_whence: Seek
        """Reference position for :py:attr:`frame_offset`

        If the :py:attr:`~term_image.renderable.Renderable.frame_count` of the
        renderable (that generated the data) is *definite*, or
        :py:attr:`~term_image.renderable.FrameCount.INDEFINITE` but
        :py:attr:`iteration` is ``False``; the value of this
        field is always :py:attr:`~term_image.renderable.Seek.START`.
        Otherwise i.e if :py:attr:`~term_image.renderable.Renderable.frame_count`
        is :py:attr:`~term_image.renderable.FrameCount.INDEFINITE` and
        :py:attr:`iteration` is ``True``, it may be any member of
        :py:class:`~term_image.renderable.Seek`.
        """

        duration: int | FrameDuration | None
        """Frame duration

        The possible values and their interpretation are the same as for
        :py:attr:`~term_image.renderable.Renderable.frame_duration`.
        See :py:meth:`~term_image.renderable.Renderable._render_`.
        """

        iteration: bool
        """:term:`Render` operation kind

        ``True`` if the render is part of a render operation involving a sequence of
        renders (most likely of different frames). Otherwise i.e if it's a one-off
        render, ``False``.
        """


_types.Renderable = Renderable
_types.RenderableMeta = RenderableMeta
_types.BASE_RENDER_ARGS.__init__(Renderable)

"""
.. Core of the Renderable API
"""

from __future__ import annotations

__all__ = ("Renderable",)

import sys
from abc import ABCMeta, abstractmethod
from dataclasses import astuple
from time import perf_counter_ns, sleep
from types import MappingProxyType
from typing import Any, Callable, ClassVar, Mapping

import term_image

from .. import geometry
from ..ctlseqs import CURSOR_DOWN, CURSOR_UP, HIDE_CURSOR, SHOW_CURSOR
from ..exceptions import InvalidSizeError, RenderableError
from ..utils import arg_type_error, arg_value_error_range, get_terminal_size
from . import _types
from ._enum import FrameCount, FrameDuration
from ._types import (
    Frame,
    HAlign,
    RenderArgs,
    RenderData,
    RenderFormat,
    RenderParam,
    VAlign,
)


class RenderableMeta(ABCMeta):
    """Base metaclass of the Renderable API.

    Implements certain aspects of the API such as render parameters.
    """

    def __new__(cls, name, bases, namespace, **kwargs):
        try:
            namespace["_RENDER_PARAMS_"] = MappingProxyType(
                namespace["_RENDER_PARAMS_"]
            )
        except KeyError:
            pass

        new_cls = super().__new__(cls, name, bases, namespace)

        if kwargs.get("_base"):  # Renderable
            all_render_params = namespace.get("_RENDER_PARAMS_", {})
            all_render_data = namespace.get("_RENDER_DATA_", frozenset())
            all_exported_descendant_attrs = frozenset(
                namespace.get("_EXPORTED_DESCENDANT_ATTRS_", ())
            )
        else:
            for base in bases:
                if issubclass(base, Renderable):
                    break
            else:
                raise RenderableError(f"{name!r} is not a subclass of 'Renderable'")

            all_render_params = {}
            all_render_data = set()
            all_cls_render_data = {}
            all_exported_descendant_attrs = set()  # remove duplicates

            for mro_cls in reversed(new_cls.mro()):
                if not issubclass(mro_cls, Renderable):
                    continue

                try:
                    all_render_params.update(vars(mro_cls)["_RENDER_PARAMS_"])
                except KeyError:
                    pass

                try:
                    cls_render_data = vars(mro_cls)["_RENDER_DATA_"]
                except KeyError:
                    pass
                else:
                    intersect = all_render_data & cls_render_data
                    if intersect:
                        for (
                            other_cls,
                            other_cls_render_data,
                        ) in all_cls_render_data.items():
                            intersect = cls_render_data & other_cls_render_data
                            if intersect:
                                break
                        raise RenderableError(
                            f"Render data {tuple(intersect)!r} of "
                            f"{mro_cls.__name__!r} conflict(s) with that/those of "
                            f"{other_cls.__name__!r}"
                        )
                    all_render_data.update(cls_render_data)
                    all_cls_render_data[mro_cls] = cls_render_data

                try:
                    all_exported_descendant_attrs.update(
                        vars(mro_cls)["_EXPORTED_DESCENDANT_ATTRS_"]
                    )
                except KeyError:
                    pass

        new_cls._ALL_RENDER_PARAMS = MappingProxyType(all_render_params)
        new_cls._ALL_RENDER_DATA = frozenset(all_render_data)
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

          * positive integer, the duration of every frame is fixed to the given
            value (in **milliseconds**).
          * :py:class:`~term_image.renderable.FrameDuration` enum member, see the
            member's description.

          This argument is ignored if *frame_count* equals 1 (one)
          i.e the renderable is non-animated.

    Raises:
        TypeError: An argument is of an inappropriate type.
        ValueError: An argument is of an appropriate type but has an
          unexpected/invalid value.
    """

    # Class Attributes

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

    _RENDER_DATA_: ClassVar[frozenset[str]] = frozenset(
        {"size", "frame", "duration", "iteration"}
    )
    """Render data.

    This specifies keys expected to be in the dictionary returned by
    :py:meth:`_get_render_data_`, which are also attributes of a
    :py:class:`~term_image.renderable.RenderData` instance associated with the
    defining class.

    The render data of a class are inherited by its subclasses.
    In the case of name conflicts, :py:class:`~term_image.exceptions.RenderableError`
    is raised during class creation.

    NOTE:
        Defining this is optional.
    """

    _RENDER_PARAMS_: ClassVar[Mapping[str, RenderParam]]
    """Render parameters.

    This specifies arguments that may be accepted by (or attributes of) a
    :py:class:`~term_image.renderable.RenderArgs` instance associated with the
    defining class. It maps parameter names to their definitions.

    The render parameters of a class are inherited by its subclasses.
    Parameter name conflicts are resolved according to the standard Method Resolution
    Order i.e the parameter definition by the class lowest in order takes precedence.

    NOTE:
        * Defining this is optional.
        * If defined, it is replaced with a read-only mapping containing the same items.
    """

    # Special Methods

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

        self.__frame_count = frame_count
        self.__frame = 0

    def __iter__(self) -> term_image.render.RenderIterator:
        """Returns a render iterator.

        Returns:
            An iterator with a loop count of 1 (one).

        :term:`Animated` renderables are iterable i.e they can be used with all means
        of iteration such as the ``for`` statement and iterable unpacking.
        """
        from term_image.render import RenderIterator

        return RenderIterator(self, loops=1)

    def __repr__(self) -> str:
        return "<{}: animated={}, render_size={}>".format(
            type(self).__name__,
            self.animated,
            self.render_size,
        )

    def __str__(self) -> str:
        """:term:`Renders` the current frame with default arguments and no formatting.

        Returns:
            The primary (unformatted) frame render output.

        Raises:
            term_image.exceptions.RenderError: An error occured during
              :term:`rendering`.
        """
        return self._init_render_(self._render_)[0].render

    # Properties

    @property
    def animated(self) -> bool:
        """``True`` if the renderable is :term:`animated`.

        GET:
            Returns ``True`` if the renderable is :term:`animated`.
            Otherwise, ``False``.
        """
        return self.__frame_count != 1

    @property
    def frame_count(self) -> int | FrameCount:
        """Frame count

        GET:
            Returns either

            * the number of frames the renderable has, or
            * :py:class:`~term_image.renderable.FrameCount.INDEFINITE`.
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

              * The fixed duration (in **milliseconds**) of **every** frame, or
              * :py:attr:`~term_image.renderable.FrameDuration.DYNAMIC`.

        SET:
            If the renderable is :term:`animated` and the value is

            * a positive integer, it is set as the fixed duration (in **milliseconds**)
              of **every** frame.
            * :py:attr:`~term_image.renderable.FrameDuration.DYNAMIC`, see the
              enum member's description.

            If the renderable is not animated, nothing is done.
        """
        return self.__frame_duration

    @frame_duration.setter
    def frame_duration(self, duration: int | FrameDuration) -> None:
        if not self.animated:
            return

        if isinstance(duration, int):
            if duration <= 0:
                raise arg_value_error_range("frame_duration", duration)
        elif not isinstance(duration, FrameDuration):
            raise arg_type_error("frame_duration", duration)

        self.__frame_duration = duration

    @property
    @abstractmethod
    def render_size(self) -> geometry.Size:
        """:term:`Render size`

        GET:
            Returns the size of the renderable's primary render output.
        """
        raise NotImplementedError

    # Public Methods

    def draw(
        self,
        render_args: RenderArgs | None = None,
        render_fmt: RenderFormat = RenderFormat(0, -2),
        *,
        animate: bool = True,
        loops: int = -1,
        cache: bool | int = 100,
        check_size: bool = True,
        scroll: bool = False,
    ) -> None:
        """Draws the current frame or an animation to standard output.

        Args:
            render_args: Render arguments.
            render_fmt: Render formatting arguments.

              Same as for :py:meth:`render`, except:

              * :term:`Padding width` must not be greater than the
                :term:`terminal width`.
              * :term:`Padding height` must not be greater than the
                :term:`terminal height`, for **animations**.

            animate: If ``False``, disable animation i.e draw only the current frame.
              Applies to :term:`animated` renderables only.
            loops: Applies to animations only.
              See :py:class:`~term_image.render.RenderIterator`.
            cache: Applies to animations only.
              See :py:class:`~term_image.render.RenderIterator`.
            check_size: If ``False``, :term:`render size` and :term:`padding size` are
              not validated, for **non-animations**.
            scroll: If ``True``, :term:`render height` and :term:`padding height` are
              not validated, for **non-animations**. Ignored if *check_size* is
              ``False``.

        Raises:
            TypeError: An argument is of an inappropriate type.
            term_image.exceptions.InvalidSizeError: The :term:`render size` and/or
              :term:`padding size` can not fit into the :term:`terminal size`.
            term_image.exceptions.RenderArgsError: Incompatible render arguments.
            term_image.exceptions.RenderError: An error occured during
              :term:`rendering`.

        NOTE:
            * For animations (i.e animated renderables with *animate* set to ``True``),
              :term:`render size` and :term:`padding size` are always validated.
            * Animations with **definite** frame count, **by default**, are infinitely
              looped and can be terminated with :py:data:`~signal.SIGINT`
              (``CTRL + C``), **without** raising :py:class:`KeyboardInterrupt`.
        """
        if render_args and not isinstance(render_args, RenderArgs):
            raise arg_type_error("render_args", render_args)
        if not isinstance(render_fmt, RenderFormat):
            raise arg_type_error("render_fmt", render_fmt)
        if self.animated and not isinstance(animate, bool):
            raise arg_type_error("animate", animate)

        # Validation of *loops* and *cache* is delegated to `RenderIterator`.

        if not isinstance(check_size, bool):
            raise arg_type_error("check_size", check_size)
        if not isinstance(scroll, bool):
            raise arg_type_error("scroll", scroll)

        animation = self.animated and animate
        output = sys.stdout

        # Validate size and get render data
        (render_data, render_args), render_size, render_fmt = self._init_render_(
            lambda *args: args,
            render_args,
            render_fmt,
            iteration=animation,
            finalize=False,
            check_size=check_size,
            scroll=scroll,
            animation=animation,
        )

        try:
            if output.isatty():
                output.write(HIDE_CURSOR)

            if animation:
                self._animate_(render_data, render_args, render_fmt, loops, cache)
            else:
                render = self._format_render_(
                    self._render_(render_data, render_args).render,
                    render_size,
                    render_fmt,
                )
                try:
                    output.write(render)
                    output.flush()
                except (KeyboardInterrupt, Exception):
                    self._handle_interrupted_draw_(render_data, render_args)
                    raise
        finally:
            output.write("\n")
            if output.isatty():
                output.write(SHOW_CURSOR)
            output.flush()
            render_data.finalize()

    def render(
        self,
        render_args: RenderArgs | None = None,
        render_fmt: RenderFormat = RenderFormat(1, 1),
    ) -> Frame:
        """:term:`Renders` the current frame.

        Args:
            render_args: Render arguments.
            render_fmt: Render formatting arguments.

              * Lines and columns surrounding the primary render output, within the
                padding size, are filled with spaces.
              * If the absolute equivalent of a padding dimension is less than the
                corresponding render dimension, it has no effect.

        Returns:
            The rendered frame.

        Raises:
            TypeError: An argument is of an inappropriate type.
            term_image.exceptions.RenderArgsError: Incompatible render arguments.
            term_image.exceptions.RenderError: An error occured during
              :term:`rendering`.
        """
        if render_args and not isinstance(render_args, RenderArgs):
            raise arg_type_error("render_args", render_args)
        if not isinstance(render_fmt, RenderFormat):
            raise arg_type_error("render_fmt", render_fmt)

        frame, render_size, render_fmt = self._init_render_(
            self._render_, render_args, render_fmt
        )
        formatted_size = render_fmt.get_formatted_size(render_size)

        return (
            frame
            if render_size == formatted_size
            else Frame(
                frame.number,
                frame.duration,
                formatted_size,
                self._format_render_(frame.render, render_size, render_fmt),
            )
        )

    def seek(self, offset: int) -> None:
        """Sets the current frame number.

        Args:
            offset: Frame number; ``0`` <= *offset* < :py:attr:`frame_count`.

        Raises:
            TypeError: An argument is of an inappropriate type.
            ValueError: An argument is of an appropriate type but has an
              unexpected/invalid value.
            term_image.exceptions.RenderableError: The renderable has
              :py:class:`~term_image.renderable.FrameCount.INDEFINITE` frame count.
        """
        if self.frame_count is FrameCount.INDEFINITE:
            raise RenderableError(
                "A renderable with INDEFINITE frame count is not seekable"
            )
        if not isinstance(offset, int):
            raise arg_type_error("offset", offset)
        if not 0 <= offset < self.frame_count:
            raise arg_value_error_range(
                "offset", offset, f"frame_count={self.frame_count}"
            )

        self.__frame = offset

    def tell(self) -> int:
        """Returns the current frame number.

        Returns:
            Zero, if the renderable is non-animated or has
            :py:class:`~term_image.renderable.FrameCount.INDEFINITE` frame count.
            Otherwise, the current frame number.
        """
        return self.__frame

    # Extension methods

    def _animate_(
        self,
        render_data: RenderData,
        render_args: RenderArgs,
        render_fmt: RenderFormat,
        loops: int,
        cache: bool | int,
    ) -> None:
        """Animates frames of a renderable on standard output.

        Args:
            render_data: Render data.
            render_args: Render arguments associated with the renderable's class.

        Called by :py:meth:`draw` for animations.

        All other parameters are the same as for :py:meth:`draw`, except that
        *render_fmt* always has **absolute** padding dimensions.

        NOTE:
            Render and padding size validation would've been performed by
            :py:meth:`draw`.
        """
        from term_image.render import RenderIterator

        lines = max(render_fmt.height, render_data.size.height)
        render_iter = RenderIterator._from_render_data_(
            self, render_data, render_args, render_fmt, loops, cache, finalize=False
        )
        cursor_to_top_left = "\r" + CURSOR_UP % (lines - 1)
        cursor_down = CURSOR_DOWN % lines
        write = sys.stdout.write
        flush = sys.stdout.flush

        try:
            # first frame
            try:
                frame = next(render_iter)
            except StopIteration:  # `INDEFINITE` frame count
                return
            write(frame.render)
            write(cursor_to_top_left)
            flush()

            # render next frame during current frame's duration
            duration_ms = frame.duration
            start_ns = perf_counter_ns()
            for frame in render_iter:  # Render next frame
                # left-over of current frame's duration
                sleep(
                    max(0, duration_ms * 10**6 - (perf_counter_ns() - start_ns))
                    / 10**9
                )

                # draw new frame
                write(frame.render)
                write(cursor_to_top_left)
                flush()

                # render next frame during current frame's duration
                start_ns = perf_counter_ns()
                duration_ms = frame.duration
        except KeyboardInterrupt:
            self._handle_interrupted_draw_(render_data, render_args)
        except Exception:
            self._handle_interrupted_draw_(render_data, render_args)
            raise
        else:
            # left-over of last frame's duration
            sleep(
                max(0, duration_ms * 10**6 - (perf_counter_ns() - start_ns)) / 10**9
            )
        finally:
            render_iter.close()
            # Move the cursor to the last line to prevent "overlayed" output in a
            # terminal
            write(cursor_down)
            flush()

    @staticmethod
    def _clear_frame_(
        render_data: RenderData,
        render_args: RenderArgs,
        render_region: geometry.Region,
    ) -> None:
        """Clears the current frame while drawing an animation, if necessary.

        Args:
            render_data: Render data.
            render_args: Render arguments.
            render_region: The region occupied by the primary render output,
              relative to the cursor position at the point of calling this method.

        Called by the base implementation of :py:meth:`_animate_` just before drawing
        the next frame of an animation.
        If writing to standard output, it's advisable to **not** flush the stream
        immediately to reduce the flicker interval. The stream will be flushed after
        writing the next frame.
        Upon return, ensure the cursor is at the same position it was at the point of
        calling this method.

        The base implementation does nothing.

        NOTE:
            * This is required only if drawing the next frame doesn't inherently
              overwrite the current frame.
            * This is only meant (and should only be used) as a last resort since
              clearing the current frame before drawing the next may result in visible
              flicker.
        """

    @classmethod
    def _finalize_render_data_(cls, render_data: RenderData) -> None:
        """Finalizes render data, if necessary.

        Args:
            render_data: Render data.

        Typically, an overriding method should

        * finalize the arguments generated by
          :py:meth:`~term_image.renderable.Renderable._get_render_data_`
          defined by the **same class**, if necessary,
        * call the overriden method.

        NOTE:
            * Any definition of this method should be safe for multiple invokations on
              the same *render_data*, if possible.
            * It's recommended to call :py:meth:`RenderData.finalize()
              <term_image.renderable.RenderData.finalize>`
              instead as that assures a single invokation of this method.

        .. seealso::
            :py:attr:`_RENDER_DATA_`,
            :py:meth:`_get_render_data_`,
            :py:meth:`RenderData.finalize()
            <term_image.renderable.RenderData.finalize>`,
            the *finalize* parameter of :py:meth:`_init_render_`.
        """

    @staticmethod
    def _format_render_(
        render: str,
        render_size: geometry.Size,
        render_fmt: RenderFormat,
    ) -> str:
        """Formats (:term:`pads <padding>`, :term:`aligns <alignment>`, etc) a
        :term:`render` output.

        Args:
            render: A render output.
            render_size: The size of the render output.
            render_fmt: Render formatting arguments.

        Returns:
            The formatted render output.

            This also conforms to the form specified to be returned by
            :py:meth:`_render_`, provided the given render output does.

        NOTE:
            * *render* is expected to be in the form specified to be returned by
              :py:meth:`_render_`.
            * Only **absolute** padding dimensions are expected.
        """
        render_width, render_height = render_size
        width, height, h_align, v_align, *_ = astuple(render_fmt)
        width = max(width, render_width)
        height = max(height, render_height)
        horizontal = width > render_width
        vertical = height > render_height

        if horizontal:
            if h_align is HAlign.LEFT:
                left = 0
                right = width - render_width
            elif h_align is HAlign.RIGHT:
                left = width - render_width
                right = 0
            else:  # CENTER
                left = (width - render_width) // 2
                right = width - render_width - left
            left = " " * left
            right = " " * right
        else:
            left = right = ""

        if vertical:
            if v_align is VAlign.TOP:
                top = 0
                bottom = height - render_height
            elif v_align is VAlign.BOTTOM:
                top = height - render_height
                bottom = 0
            else:  # MIDDLE
                top = (height - render_height) // 2
                bottom = height - render_height - top
            top = f"{' ' * width}\n" * top if top else ""
            bottom = f"\n{' ' * width}" * bottom if bottom else ""
        else:
            top = bottom = ""

        return (
            "".join(
                (
                    top,
                    left,
                    render.replace("\n", f"{right}\n{left}") if horizontal else render,
                    right,
                    bottom,
                )
            )
            if horizontal or vertical
            else render
        )

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
                renderable has been taken to be animated.

        The base implementation raises :py:class:`NotImplementedError`.
        """
        raise NotImplementedError("POSTPONED frame count evaluation isn't implemented")

    def _get_render_data_(self, *, iteration: bool) -> dict[str, Any]:
        """Generates any data required for rendering that's based on internal or
        external state.

        Args:
            iteration: ``True`` if the render operation requiring the data involves a
              sequence of :term:`renders`, possibly of different frames.
              Otherwise, ``False`` i.e it's a one-off :term:`render`.

        Returns:
            Render data based on internal or external state.

        Should return copies of any variable internal/external state required for
        rendering or other data generated from constant state but which should persist
        for the lifetime of the render data e.g throughout the course of an animation
        or render iteration.

        May also be used to "allocate" storage for mutable/variable data specific to a
        set of consecutive/repeated render operations e.g for animation or render
        iteration.

        Typically, an overriding method should

        * call the overriden method,
        * update the dictionary returned by the overriden method,
        * return the dictionary.

        Though, it's not necessary to return the same dictionary as returned by the
        overriden method.

        IMPORTANT:
            The dictionary returned must contain values for all render data defined
            and inherited by the class that defines this method, not more, not less.
            Otherwise, an exception will be raised when creating the corresponding
            :py:class:`~term_image.renderable.RenderData` instance.

        NOTE:
            * This method being called doesn't mean the data generated will be used
              immediately.
            * It's recommended to get render data via
              :py:meth:`~term_image.renderable.Renderable._init_render_` instead.

        .. seealso::
            :py:attr:`_RENDER_DATA_`,
            :py:class:`~term_image.renderable.RenderData`,
            :py:meth:`_finalize_render_data_`,
            :py:meth:`~term_image.renderable.Renderable._init_render_`.
        """
        return dict(
            size=self.render_size,
            frame=self.tell(),
            duration=self.frame_duration,
            iteration=iteration,
        )

    def _handle_interrupted_draw_(
        self, render_data: RenderData, render_args: RenderArgs
    ) -> None:
        """Performs any necessary actions when :py:meth:`draw` or :py:meth:`_animate_`
        is interrupted.

        Args:
            render_data: Render data.
            render_args: Render arguments.

        The base implementation does nothing.

        HINT:
            For a renderable that uses SGR sequences in its render output, this method
            may write ``CSI 0 m`` to standard output.
        """

    def _init_render_(
        self,
        renderer: Callable[[RenderData, RenderArgs], Any],
        render_args: RenderArgs | None = None,
        render_fmt: RenderFormat | None = None,
        *,
        iteration: bool = False,
        finalize: bool = True,
        check_size: bool = False,
        scroll: bool = False,
        animation: bool = False,
    ) -> tuple[Any, geometry.Size, RenderFormat | None]:
        """Initiates a render operation.

        Args:
            renderer: Performs a render operation or extracts render data and arguments
              for a render operation to be performed later on.
            render_args: Render arguments.
            render_fmt: Render formatting arguments.
            iteration: ``True`` if the render operation involves a sequence of renders,
              possibly of different frames. Otherwise, ``False`` i.e it's a one-off
              render.
            finalize: If ``True``, the render data passed to *renderer* is finalized
              immediately *renderer* returns. Otherwise, finalizing the render data is
              left to the caller of this method.
            check_size: If ``False``, :term:`render size` and :term:`padding size` are
              not validated, for **non-animations**.
            scroll: If ``True``, :term:`render height` and :term:`padding height` are
              not validated, for **non-animations**. Applies only if *check_size* is
              ``True``.
            animation: If ``True``, *check_size* and *scroll* are ignored;
              :term:`render size` and :term:`padding size` are validated.

        Returns:
            A tuple containing

            * The return value of *renderer*
            * The :term:`render size`
            * Render formatting arguments with equivalent **absolute** padding
              dimensions, if *render_fmt* is given and not ``None``.
              Otherwise, ``None``.

        Raises:
            term_image.exceptions.RenderArgsError: Incompatible render arguments.
            term_image.exceptions.InvalidSizeError: *check_size* or *animation* is
              ``True`` and the :term:`render size` and/or :term:`padding size` cannot
              fit into the :term:`terminal size`.

        After preparing render data and processing arguments, *renderer* is called with
        the following positional arguments:

        1. Render data associated with **the renderable's class**
        2. Render arguments associated with **the renderable's class** and initialized
           with *render_args*

        Any exception raised by *renderer* is propagated.

        TIP:
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
        render_args = RenderArgs(type(self), render_args)  # Validate and complete
        terminal_size = get_terminal_size()
        render_data = RenderData(
            type(self), **self._get_render_data_(iteration=iteration)
        )

        try:
            if render_fmt:
                render_fmt = render_fmt.absolute(terminal_size)

            if check_size or animation:
                width, height = render_data.size
                terminal_width, terminal_height = terminal_size

                if width > terminal_width:
                    raise InvalidSizeError(
                        "Render width out of range "
                        f"(got: {width}, terminal_width={terminal_width})"
                    )
                if render_fmt and render_fmt.width > terminal_width:
                    raise InvalidSizeError(
                        "Padding width out of range "
                        f"(got: {render_fmt.width}, terminal_width={terminal_width})"
                    )

                if animation or not scroll:
                    if height > terminal_height:
                        raise InvalidSizeError(
                            f"Render height out of range (got: {height}, "
                            f"terminal_height={terminal_height}, animation={animation})"
                        )
                    if render_fmt and render_fmt.height > terminal_height:
                        raise InvalidSizeError(
                            f"Padding height out of range (got: {render_fmt.height}, "
                            f"terminal_height={terminal_height}, animation={animation})"
                        )

            return renderer(render_data, render_args), render_data.size, render_fmt
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

            * The :py:attr:`~term_image.renderable.Frame.render` field holds the
              **primary** :term:`render` output. This string should:

              * contain as many lines as ``render_data.size.height`` i.e
                exactly ``render_data.size.height - 1`` occurences of ``\\n``
                (the newline sequence).
              * occupy exactly ``render_data.size.width`` columns and
                ``render_data.size.height`` lines when drawn onto a terminal screen,
                **at least** when the render **size** it not greater than the terminal
                size on either axis.

                .. tip::
                  If for any reason, the output behaves differently when the render
                  **height** is greater than the terminal height, the behaviour, along
                  with any possible alternatives or workarounds, should be duely noted.
                  This doesn't apply to the **width**.

              * **not** end with ``\\n`` (the newline sequence).

            * The value of the :py:attr:`~term_image.renderable.Frame.duration` field
              should be determined from the frame data source (or a default/fallback
              value, if undeterminable), if ``render_data.duration`` is
              :py:attr:`~term_image.renderable.FrameDuration.DYNAMIC`.
              Otherwise, it should be equal to ``render_data.duration``.

        Raises:
            StopIteration: End of iteration for an animated renderable with
              :py:attr:`~term_image.renderable.FrameCount.INDEFINITE` frame count.
            term_image.exceptions.RenderError: An error occured while rendering.

        NOTE:
            :py:class:`StopIteration` may be raised if and only if
            ``render_data.iteration`` is ``True``. Otherwise, it would be out of place.
        """
        raise NotImplementedError


_types.Renderable = Renderable
_types.RenderableMeta = RenderableMeta
_types.BASE_RENDER_ARGS.__init__(Renderable)

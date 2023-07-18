"""
.. Custom data types for the Renderable API
"""

from __future__ import annotations

__all__ = (
    "Frame",
    "RenderArgs",
    "RenderData",
    "RenderFormat",
    "RenderParam",
)

import os
from dataclasses import dataclass
from typing import Any, Callable, NamedTuple, Type

from .. import geometry
from ..exceptions import RenderArgsError, RenderDataError, RenderFormatError
from ..geometry import Size
from ..utils import (
    arg_type_error,
    arg_type_error_msg,
    arg_value_error,
    arg_value_error_msg,
    arg_value_error_range,
)
from ._enum import HAlign, VAlign


class Frame(NamedTuple):
    """A rendered frame.

    NOTE:
        Arguments are not validated since instances are only meant to be created
        internally.
    """

    number: int
    """Frame number

    Zero, if the frame belongs to a non-animated renderable or one with
    :py:attr:`~term_image.renderable.FrameCount.INDEFINITE` frame count.
    Otherwise, a non-negative integer.
    """

    duration: int | None
    """Frame duration (in **milliseconds**)

    ``None``, if the frame belongs to a non-animated renderable. Otherwise, a positive
    integer.
    """

    size: geometry.Size
    """Frame :term:`render size`"""

    render: str
    """Frame :term:`render` output"""

    def __str__(self) -> str:
        """Returns the frame render output.

        Returns:
            The frame render output, :py:attr:`render`.
        """
        return self.render


class RenderArgsData:
    def __delattr__(self, _):
        raise AttributeError("Can't delete attribute")

    def __repr__(self):
        return "".join(
            (
                f"{type(self).__name__}({self.render_cls.__name__}",
                ", " if self.__dict__ else "",
                ", ".join(f"{arg}={value!r}" for arg, value in self.__dict__.items()),
                ")",
            )
        )


class RenderArgs(RenderArgsData):
    """Render arguments.

    Args:
        render_cls: :py:class:`~term_image.renderable.Renderable` or a subclass of it.
        init_render_args: An instance of this class. If given and not ``None``,

          * it must be *compatible* with *render_cls*,
          * it'll be used to initialize the render arguments.

        render_args: Render arguments for *render_cls*.

    Raises:
        TypeError: An argument is of an inappropriate type.
        term_image.exceptions.RenderArgsError: *init_render_args* isn't *compatible*
          with *render_cls*.
        term_image.exceptions.RenderArgsError: Unknown render parameter for
          *render_cls*.
        ValueError: A render argument is of an appropriate type but has an
          unexpected/invalid value.

    The value of each render argument is determined from the following sources,
    in [descending] order of precedence:

    - *render_args*
    - *init_render_args*
    - default values defined/inherited by *render_cls*

    The render arguments are exposed as attributes of an instance.

    NOTE:
        * An instance is *compatible* with its associated subclass of
          :py:class:`~term_image.renderable.Renderable` (:py:attr:`render_cls`) and
          its subclasses.
        * Instances are effectively immutable but modified copies can be created via
          :py:meth:`copy`.

    TIP:
        See :py:class:`~term_image.renderable.Renderable` and its subclasses for the
        names and descriptions of their respective render parameters.
    """

    __slots__ = ("render_cls",)

    __interned: dict[type[Renderable], RenderArgs] = {}

    def __new__(
        cls,
        render_cls: type[Renderable],
        init_render_args: RenderArgs | None = None,
        **render_args: Any,
    ) -> RenderArgs:
        if init_render_args:
            if not isinstance(render_cls, RenderableMeta):
                raise arg_type_error("render_cls", render_cls)

            if not isinstance(init_render_args, cls):
                raise arg_type_error("init_render_args", init_render_args)

            if not issubclass(render_cls, init_render_args.render_cls):
                raise RenderArgsError(
                    f"Render arguments for {init_render_args.render_cls.__name__!r} "
                    f"are incompatible with {render_cls.__name__!r}"
                )

        # has default values only
        if not render_args and (
            not init_render_args
            or init_render_args is BASE_RENDER_ARGS
            or cls.__interned.get(init_render_args.render_cls) is init_render_args
        ):
            try:
                return cls.__interned[render_cls]
            except KeyError:
                pass

        if (
            init_render_args
            and init_render_args.render_cls is render_cls
            and not render_args
        ):
            return init_render_args

        return super().__new__(cls)

    def __init__(
        self,
        render_cls: type[Renderable],
        init_render_args: RenderArgs | None = None,
        **render_args: Any,
    ) -> None:
        # `init_render_args` is validated in `__new__()`.
        # `render_cls` is validated in `__new__()`, if and only if `init_render_args`
        # is not `None`.

        # has default values only
        if not render_args and (
            not init_render_args
            or init_render_args is BASE_RENDER_ARGS
            or (
                type(self).__interned.get(init_render_args.render_cls)
                is init_render_args
            )
        ):
            if render_cls in type(self).__interned:  # has been initialized
                return
            intern = True
        else:
            intern = False

        if init_render_args:
            if init_render_args.render_cls is render_cls and not render_args:
                return
        # `render_cls` wasn't validated in `__new__()`
        elif not isinstance(render_cls, RenderableMeta):
            raise arg_type_error("render_cls", render_cls)

        super().__setattr__("render_cls", render_cls)
        self.__dict__.update(
            {
                name: param.default
                for name, param in render_cls._ALL_RENDER_PARAMS.items()
            }
        )

        if init_render_args:
            self.__dict__.update(init_render_args.__dict__)

        render_params = render_cls._ALL_RENDER_PARAMS
        for name, value in render_args.items():
            try:
                param = render_params[name]
            except KeyError:
                raise RenderArgsError(
                    f"Unknown render parameter {name!r} for {render_cls.__name__!r}"
                )

            if param.type_check and not param.type_check(render_cls, value):
                raise (
                    arg_type_error_msg(param.type_msg, value)
                    if param.type_msg
                    else arg_type_error(name, value)
                )
            if param.value_check and not param.value_check(render_cls, value):
                raise (
                    arg_value_error_msg(param.value_msg, value)
                    if param.value_msg
                    else arg_value_error(name, value)
                )
            self.__dict__[name] = value

        if intern:
            type(self).__interned[render_cls] = self

    def __init_subclass__(cls) -> None:
        cls.__interned = {}

    def __eq__(self, other: RenderArgs) -> bool:
        """Compares this set of render arguments with another.

        Args:
            other: Another set of render arguments.

        Returns:
            ``True`` if both are associated with the same subclass of
            :py:class:`~term_image.renderable.Renderable` and have equal argument
            values. Otherwise, ``False``.
        """
        if not isinstance(other, type(self)):
            return NotImplemented

        return (
            self is other
            or self.render_cls is other.render_cls
            and vars(self) == vars(other)
        )

    def __hash__(self) -> int:
        """Computes the hash of the render arguments.

        Returns:
            The computed hash.

        IMPORTANT:
            Like tuples, an instance is hashable if and only if the render argument
            values are hashable.
        """
        # Keys in instance dictionaries are always in the same order.
        # Hence, there's no need to take the keys into consideration.
        return hash((self.render_cls, tuple(vars(self).values())))

    def __getattr__(self, attr):
        raise AttributeError(
            f"Unknown render parameter {attr!r} for {self.render_cls.__name__!r}"
        )

    def __setattr__(self, *_):
        raise AttributeError("Can't set attribute, use the `copy()` method instead")

    render_cls: Type[Renderable]
    """The associated subclass of :py:class:`~term_image.renderable.Renderable`"""

    def copy(self, **render_args: Any) -> RenderArgs:
        """Creates a copy with some arguments modified.

        Args:
            render_args: Render arguments (for :py:attr:`render_cls`) to be modified in
              the returned instance.

        Returns:
            A new instance, if any argument is to be modified.
            Otherwise, the same instance.

        Raises the same exceptions as the constructor, where applicable.
        """
        return type(self)(self.render_cls, self, **render_args) if render_args else self


class RenderData(RenderArgsData):
    """Render data.

    Args:
        render_cls: :py:class:`~term_image.renderable.Renderable` or a subclass of it.
        render_data: Render data for *render_cls*.

    Raises:
        term_image.exceptions.RenderDataError: Unknown render data for *render_cls*.
        term_image.exceptions.RenderDataError: Incomplete render data for *render_cls*.

    Similar to :py:class:`RenderArgs`, except:

    - it works with :py:attr:`~term_image.renderable.Renderable._RENDER_DATA_`
      instead of :py:attr:`~term_image.renderable.Renderable._RENDER_PARAMS_`,
    - render data have no default values,
    - no argument validation is performed,
    - instances are mutable and may contain mutable data.

    IMPORTANT:
        See :py:class:`~term_image.renderable.Renderable` and its subclasses for the
        names and descriptions of their respective render data.

    NOTE:
        * Instances shouldn't be copied by any means because finalizing one copy may
          invalidate all other copies.
        * Instances should always be explicitly finalized as soon as they're no longer
          needed.
    """

    __slots__ = ("finalized", "render_cls")

    def __init__(self, render_cls: type[Renderable], **render_data: Any) -> None:
        super().__setattr__("render_cls", render_cls)
        super().__setattr__("finalized", False)

        render_params = render_cls._ALL_RENDER_DATA
        difference = render_data.keys() - render_params
        if difference:
            raise RenderDataError(
                f"Unknown render data for {render_cls.__name__!r} "
                f"(got: {', '.join(map(repr, difference))})"
            )

        self.__dict__.update(render_data)

        if len(self.__dict__) < len(render_params):
            missing = tuple(render_cls._ALL_RENDER_DATA - render_data.keys())
            raise RenderDataError(
                f"Incomplete render data for {render_cls.__name__!r} "
                f"(got: {tuple(render_data)}, missing={missing})"
            )

    def __del__(self):
        try:
            self.finalize()
        except AttributeError:  # Unsuccesful initialization
            pass

    def __getattr__(self, attr):
        raise AttributeError(
            f"Unknown render data {attr!r} for {self.render_cls.__name__!r}"
        )

    def __setattr__(self, attr, value):
        if attr not in self.render_cls._ALL_RENDER_DATA:
            raise AttributeError(
                f"Unknown render data {attr!r} for {self.render_cls.__name__!r}"
            )
        super().__setattr__(attr, value)

    finalized: bool
    """Finalization status"""

    render_cls: Type[Renderable]
    """The associated subclass of :py:class:`~term_image.renderable.Renderable`"""

    def finalize(self) -> None:
        """Finalizes the render data.

        Calls :py:meth:`~term_image.renderable.Renderable._finalize_render_data_`
        of the associated subclass of :py:class:`~term_image.renderable.Renderable`.

        NOTE:
            This method is safe for multiple invokations on the same instance.
        """
        if not self.finalized:
            try:
                self.render_cls._finalize_render_data_(self)
            finally:
                super().__setattr__("finalized", True)


@dataclass(frozen=True)
class RenderFormat:
    """Render formatting arguments.

    Args:
        width: :term:`Padding width`.
        height: :term:`Padding height`.
        h_align: :term:`Horizontal alignment`.
        v_align: :term:`Vertical alignment`.

    Raises:
        TypeError: An argument is of an inappropriate type.

    If *width* or *height* is:

    * positive, it is **absolute** and used as-is.
    * non-positive, it is **relative** to the corresponding terminal dimension
      (**at the point of resolution**) and equivalent to the absolute dimension
      ``max(terminal_dimension + dimension, 1)``.

    NOTE:
        Public interfaces receiving an instance with **relative** dimensions should
        typically translate it to an instance with equivalent **absolute** padding
        dimensions upon reception.

    .. seealso:: :doc:`/guide/formatting`.
    """

    __slots__ = ("width", "height", "h_align", "v_align", "relative", "_size")

    width: int
    """:term:`Padding width`"""

    height: int
    """:term:`Padding height`"""

    h_align: HAlign
    """:term:`Horizontal alignment`"""

    v_align: VAlign
    """:term:`Vertical alignment`"""

    relative: bool
    """``True`` if either or both padding dimension(s) is/are relative i.e non-positive.
    Otherwise, ``False``.
    """

    def __init__(
        self,
        width: int,
        height: int,
        h_align: HAlign = HAlign.CENTER,
        v_align: VAlign = VAlign.MIDDLE,
    ):
        if not isinstance(width, int):
            raise arg_type_error("width", width)
        if not isinstance(height, int):
            raise arg_type_error("height", height)
        if not isinstance(h_align, HAlign):
            raise arg_type_error("h_align", h_align)
        if not isinstance(v_align, VAlign):
            raise arg_type_error("v_align", v_align)

        super().__setattr__("width", width)
        super().__setattr__("height", height)
        super().__setattr__("h_align", h_align)
        super().__setattr__("v_align", v_align)
        super().__setattr__("relative", not width > 0 < height)

    def __repr__(self) -> str:
        return "{}(width={}, height={}, h_align={}, v_align={}, relative={})".format(
            type(self).__name__,
            self.width,
            self.height,
            self.h_align.name,
            self.v_align.name,
            self.relative,
        )

    @property
    def size(self) -> Size:
        """:term:`Padding size`

        GET:
            Returns the padding dimensions.
        """
        try:
            return self._size
        except AttributeError:
            size = Size(self.width, self.height)
            super().__setattr__("_size", size)
            return size

    def absolute(self, terminal_size: os.terminal_size) -> RenderFormat:
        """Resolves **relative** padding dimensions.

        Args:
            terminal_size: The terminal size against which to resolve relative padding
              dimensions.

        Returns:
            An instance with equivalent **absolute** padding dimensions.

        Raises:
            TypeError: An argument is of an inappropriate type.
        """
        if not self.relative:
            return self

        if not isinstance(terminal_size, os.terminal_size):
            raise arg_type_error("terminal_size", terminal_size)

        width, height = self.width, self.height
        terminal_width, terminal_height = terminal_size
        if width <= 0:
            width = max(terminal_width + width, 1)
        if height <= 0:
            height = max(terminal_height + height, 1)

        return type(self)(width, height, self.h_align, self.v_align)

    def get_formatted_size(self, render_size: Size) -> Size:
        """Computes the expected size of a formated render output.

        Args:
            render_size: Primary :term:`render size`.

        Returns:
            The size of the formatted render output that would be produced using
            this set of formatting arguments on a render output with the given size.

        Raises:
            term_image.exceptions.RenderFormatError: Relative padding dimension(s).
            TypeError: An argument is of an inappropriate type.
            ValueError: An argument is of an appropriate type but has an
              unexpected/invalid value.
        """
        if self.relative:
            raise RenderFormatError("Relative padding dimension(s)")

        if not isinstance(render_size, Size):
            raise arg_type_error("render_size", render_size)
        if not render_size.width > 0 < render_size.height:
            raise arg_value_error_range("render_size", render_size)

        return Size(*map(max, (self.width, self.height), render_size))


class RenderParam(NamedTuple):
    """Render parameter definition.

    Args:
        default: The default value of the render parameter.
        type_check: Render argument type validator. If

          * ``None``, argument type validation is skipped.
          * not ``None``, it is called with the class of the renderable for which a
            render argument is given and the argument itself.
            If it returns ``False``, ``TypeError(type_msg)`` is raised.

        type_msg: The error message when *type_check* returns ``False`` for a render
          argument. If `None`, a generic error message is generated.
        value_check: Render argument value validator. If

          * ``None``, argument value validation is skipped.
          * not ``None``, it is called with the class of the renderable for which a
            render argument is given and the argument itself.
            If it returns ``False``, ``ValueError(value_msg)`` is raised.

        value_msg: The error message when *value_check* returns ``False`` for a render
          argument. If `None`, a generic error message is generated.

    IMPORTANT:
        Parameter values (including *default*) should be immutable and hashable.
        Otherwise, :py:class:`~term_image.renderable.RenderArgs`\\ ' contract of
        immutability and/or hashability would be broken and it may also result in
        unexpected behaviour during render operations.
    """

    default: Any
    """Default value

    :meta hide-value:
    """

    type_check: Callable[[type[Renderable], Any], bool] | None = None
    """Type validator

    :meta hide-value:
    """

    type_msg: str | None = None
    """Type error message

    :meta hide-value:
    """

    value_check: Callable[[type[Renderable], Any], bool] | None = None
    """Value validator

    :meta hide-value:
    """

    value_msg: str | None = None
    """Value error message

    :meta hide-value:
    """


BASE_RENDER_ARGS = RenderArgs.__new__(RenderArgs, None)

# Updated from `._renderable`
Renderable = "Renderable"
RenderableMeta = "RenderableMeta"
